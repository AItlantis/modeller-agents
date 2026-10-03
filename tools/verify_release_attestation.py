"""Validate a GitHub SLSA statement bundled beside a modeller-agents wheel.

The caller must run ``gh attestation verify`` first. This script checks the
verified statement's subject digest and invocation against the exact workflow
run that produced the assets. Release mode requires an immutable version tag;
smoke mode can explicitly allow a branch ref and never publishes a release.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import posixpath
import sys
from pathlib import Path
from typing import Any


PROVENANCE_TYPE = "https://slsa.dev/provenance/v1"


def _load_statement(bundle_path: Path) -> dict[str, Any]:
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        payload = bundle["dsseEnvelope"]["payload"]
        statement = json.loads(base64.b64decode(payload, validate=True))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Sigstore DSSE bundle {bundle_path}: {exc}") from exc
    if not isinstance(statement, dict):
        raise ValueError("attestation payload must be a JSON object")
    return statement


def verify_release_attestation(
    wheel_path: Path,
    bundle_path: Path,
    *,
    source_repository: str,
    source_sha: str,
    source_ref: str,
    source_tag: str,
    workflow_path: str,
    server_url: str,
    run_id: str,
    run_attempt: str,
    allow_branch_ref: bool = False,
) -> None:
    """Raise ``ValueError`` unless the statement binds this wheel to this run."""
    statement = _load_statement(bundle_path)
    subjects = statement.get("subject")
    if statement.get("predicateType") != PROVENANCE_TYPE:
        raise ValueError("attestation must contain SLSA provenance v1")
    if not isinstance(subjects, list) or len(subjects) != 1:
        raise ValueError("attestation must have exactly one subject: the release wheel")

    wheel_digest = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    subject = subjects[0]
    subject_name = subject.get("name", "") if isinstance(subject, dict) else ""
    subject_digest = subject.get("digest", {}) if isinstance(subject, dict) else {}
    if posixpath.basename(str(subject_name).replace("\\", "/")) != wheel_path.name:
        raise ValueError("attestation subject name does not match the published wheel")
    if not isinstance(subject_digest, dict) or subject_digest.get("sha256") != wheel_digest:
        raise ValueError("attestation subject digest does not match the published wheel bytes")

    predicate = statement.get("predicate")
    build_definition = predicate.get("buildDefinition") if isinstance(predicate, dict) else None
    run_details = predicate.get("runDetails") if isinstance(predicate, dict) else None
    if not isinstance(build_definition, dict) or not isinstance(run_details, dict):
        raise ValueError("SLSA provenance is missing buildDefinition or runDetails")

    external_parameters = build_definition.get("externalParameters", {})
    workflow = external_parameters.get("workflow", {}) if isinstance(external_parameters, dict) else {}
    if not isinstance(workflow, dict):
        raise ValueError("provenance is missing its workflow source identity")
    expected_repository = f"https://github.com/{source_repository}"
    if workflow.get("repository") != expected_repository:
        raise ValueError("provenance source repository does not match this release")
    if workflow.get("ref") != source_ref:
        raise ValueError("provenance source ref does not match the release tag event")
    if workflow.get("path") != workflow_path:
        raise ValueError("provenance workflow path does not match the release workflow")

    resolved = build_definition.get("resolvedDependencies", [])
    expected_material_uri = f"git+{expected_repository}@{source_ref}"
    if not isinstance(resolved, list):
        raise ValueError("provenance resolvedDependencies must be a list")
    if not any(
        isinstance(material, dict)
        and material.get("uri") == expected_material_uri
        and isinstance(material.get("digest"), dict)
        and material["digest"].get("gitCommit") == source_sha
        for material in resolved
    ):
        raise ValueError("provenance does not bind the expected source commit")

    metadata = run_details.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("provenance is missing run metadata")
    expected_invocation = (
        f"{server_url.rstrip('/')}/{source_repository}/actions/runs/"
        f"{run_id}/attempts/{run_attempt}"
    )
    if metadata.get("invocationId") != expected_invocation:
        raise ValueError("provenance invocation ID does not match this exact CI run attempt")
    if allow_branch_ref:
        if source_tag or not source_ref.startswith("refs/heads/"):
            raise ValueError("smoke source ref must be a branch ref with no release tag")
    elif not source_tag or source_ref != f"refs/tags/{source_tag}":
        raise ValueError("release source ref is not the expected immutable tag event")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--source-tag", default="")
    parser.add_argument("--workflow-path", required=True)
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument(
        "--allow-branch-ref",
        action="store_true",
        help="allow branch refs for the non-publishing manual attestation smoke workflow",
    )
    args = parser.parse_args()
    try:
        verify_release_attestation(
            args.wheel,
            args.bundle,
            source_repository=args.source_repository,
            source_sha=args.source_sha,
            source_ref=args.source_ref,
            source_tag=args.source_tag,
            workflow_path=args.workflow_path,
            server_url=args.server_url,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            allow_branch_ref=args.allow_branch_ref,
        )
    except (OSError, ValueError) as exc:
        print(f"release attestation verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Verified wheel provenance for {args.source_sha}, run {args.run_id}/{args.run_attempt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
