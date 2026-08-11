"""Fixture-backed governed Testudo-to-aimsun-psp pipeline trace."""

from __future__ import annotations

import json
import urllib.error
import unittest
from pathlib import Path

from modeller.adapters.testudo_gateway import (
    HttpTestudoTransport,
    TestudoGatewayAdapter,
    TestudoTransportConfig as _TestudoTransportConfig,
    canonical_digest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "testudo_pipeline_fixture.json"
VALID_DIGEST = "sha256:" + "a" * 64


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FixtureTestudoServer:
    """A deterministic Testudo HTTP boundary, not a local provider or DB."""

    def __init__(self, fixture: dict) -> None:
        self.fixture = fixture
        self.requests: list[dict] = []
        self.revoked = False

    def __call__(self, request, timeout: float) -> _Response:
        del timeout
        body = json.loads(request.data.decode("utf-8"))
        self.requests.append({"url": request.full_url, "headers": dict(request.headers), "body": body})
        if self.revoked:
            raise urllib.error.HTTPError(request.full_url, 403, "revoked", {}, None)
        operation = body["operation"]
        key = request.get_header("Idempotency-key")
        return _Response({
            "accepted": True,
            "operation": operation,
            "idempotency_key": key,
            "contract_version": body.get("contract_version", "1.2"),
            "correlation_id": body["correlation_id"],
            "request_digest": canonical_digest({"operation": operation, "payload": body}),
            "identity": {field: body[field] for field in (
                "mission_id", "task_id", "attempt_id", "pipeline_execution_id", "workflow_id", "workflow_run_id"
            ) if field in body},
            "response_identity": {
                "operation": operation, "idempotency_key": key, "correlation_id": body["correlation_id"]
            },
            "workflow_run_id": body.get("workflow_run_id"),
        })


class TestudoPipelineE2ETests(unittest.TestCase):
    def test_governed_pipeline_trace_replays_and_recovers_without_provider_access(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        server = FixtureTestudoServer(fixture)
        config = _TestudoTransportConfig.from_mapping(fixture["testudo"])
        transport = HttpTestudoTransport(config, opener=server)
        adapter = TestudoGatewayAdapter(transport=transport)
        identity = {
            "mission_id": "mission-fixture-001", "task_id": "task-fixture-001",
            "attempt_id": "attempt-fixture-001", "pipeline_execution_id": "pipeline-fixture-001",
            "workflow_run_id": "workflow-fixture-001",
        }
        plan = adapter.dispatch_plan({**identity, "plan": {"pipeline_id": "render-network"}})
        command = adapter.dispatch_command({
            **identity, "approved_plan_ref": "plan-fixture-001", "approved_plan_digest": VALID_DIGEST,
            "baseline_ref": "baseline-fixture-001", "baseline_digest": VALID_DIGEST,
            "pipeline_id": fixture["aimsun_psp"]["pipeline_id"],
            "pipeline_version": fixture["aimsun_psp"]["pipeline_version"],
        })
        receipt = adapter.ingest_receipt({
            **identity, "receipt_id": "receipt-fixture-001", "status": fixture["recovery"]["successful_receipt_status"],
        })
        replay = adapter.dispatch_command({
            **identity, "approved_plan_ref": "plan-fixture-001", "approved_plan_digest": VALID_DIGEST,
            "baseline_ref": "baseline-fixture-001", "baseline_digest": VALID_DIGEST,
            "pipeline_id": "render-network", "pipeline_version": "1.0.0",
        }, idempotency_key=command.idempotency_key)
        self.assertTrue(plan.ok, plan.errors)
        self.assertTrue(command.ok, command.errors)
        self.assertTrue(receipt.ok, receipt.errors)
        self.assertTrue(replay.duplicate)
        self.assertEqual(len(server.requests), 3)
        self.assertTrue(all("ollama" not in json.dumps(item["body"]).lower() for item in server.requests))

        server.revoked = True
        recovery = adapter.ingest_receipt({
            **identity, "receipt_id": "receipt-fixture-002", "status": "recovery_required",
        }, idempotency_key="recovery-fixture-001")
        self.assertFalse(recovery.ok)
        self.assertEqual(recovery.attempts, 1)
        self.assertEqual(len(server.requests), 4)


if __name__ == "__main__":
    unittest.main()
