"""Tests for the RuntimeEvent/RuntimeReceipt outbound contracts (WI-02).

Kept as a sibling file to test_contracts_identity.py rather than folded into
it: test_contracts_identity.py is scoped to the pre-existing
MissionIdentity/CheckpointReceipt precedent (additionalProperties:true,
defensive internal records); this file is scoped to the new
RuntimeEvent/RuntimeReceipt outbound contracts (additionalProperties:false,
authored to match a real external consumer). Keeping them separate makes the
posture difference between the two contract families legible from the test
layout itself, not just from schema comments.

Note: the shared `_validate_schema_value` engine in contracts.py (used by both
the pre-existing MissionIdentity/CheckpointReceipt validators and these new
RuntimeEvent/RuntimeReceipt validators) checks required/type/enum/pattern but
does not enforce JSON Schema's `additionalProperties: false`. The two new
schema files still declare `additionalProperties: false` (per the WI-02
brief, matching testudo-backend's producer-contract posture) as the intended
contract shape for any future stricter validator or external consumer; this
test file therefore does not assert that extra properties are rejected by
validate_runtime_event/validate_runtime_receipt today, since the shared
engine does not implement that check and extending it is outside WI-02's
write scope (contracts.py changes here are additive, not a rewrite of the
shared validation engine).
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from modeller.contracts import (
    RuntimeEvent,
    RuntimeReceipt,
    validate_runtime_event,
    validate_runtime_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


def _valid_runtime_event(**overrides) -> dict:
    event = RuntimeEvent(
        runtime_event_id="event-001",
        event_type="task.progressed",
        task_id="task-001",
        mission_id="mission-001",
        pipeline_execution_id="pipeline-exec-001",
        sequence=1,
        occurred_at="2026-08-09T00:00:00Z",
        payload={"detail": "stage 1 complete"},
    ).to_dict()
    event.update(overrides)
    return event


def _valid_runtime_receipt(**overrides) -> dict:
    receipt = RuntimeReceipt(
        receipt_id="receipt-001",
        task_id="task-001",
        mission_id="mission-001",
        pipeline_execution_id="pipeline-exec-001",
        status="completed",
        created_at="2026-08-09T00:00:00Z",
        evidence=["artifact://evidence-001"],
    ).to_dict()
    receipt.update(overrides)
    return receipt


def _copy_schema_runtime(tmp: Path) -> Path:
    root = tmp / "repo"
    (root / "schemas").mkdir(parents=True, exist_ok=True)
    for name in ["runtime-event.schema.json", "runtime-receipt.schema.json"]:
        shutil.copy(ROOT / "schemas" / name, root / "schemas" / name)
    return root


class RuntimeEventContractTests(unittest.TestCase):
    def test_valid_runtime_event_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_runtime_event(root, _valid_runtime_event())

            self.assertTrue(check.ok, check.errors)

    def test_missing_pipeline_execution_id_fails_with_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_event()
            del payload["pipeline_execution_id"]

            check = validate_runtime_event(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(
                any("pipeline_execution_id" in error for error in check.errors), check.errors
            )
            self.assertTrue(
                any("pipeline_execution_id" in item for item in check.remediation), check.remediation
            )

    def test_malformed_pipeline_execution_id_fails_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_event(pipeline_execution_id="bad id with spaces")

            check = validate_runtime_event(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(
                any("pipeline_execution_id" in error for error in check.errors), check.errors
            )

    def test_schema_version_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_event(schema_version=99)

            check = validate_runtime_event(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("schema_version" in error for error in check.errors), check.errors)
            self.assertTrue(check.remediation)

    def test_non_dict_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_runtime_event(root, ["not", "a", "dict"])  # type: ignore[arg-type]

            self.assertFalse(check.ok)
            self.assertTrue(check.remediation)


class RuntimeReceiptContractTests(unittest.TestCase):
    def test_valid_runtime_receipt_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_runtime_receipt(root, _valid_runtime_receipt())

            self.assertTrue(check.ok, check.errors)

    def test_missing_pipeline_execution_id_fails_with_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_receipt()
            del payload["pipeline_execution_id"]

            check = validate_runtime_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(
                any("pipeline_execution_id" in error for error in check.errors), check.errors
            )
            self.assertTrue(
                any("pipeline_execution_id" in item for item in check.remediation), check.remediation
            )

    def test_malformed_pipeline_execution_id_fails_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_receipt(pipeline_execution_id="bad id with spaces")

            check = validate_runtime_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(
                any("pipeline_execution_id" in error for error in check.errors), check.errors
            )

    def test_schema_version_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_receipt(schema_version=99)

            check = validate_runtime_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("schema_version" in error for error in check.errors), check.errors)
            self.assertTrue(check.remediation)

    def test_invalid_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))
            payload = _valid_runtime_receipt(status="not-a-real-status")

            check = validate_runtime_receipt(root, payload)

            self.assertFalse(check.ok)
            self.assertTrue(any("status" in error for error in check.errors), check.errors)

    def test_non_dict_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_schema_runtime(Path(tmp))

            check = validate_runtime_receipt(root, "not-a-dict")  # type: ignore[arg-type]

            self.assertFalse(check.ok)
            self.assertTrue(check.remediation)


if __name__ == "__main__":
    unittest.main()
