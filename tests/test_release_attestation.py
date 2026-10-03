"""Tests for release wheel attestation subject and run binding."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from tools.verify_release_attestation import verify_release_attestation


REPOSITORY = "AItlantis/modeller-agents"
SOURCE_SHA = "a" * 40
SOURCE_REF = "refs/tags/v0.1.0"
RUN_ID = "123456789"
RUN_ATTEMPT = "2"
SERVER_URL = "https://github.com"
WORKFLOW_PATH = ".github/workflows/release.yml"


def _release_files(tmp_path: Path) -> tuple[Path, Path]:
    wheel = tmp_path / "modeller_agents-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"the exact published wheel bytes")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": wheel.name, "digest": {"sha256": digest}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "externalParameters": {
                    "workflow": {
                        "repository": f"https://github.com/{REPOSITORY}",
                        "ref": SOURCE_REF,
                        "path": WORKFLOW_PATH,
                    }
                },
                "resolvedDependencies": [
                    {
                        "uri": f"git+https://github.com/{REPOSITORY}@{SOURCE_REF}",
                        "digest": {"gitCommit": SOURCE_SHA},
                    }
                ],
            },
            "runDetails": {
                "metadata": {
                    "invocationId": (
                        f"{SERVER_URL}/{REPOSITORY}/actions/runs/"
                        f"{RUN_ID}/attempts/{RUN_ATTEMPT}"
                    )
                }
            },
        },
    }
    bundle = tmp_path / f"{wheel.name}.sigstore.json"
    bundle.write_text(
        json.dumps(
            {
                "dsseEnvelope": {
                    "payloadType": "application/vnd.in-toto+json",
                    "payload": base64.b64encode(json.dumps(statement).encode()).decode(),
                    "signatures": [],
                }
            }
        ),
        encoding="utf-8",
    )
    return wheel, bundle


def _verify(wheel: Path, bundle: Path, **overrides: str) -> None:
    values = {
        "source_repository": REPOSITORY,
        "source_sha": SOURCE_SHA,
        "source_ref": SOURCE_REF,
        "source_tag": "v0.1.0",
        "workflow_path": WORKFLOW_PATH,
        "server_url": SERVER_URL,
        "run_id": RUN_ID,
        "run_attempt": RUN_ATTEMPT,
    }
    values.update(overrides)
    verify_release_attestation(wheel, bundle, **values)


def test_accepts_attestation_for_exact_wheel_source_and_run_attempt(tmp_path: Path) -> None:
    wheel, bundle = _release_files(tmp_path)

    _verify(wheel, bundle)


@pytest.mark.parametrize(
    ("override", "value", "message"),
    [
        ("source_sha", "b" * 40, "source commit"),
        ("run_attempt", "1", "exact CI run attempt"),
        ("run_id", "987654321", "exact CI run attempt"),
        ("source_ref", "refs/tags/v0.1.1", "source ref"),
    ],
)
def test_rejects_wrong_source_or_run_binding(
    tmp_path: Path, override: str, value: str, message: str
) -> None:
    wheel, bundle = _release_files(tmp_path)

    with pytest.raises(ValueError, match=message):
        _verify(wheel, bundle, **{override: value})


def test_rejects_wheel_byte_change_after_attestation(tmp_path: Path) -> None:
    wheel, bundle = _release_files(tmp_path)
    wheel.write_bytes(wheel.read_bytes() + b" changed")

    with pytest.raises(ValueError, match="subject digest"):
        _verify(wheel, bundle)


def test_release_workflow_attests_and_publishes_the_wheel_bundle() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    )
    build_job = workflow["jobs"]["test-and-build"]
    permissions = build_job["permissions"]
    assert permissions["id-token"] == "write"
    assert permissions["attestations"] == "write"
    assert permissions["artifact-metadata"] == "write"

    steps = build_job["steps"]
    source_checkout = next(step for step in steps if step.get("name") == "Check out tagged modeller-agents source")
    assert source_checkout["with"]["ref"] == "${{ github.sha }}"
    build = next(step for step in steps if step.get("id") == "build-wheel")
    attest = next(step for step in steps if step.get("id") == "attest-wheel")
    assert steps.index(build) < steps.index(attest)
    assert attest["uses"] == "actions/attest@v4"
    assert attest["with"]["subject-path"] == (
        "${{ github.workspace }}/${{ steps.build-wheel.outputs.wheel-path }}"
    )

    uploaded_artifact = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
    assert "modeller-agents/release-assets/*.whl.sigstore.json" in uploaded_artifact["with"]["path"]
    release_steps = workflow["jobs"]["create-draft-release"]["steps"]
    create_release = next(step for step in release_steps if "Create a draft release" in step.get("name", ""))
    assert "release-assets/*.whl.sigstore.json" in create_release["run"]
