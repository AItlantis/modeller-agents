"""Contract tests for the dry-run Testudo Gateway adapter seam."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from modeller.adapters.testudo_gateway import (
    DryRunTransport,
    TestudoGatewayAdapter,
)


ROOT = Path(__file__).resolve().parents[1]


def _adapter(*, transport=None, max_retries=0, root=ROOT) -> tuple[TestudoGatewayAdapter, DryRunTransport | object]:
    actual_transport = transport or DryRunTransport()
    return TestudoGatewayAdapter(root=root, transport=actual_transport, max_retries=max_retries), actual_transport


def _identity(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "mission_id": "mission-rendering-001",
        "task_id": "task-rendering-001",
        "attempt_id": "attempt-001",
        "workflow_run_id": "workflow-run-001",
    }
    payload.update(overrides)
    return payload


class TestudoGatewayAdapterTests(unittest.TestCase):
    def test_pinned_v12_contract_is_validated(self) -> None:
        adapter, _ = _adapter()

        check = adapter.validate_contract()

        self.assertTrue(check.ok, check.errors)
        self.assertEqual(check.observed_version, "1.2")
        self.assertEqual(check.contract_sha, "dbd00cb1299f3f68add0e5971e6ec808f010059d")

    def test_mission_creation_preserves_identity_and_is_dry_run(self) -> None:
        adapter, transport = _adapter()

        result = adapter.create_mission({**_identity(), "objective": "render the network"})

        self.assertTrue(result.ok, result.errors)
        self.assertIsInstance(transport, DryRunTransport)
        self.assertEqual(len(transport.requests), 1)
        request = transport.requests[0]["payload"]
        self.assertEqual(request["mission_id"], "mission-rendering-001")
        self.assertEqual(request["task_id"], "task-rendering-001")
        self.assertEqual(request["attempt_id"], "attempt-001")
        self.assertEqual(request["workflow_run_id"], "workflow-run-001")
        self.assertEqual(request["correlation_id"], "task-correlation-task-rendering-001")
        self.assertEqual(result.correlation_id, adapter.correlation_id("mission-rendering-001", "task-rendering-001"))

    def test_plan_and_command_dispatch_validate_v12_run_config(self) -> None:
        adapter, transport = _adapter()

        plan = adapter.dispatch_plan({**_identity(), "plan": {"stages": ["RM-00", "RM-01"]}})
        command = adapter.dispatch_command(
            {
                **_identity(),
                "pipeline_id": "render-network",
                "pipeline_version": "1.0.0",
                "contract_version": "1.2",
                "config": {"inputs": {"scenario": "base"}, "params": {}, "metadata": {}},
            }
        )

        self.assertTrue(plan.ok, plan.errors)
        self.assertTrue(command.ok, command.errors)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(plan.correlation_id, command.correlation_id)
        self.assertEqual(transport.requests[1]["payload"]["contract_version"], "1.2")

    def test_receipt_ingestion_preserves_correlation_and_rejects_schema(self) -> None:
        adapter, _ = _adapter()
        dispatched = adapter.dispatch_command(
            {
                **_identity(),
                "pipeline_id": "render-network",
                "pipeline_version": "1.0.0",
                "config": {"inputs": {}},
            }
        )
        receipt = adapter.ingest_receipt(
            {
                **_identity(),
                "receipt_id": "receipt-001",
                "status": "completed",
                "contract_version": "1.2",
            }
        )
        bad = adapter.ingest_receipt({**_identity(), "receipt_id": "receipt-002", "status": "unknown"})

        self.assertTrue(dispatched.ok, dispatched.errors)
        self.assertTrue(receipt.ok, receipt.errors)
        self.assertEqual(receipt.correlation_id, dispatched.correlation_id)
        self.assertFalse(bad.ok)
        self.assertTrue(any("receipt status" in error for error in bad.errors), bad.errors)

    def test_retry_and_idempotency_replay_without_duplicate_transport(self) -> None:
        transport = DryRunTransport(failures_before_success=1)
        adapter, _ = _adapter(transport=transport, max_retries=1)
        command = {**_identity(), "pipeline_id": "render-network", "pipeline_version": "1.0.0"}

        first = adapter.dispatch_command(command, idempotency_key="dispatch-001")
        replay = adapter.dispatch_command(command, idempotency_key="dispatch-001")
        conflict = adapter.dispatch_command({**command, "pipeline_version": "2.0.0"}, idempotency_key="dispatch-001")

        self.assertTrue(first.ok, first.errors)
        self.assertEqual(first.attempts, 2)
        self.assertTrue(replay.ok)
        self.assertTrue(replay.duplicate)
        self.assertEqual(len(transport.requests), 2)
        self.assertFalse(conflict.ok)
        self.assertTrue(any("conflicts" in error for error in conflict.errors), conflict.errors)

    def test_canonical_correlation_must_remain_stable(self) -> None:
        adapter, _ = _adapter()
        canonical = "task-correlation-task-rendering-001"
        first = adapter.create_mission({**_identity(), "correlation_id": canonical})
        second = adapter.dispatch_plan({**_identity(), "correlation_id": "corr-other-001"})
        receipt = adapter.ingest_receipt(
            {
                **_identity(),
                "receipt_id": "receipt-003",
                "status": "completed",
                "correlation_id": canonical,
            }
        )

        self.assertTrue(first.ok, first.errors)
        self.assertFalse(second.ok)
        self.assertTrue(any("canonical" in error for error in second.errors), second.errors)
        self.assertTrue(receipt.ok, receipt.errors)
        self.assertEqual(receipt.correlation_id, canonical)

    def test_command_and_receipt_require_attempt_id(self) -> None:
        adapter, transport = _adapter()
        missing_attempt = _identity()
        del missing_attempt["attempt_id"]

        command = adapter.dispatch_command(
            {
                **missing_attempt,
                "pipeline_id": "render-network",
                "pipeline_version": "1.0.0",
            }
        )
        receipt = adapter.ingest_receipt(
            {
                **missing_attempt,
                "receipt_id": "receipt-missing-attempt",
                "status": "completed",
            }
        )

        self.assertFalse(command.ok)
        self.assertFalse(receipt.ok)
        self.assertTrue(any("attempt_id" in error for error in command.errors), command.errors)
        self.assertTrue(any("attempt_id" in error for error in receipt.errors), receipt.errors)
        self.assertEqual(transport.requests, [])

    def test_mismatched_attempt_identity_is_rejected_across_operations(self) -> None:
        adapter, transport = _adapter()
        command = adapter.dispatch_command(
            {**_identity(), "pipeline_id": "render-network", "pipeline_version": "1.0.0"}
        )
        receipt = adapter.ingest_receipt(
            {
                **_identity(attempt_id="attempt-002"),
                "receipt_id": "receipt-mismatched-attempt",
                "status": "completed",
            }
        )

        self.assertTrue(command.ok, command.errors)
        self.assertFalse(receipt.ok)
        self.assertTrue(any("attempt_id" in error for error in receipt.errors), receipt.errors)
        self.assertEqual(len(transport.requests), 1)

    def test_malformed_transport_response_fails_closed_and_is_not_cached(self) -> None:
        transport = DryRunTransport(
            responses={
                "dispatch_command": {
                    "accepted": True,
                    "contract_version": "1.1",
                    "correlation_id": "wrong-correlation",
                    "identity": {"task_id": "wrong-task"},
                }
            }
        )
        adapter, _ = _adapter(transport=transport)
        command = {**_identity(), "pipeline_id": "render-network", "pipeline_version": "1.0.0"}

        first = adapter.dispatch_command(command, idempotency_key="malformed-response-001")
        replay = adapter.dispatch_command(command, idempotency_key="malformed-response-001")

        self.assertFalse(first.ok)
        self.assertFalse(replay.ok)
        self.assertFalse(replay.duplicate)
        self.assertEqual(len(transport.requests), 2)
        self.assertTrue(any("contract_version" in error for error in first.errors), first.errors)
        self.assertTrue(any("correlation_id" in error for error in first.errors), first.errors)
        self.assertTrue(any("identity" in error for error in first.errors), first.errors)

    def test_contract_version_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            shutil.copytree(ROOT / "vendor", root / "vendor")
            (root / "vendor/modeller-pipelines/contracts/VERSION").write_text("1.1\n", encoding="utf-8")
            adapter = TestudoGatewayAdapter(root=root)

            check = adapter.validate_contract()
            result = adapter.create_mission(_identity())

            self.assertFalse(check.ok)
            self.assertTrue(any("does not match" in error for error in check.errors), check.errors)
            self.assertFalse(result.ok)
            self.assertTrue(any("contract" in error for error in result.errors), result.errors)

    def test_command_schema_rejection_is_fail_closed_before_transport(self) -> None:
        adapter, transport = _adapter()

        result = adapter.dispatch_command(
            {
                **_identity(),
                "pipeline_id": "render-network",
                "pipeline_version": "1.0.0",
                "contract_version": "1.1",
                "config": [],
            }
        )

        self.assertFalse(result.ok)
        self.assertEqual(transport.requests, [])
        self.assertTrue(any("contract_version" in error or "config" in error for error in result.errors), result.errors)


if __name__ == "__main__":
    unittest.main()
