from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from modeller.contracts import (
    ArtifactLineageDigest,
    CheckpointAuthorization,
    CheckpointReceipt,
    MissionIdentity,
    validate_checkpoint_receipt,
    validate_mission_identity,
)


ROOT = Path(__file__).resolve().parents[1]


def _valid_mission_identity() -> dict:
    return MissionIdentity(
        project_id="proj-aitlantis",
        mission_id="mission-001",
        task_id="task-001",
        created_at="2026-08-07T00:00:00Z",
        lineage=[
            ArtifactLineageDigest(
                artifact_id="brief",
                digest="sha256:" + "a" * 64,
                produced_at="2026-08-07T00:00:00Z",
                producer_task_id="task-001",
            )
        ],
    ).to_dict()


def _valid_checkpoint_receipt(**overrides) -> dict:
    receipt = CheckpointReceipt(
        checkpoint_id="checkpoint-001",
        mission_id="mission-001",
        task_id="task-001",
        verified_at="2026-08-07T00:00:00Z",
        verification_status="verified",
        authorization=CheckpointAuthorization(
            decision="approved",
            actor_id="human-reviewer",
            actor_role="project-lead",
        ),
        subject_digest="sha256:" + "b" * 64,
    ).to_dict()
    receipt.update(overrides)
    return receipt


def _copy_schema_runtime(tmp: Path) -> Path:
    root = tmp / "repo"
    (root / "schemas").mkdir(parents=True, exist_ok=True)
    for name in ["mission-identity.schema.json", "checkpoint-receipt.schema.json"]:
        shutil.copy(ROOT / "schemas" / name, root / "schemas" / name)
    return root


class MissionIdentityContractTests(unittest.TestCase):
    def test_valid_mission_identity_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_mission_identity(root, _valid_mission_identity())

            self.assertTrue(check.ok, check.errors)

    def test_missing_required_field_is_rejected_with_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_mission_identity()
            del payload["task_id"]

            check = validate_mission_identity(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("task_id" in error for error in check.errors), check.errors)

    def test_stale_schema_version_is_rejected_with_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_mission_identity()
            payload["schema_version"] = 0

            check = validate_mission_identity(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("schema_version" in error for error in check.errors), check.errors)
            self.assertTrue(check.remediation)

    def test_malformed_identity_token_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_mission_identity()
            payload["mission_id"] = "bad id with spaces"

            check = validate_mission_identity(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("mission_id" in error for error in check.errors), check.errors)

    def test_malformed_lineage_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_mission_identity()
            payload["lineage"][0]["digest"] = "not-a-digest"

            check = validate_mission_identity(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("digest" in error for error in check.errors), check.errors)

    def test_non_dict_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_mission_identity(root, ["not", "a", "dict"])  # type: ignore[arg-type]

            self.assertFalse(check.ok)
            self.assertTrue(check.remediation)

    def test_missing_schema_file_is_reported_with_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            (root / "schemas").mkdir(parents=True, exist_ok=True)

            check = validate_mission_identity(root, _valid_mission_identity())

            self.assertFalse(check.ok)
            self.assertTrue(check.remediation)


class CheckpointReceiptContractTests(unittest.TestCase):
    def test_valid_checkpoint_receipt_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_checkpoint_receipt(root, _valid_checkpoint_receipt())

            self.assertTrue(check.ok, check.errors)

    def test_stale_verification_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt(verification_status="stale")

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("stale" in error for error in check.errors), check.errors)
            self.assertTrue(check.remediation)

    def test_incompatible_verification_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt(verification_status="incompatible")

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("incompatible" in error for error in check.errors), check.errors)

    def test_malformed_verification_status_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt(verification_status="not-a-real-status")

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("verification_status" in error for error in check.errors), check.errors)

    def test_missing_authorization_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt()
            del payload["authorization"]

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("authorization" in error for error in check.errors), check.errors)

    def test_invalid_authorization_decision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt()
            payload["authorization"]["decision"] = "maybe"

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("decision" in error for error in check.errors), check.errors)

    def test_malformed_subject_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt(subject_digest="not-a-digest")

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("subject_digest" in error for error in check.errors), check.errors)

    def test_schema_version_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt(schema_version=99)

            check = validate_checkpoint_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("schema_version" in error for error in check.errors), check.errors)

    def test_mission_binding_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt()
            mission_identity = _valid_mission_identity()
            mission_identity["mission_id"] = "other-mission"

            check = validate_checkpoint_receipt(root, payload, mission_identity=mission_identity)

            self.assertFalse(check.ok)
            self.assertTrue(any("mission_id" in error for error in check.errors), check.errors)

    def test_mission_binding_match_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_checkpoint_receipt()
            mission_identity = _valid_mission_identity()

            check = validate_checkpoint_receipt(root, payload, mission_identity=mission_identity)

            self.assertTrue(check.ok, check.errors)

    def test_non_dict_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_checkpoint_receipt(root, "not-a-dict")  # type: ignore[arg-type]

            self.assertFalse(check.ok)
            self.assertTrue(check.remediation)


if __name__ == "__main__":
    unittest.main()
