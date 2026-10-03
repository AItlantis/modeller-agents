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
SMOKE_WORKFLOW_PATH = ".github/workflows/release-attestation-smoke.yml"


def _release_files(
    tmp_path: Path,
    *,
    source_ref: str = SOURCE_REF,
    workflow_path: str = WORKFLOW_PATH,
) -> tuple[Path, Path]:
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
                        "ref": source_ref,
                        "path": workflow_path,
                    }
                },
                "resolvedDependencies": [
                    {
                        "uri": f"git+https://github.com/{REPOSITORY}@{source_ref}",
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


def _verify(wheel: Path, bundle: Path, **overrides: object) -> None:
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


def test_smoke_mode_accepts_an_exact_branch_run_but_release_mode_rejects_it(tmp_path: Path) -> None:
    source_ref = "refs/heads/main"
    wheel, bundle = _release_files(
        tmp_path, source_ref=source_ref, workflow_path=SMOKE_WORKFLOW_PATH,
    )

    with pytest.raises(ValueError, match="immutable tag event"):
        _verify(
            wheel, bundle, source_ref=source_ref, source_tag="",
            workflow_path=SMOKE_WORKFLOW_PATH,
        )

    _verify(
        wheel, bundle, source_ref=source_ref, source_tag="",
        workflow_path=SMOKE_WORKFLOW_PATH, allow_branch_ref=True,
    )


def test_smoke_mode_rejects_a_tag_or_non_branch_ref(tmp_path: Path) -> None:
    for source_ref, source_tag in ((SOURCE_REF, "v0.1.0"), ("refs/pull/6/merge", "")):
        wheel, bundle = _release_files(
            tmp_path, source_ref=source_ref, workflow_path=SMOKE_WORKFLOW_PATH,
        )
        with pytest.raises(ValueError, match="smoke source ref must be a branch ref"):
            _verify(
                wheel, bundle, source_ref=source_ref, source_tag=source_tag,
                workflow_path=SMOKE_WORKFLOW_PATH, allow_branch_ref=True,
            )


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


def test_manual_attestation_smoke_only_uploads_evidence_and_never_publishes() -> None:
    smoke_path = Path(".github/workflows/release-attestation-smoke.yml")
    smoke = yaml.load(smoke_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert set(smoke["on"]) == {"workflow_dispatch"}
    assert "create-draft-release" not in smoke["jobs"]
    assert set(smoke["jobs"]) == {"smoke"}
    smoke_job = smoke["jobs"]["smoke"]
    assert smoke_job["if"] == "github.ref == 'refs/heads/main'"
    permissions = smoke_job["permissions"]
    assert permissions["id-token"] == "write"
    assert permissions["attestations"] == "write"
    assert permissions["artifact-metadata"] == "write"

    steps = smoke_job["steps"]
    attest = next(step for step in steps if step.get("id") == "attest-wheel")
    verify = next(step for step in steps if step.get("name") == "Verify wheel signature and exact run")
    upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
    assert attest["uses"] == "actions/attest@v4"
    assert SMOKE_WORKFLOW_PATH in verify["run"]
    assert "--allow-branch-ref" in verify["run"]
    assert "github.run_id" in upload["with"]["name"]
    assert "github.run_attempt" in upload["with"]["name"]
    assert not any("gh release" in step.get("run", "") for step in steps)
