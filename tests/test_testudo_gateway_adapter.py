"""Contract tests for the dry-run Testudo Gateway adapter seam."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modeller.adapters.testudo_gateway import (
    CanonicalizationError,
    DryRunTransport,
    GatewayIdempotencyPolicy,
    InMemoryGatewayIdempotencyStore,
    TestudoGatewayAdapter,
    activation_preparation_contract_digest,
    activation_preparation_evidence_digest,
    canonical_digest,
    canonical_json,
)


ROOT = Path(__file__).resolve().parents[1]
VECTOR_FIXTURE = ROOT / "tests" / "fixtures" / "testudo_gateway_canonical_vectors.json"
ACTIVATION_FIXTURE = ROOT / "tests" / "fixtures" / "activation_preparation_manifest.json"
ACTIVATION_SCHEMA_FIXTURE = ROOT / "tests" / "fixtures" / "activation_preparation_manifest.schema.json"
VALID_DIGEST = "sha256:" + "a" * 64


def _adapter(
    *,
    transport=None,
    max_retries=0,
    root=ROOT,
    store=None,
    policy=None,
) -> tuple[TestudoGatewayAdapter, DryRunTransport | object]:
    actual_transport = transport or DryRunTransport()
    return (
        TestudoGatewayAdapter(
            root=root,
            transport=actual_transport,
            max_retries=max_retries,
            store=store,
            policy=policy,
        ),
        actual_transport,
    )


def _identity(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "mission_id": "mission-rendering-001",
        "task_id": "task-rendering-001",
        "attempt_id": "attempt-001",
        "pipeline_execution_id": "pipeline-execution-001",
        "workflow_run_id": "workflow-run-001",
    }
    payload.update(overrides)
    return payload


def _evidence(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "approved_plan_ref": "plan-001",
        "approved_plan_digest": VALID_DIGEST,
        "baseline_ref": "baseline-001",
        "baseline_digest": VALID_DIGEST,
    }
    payload.update(overrides)
    return payload


def _command(**overrides: object) -> dict[str, object]:
    payload = {
        **_identity(),
        **_evidence(),
        "pipeline_id": "render-network",
        "pipeline_version": "1.0.0",
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

    def test_canonical_fixture_asserts_every_vector_and_serialization_contract(self) -> None:
        fixture = json.loads(VECTOR_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["contract"]["version"], "testudo-canonical-json-v1")
        self.assertEqual(fixture["contract"]["serialization"], {
            "ensure_ascii": False,
            "sort_keys": True,
            "separators": [",", ":"],
            "encoding": "utf-8",
        })
        for vector in fixture["vectors"]:
            with self.subTest(vector=vector["name"]):
                self.assertEqual(json.loads(canonical_json(vector["input"])), vector["envelope"])
                self.assertEqual(canonical_json(vector["input"]), vector["canonical_json"])
                self.assertEqual(canonical_digest(vector["input"]), vector["digest"])

    def test_typed_digest_rejects_unsupported_identity_values_before_transport(self) -> None:
        class Unsupported:
            pass

        transport = DryRunTransport()
        adapter, _ = _adapter(transport=transport)
        result = adapter.create_mission({**_identity(), "objective": Unsupported()})
        self.assertFalse(result.ok)
        self.assertTrue(any("unsupported identity-bearing value" in error for error in result.errors))
        self.assertEqual(transport.requests, [])
        with self.assertRaises(CanonicalizationError):
            canonical_json(Unsupported())

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
        self.assertEqual(request["pipeline_execution_id"], "pipeline-execution-001")
        self.assertNotIn("workflow_id", request)
        self.assertEqual(request["workflow_run_id"], "workflow-run-001")
        self.assertEqual(request["correlation_id"], "task-correlation-task-rendering-001")
        self.assertEqual(result.correlation_id, adapter.correlation_id("mission-rendering-001", "task-rendering-001"))

    def test_plan_and_receipt_do_not_require_execution_evidence(self) -> None:
        adapter, transport = _adapter()
        plan = adapter.dispatch_plan({**_identity(), "plan": {"stages": ["RM-00", "RM-01"]}})
        receipt = adapter.ingest_receipt({
            **_identity(),
            "receipt_id": "receipt-001",
            "status": "completed",
            "contract_version": "1.2",
        })
        self.assertTrue(plan.ok, plan.errors)
        self.assertTrue(receipt.ok, receipt.errors)
        self.assertEqual(len(transport.requests), 2)

    def test_pipeline_call_projects_notebook_operation_request_without_rewriting_fields(self) -> None:
        adapter, transport = _adapter()
        notebook_request = {
            **_identity(),
            "notebook_session_id": "session-001",
            "cell_id": "cell-001",
            "correlation": {"request_id": "request-001", "source": "geolibre"},
            "payload": {"pipeline_id": "render-network", "inputs": {"scenario": "base"}},
        }

        result = adapter.pipeline_call(notebook_request, idempotency_key="notebook-call-001")

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.operation, "pipeline_call")
        self.assertEqual(len(transport.requests), 1)
        sent = transport.requests[0]["payload"]
        self.assertEqual(sent["operation"], "pipeline_call")
        self.assertEqual(sent["notebook_session_id"], "session-001")
        self.assertEqual(sent["cell_id"], "cell-001")
        self.assertEqual(sent["correlation"], notebook_request["correlation"])
        self.assertEqual(sent["payload"], notebook_request["payload"])
        self.assertEqual(sent["task_id"], notebook_request["task_id"])

    def test_pipeline_call_rejects_incomplete_or_malformed_notebook_request_before_transport(self) -> None:
        transport = DryRunTransport()
        adapter, _ = _adapter(transport=transport)
        for field_name in ("notebook_session_id", "cell_id", "correlation", "payload"):
            with self.subTest(field=field_name):
                candidate = {
                    **_identity(),
                    "notebook_session_id": "session-001",
                    "cell_id": "cell-001",
                    "correlation": {},
                    "payload": {},
                }
                del candidate[field_name]
                result = adapter.pipeline_call(candidate)
                self.assertFalse(result.ok)
                self.assertTrue(any(field_name in error for error in result.errors), result.errors)
        malformed = adapter.pipeline_call({
            **_identity(),
            "notebook_session_id": "session with spaces",
            "cell_id": "cell-001",
            "correlation": [],
            "payload": [],
        })
        self.assertFalse(malformed.ok)
        self.assertTrue(any("safe identity token" in error for error in malformed.errors), malformed.errors)
        self.assertTrue(any("correlation" in error for error in malformed.errors), malformed.errors)
        self.assertTrue(any("payload" in error for error in malformed.errors), malformed.errors)
        self.assertEqual(transport.requests, [])

    def test_pipeline_call_reuses_gateway_idempotency_and_response_contract(self) -> None:
        adapter, transport = _adapter()
        request = {
            **_identity(),
            "notebook_session_id": "session-001",
            "cell_id": "cell-001",
            "correlation": {"request_id": "request-001"},
            "payload": {"pipeline_id": "render-network"},
        }

        first = adapter.pipeline_call(request, idempotency_key="notebook-call-002")
        replay = adapter.pipeline_call(request, idempotency_key="notebook-call-002")
        conflict = adapter.pipeline_call(
            {**request, "payload": {"pipeline_id": "other-pipeline"}},
            idempotency_key="notebook-call-002",
        )

        self.assertTrue(first.ok, first.errors)
        self.assertTrue(replay.duplicate)
        self.assertFalse(conflict.ok)
        self.assertTrue(any("conflicts" in error for error in conflict.errors), conflict.errors)
        self.assertEqual(len(transport.requests), 1)

    def test_execution_identity_projects_pipeline_execution_to_workflow_id(self) -> None:
        adapter, transport = _adapter()
        result = adapter.dispatch_command(_command())
        self.assertTrue(result.ok, result.errors)
        request = transport.requests[0]["payload"]
        self.assertEqual(request["pipeline_execution_id"], "pipeline-execution-001")
        self.assertEqual(request["workflow_id"], "pipeline-execution-001")
        self.assertEqual(request["workflow_run_id"], "workflow-run-001")
        self.assertNotEqual(request["workflow_run_id"], request["pipeline_execution_id"])

        optional_workflow_run = _command()
        del optional_workflow_run["workflow_run_id"]
        optional = adapter.dispatch_command(optional_workflow_run)
        self.assertTrue(optional.ok, optional.errors)
        optional_request = transport.requests[1]["payload"]
        self.assertNotIn("workflow_run_id", optional_request)
        self.assertEqual(optional_request["workflow_id"], optional_request["pipeline_execution_id"])

    def test_execution_identity_rejects_missing_pipeline_and_mismatched_workflow_before_transport(self) -> None:
        for operation, payload in (
            ("plan", {**_identity(), "plan": {"stages": ["RM-00"]}}),
            ("command", _command()),
            ("receipt", {
                **_identity(),
                "receipt_id": "receipt-identity-001",
                "status": "completed",
            }),
        ):
            with self.subTest(case=f"missing pipeline {operation}"):
                transport = DryRunTransport()
                adapter, _ = _adapter(transport=transport)
                candidate = dict(payload)
                del candidate["pipeline_execution_id"]
                result = getattr(adapter, f"dispatch_{operation}")(candidate) if operation != "receipt" else adapter.ingest_receipt(candidate)
                self.assertFalse(result.ok)
                self.assertTrue(any("pipeline_execution_id" in error for error in result.errors), result.errors)
                self.assertEqual(transport.requests, [])

            with self.subTest(case=f"mismatched workflow {operation}"):
                transport = DryRunTransport()
                adapter, _ = _adapter(transport=transport)
                candidate = {**payload, "workflow_id": "workflow-other-001"}
                result = getattr(adapter, f"dispatch_{operation}")(candidate) if operation != "receipt" else adapter.ingest_receipt(candidate)
                self.assertFalse(result.ok)
                self.assertTrue(any("workflow_id" in error for error in result.errors), result.errors)
                self.assertEqual(transport.requests, [])

    def test_execution_identity_changes_fail_closed_after_binding(self) -> None:
        adapter, transport = _adapter()
        first = adapter.dispatch_command(_command())
        changed_pipeline = adapter.dispatch_command(
            _command(pipeline_execution_id="pipeline-execution-002")
        )
        changed_attempt = adapter.dispatch_command(_command(attempt_id="attempt-002"))
        changed_workflow_run = adapter.dispatch_command(_command(workflow_run_id="workflow-run-002"))
        self.assertTrue(first.ok, first.errors)
        self.assertFalse(changed_pipeline.ok)
        self.assertFalse(changed_attempt.ok)
        self.assertFalse(changed_workflow_run.ok)
        self.assertTrue(any("pipeline_execution_id" in error for error in changed_pipeline.errors), changed_pipeline.errors)
        self.assertTrue(any("attempt_id" in error for error in changed_attempt.errors), changed_attempt.errors)
        self.assertTrue(any("workflow_run_id" in error for error in changed_workflow_run.errors), changed_workflow_run.errors)
        self.assertEqual(len(transport.requests), 1)

    def test_execution_evidence_rejects_missing_stale_changed_and_cross_task(self) -> None:
        cases = [
            ("missing", _identity()),
            ("stale", {**_identity(), **_evidence(approved_plan_evidence={"stale": True})}),
            ("changed", {**_identity(), **_evidence(
                approved_plan_evidence={"digest": "sha256:" + "b" * 64}
            )}),
            ("cross-task", {**_identity(), **_evidence(
                baseline_evidence={"task_id": "task-other", "digest": VALID_DIGEST}
            )}),
        ]
        for name, payload in cases:
            with self.subTest(case=name):
                transport = DryRunTransport()
                adapter, _ = _adapter(transport=transport)
                result = adapter.dispatch_command(payload)
                self.assertFalse(result.ok)
                self.assertEqual(transport.requests, [])
                self.assertTrue(any(
                    term in " ".join(result.errors)
                    for term in ("required", "stale", "changed", "different task")
                ), result.errors)

    def test_plan_and_command_dispatch_validate_v12_run_config(self) -> None:
        adapter, transport = _adapter()
        plan = adapter.dispatch_plan({**_identity(), "plan": {"stages": ["RM-00", "RM-01"]}})
        command = adapter.dispatch_command({
            **_command(),
            "contract_version": "1.2",
            "config": {"inputs": {"scenario": "base"}, "params": {}, "metadata": {}},
        })
        self.assertTrue(plan.ok, plan.errors)
        self.assertTrue(command.ok, command.errors)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(plan.correlation_id, command.correlation_id)
        self.assertEqual(transport.requests[1]["payload"]["contract_version"], "1.2")

    def test_retry_same_key_replay_changed_body_and_restart_equivalent_store(self) -> None:
        store = InMemoryGatewayIdempotencyStore()
        transport = DryRunTransport(failures_before_success=1)
        adapter, _ = _adapter(transport=transport, max_retries=1, store=store)
        first = adapter.dispatch_command(_command(), idempotency_key="dispatch-001")
        replay = adapter.dispatch_command(_command(), idempotency_key="dispatch-001")
        conflict = adapter.dispatch_command(
            _command(pipeline_version="2.0.0"), idempotency_key="dispatch-001"
        )
        restarted_transport = DryRunTransport()
        restarted, _ = _adapter(transport=restarted_transport, store=store)
        restarted_replay = restarted.dispatch_command(_command(), idempotency_key="dispatch-001")
        self.assertTrue(first.ok, first.errors)
        self.assertEqual(first.attempts, 2)
        self.assertTrue(replay.duplicate)
        self.assertFalse(conflict.ok)
        self.assertTrue(any("conflicts" in error for error in conflict.errors), conflict.errors)
        self.assertTrue(restarted_replay.duplicate)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(restarted_transport.requests, [])

    def test_canonical_correlation_and_identity_context_remain_stable(self) -> None:
        adapter, _ = _adapter()
        canonical = "task-correlation-task-rendering-001"
        first = adapter.create_mission({**_identity(), "correlation_id": canonical})
        second = adapter.dispatch_plan({**_identity(), "correlation_id": "corr-other-001"})
        receipt = adapter.ingest_receipt({
            **_identity(),
            "receipt_id": "receipt-003",
            "status": "completed",
            "correlation_id": canonical,
            "principal_id": "principal-001",
            "scope": "mission",
        })
        self.assertTrue(first.ok, first.errors)
        self.assertFalse(second.ok)
        self.assertTrue(any("canonical" in error for error in second.errors), second.errors)
        self.assertTrue(receipt.ok, receipt.errors)
        self.assertEqual(receipt.correlation_id, canonical)

    def test_command_and_receipt_require_attempt_id(self) -> None:
        adapter, transport = _adapter()
        missing_attempt = _identity()
        del missing_attempt["attempt_id"]
        plan = adapter.dispatch_plan({**missing_attempt, "plan": {"stages": ["RM-00"]}})
        command = adapter.dispatch_command({**missing_attempt, **_evidence(), "pipeline_id": "render-network"})
        receipt = adapter.ingest_receipt({
            **missing_attempt,
            "receipt_id": "receipt-missing-attempt",
            "status": "completed",
        })
        self.assertFalse(plan.ok)
        self.assertFalse(command.ok)
        self.assertFalse(receipt.ok)
        self.assertTrue(any("attempt_id" in error for error in plan.errors), plan.errors)
        self.assertTrue(any("attempt_id" in error for error in command.errors), command.errors)
        self.assertTrue(any("attempt_id" in error for error in receipt.errors), receipt.errors)
        self.assertEqual(transport.requests, [])

    def test_response_workflow_identity_mismatch_is_rejected_without_ledger_write(self) -> None:
        transport = DryRunTransport(responses={
            "dispatch_command": {
                "identity": {
                    "mission_id": "mission-rendering-001",
                    "task_id": "task-rendering-001",
                    "attempt_id": "attempt-001",
                    "pipeline_execution_id": "pipeline-execution-001",
                    "workflow_id": "workflow-other-001",
                }
            }
        })
        adapter, _ = _adapter(transport=transport)
        result = adapter.dispatch_command(_command(), idempotency_key="workflow-response-001")
        self.assertFalse(result.ok)
        self.assertEqual(adapter.store.records, {})
        self.assertTrue(any("workflow_id" in error for error in result.errors), result.errors)

    def test_malformed_transport_response_fails_closed_and_is_not_cached(self) -> None:
        transport = DryRunTransport(responses={
            "dispatch_command": {
                "accepted": True,
                "contract_version": "1.1",
                "correlation_id": "wrong-correlation",
                "identity": {"task_id": "wrong-task"},
            }
        })
        adapter, _ = _adapter(transport=transport)
        first = adapter.dispatch_command(_command(), idempotency_key="malformed-response-001")
        replay = adapter.dispatch_command(_command(), idempotency_key="malformed-response-001")
        self.assertFalse(first.ok)
        self.assertFalse(replay.ok)
        self.assertFalse(replay.duplicate)
        self.assertEqual(len(transport.requests), 2)
        self.assertTrue(any("contract_version" in error for error in first.errors), first.errors)
        self.assertTrue(any("correlation_id" in error for error in first.errors), first.errors)
        self.assertTrue(any("identity" in error for error in first.errors), first.errors)

    def test_response_identity_mismatch_is_rejected_without_ledger_write(self) -> None:
        transport = DryRunTransport(responses={
            "dispatch_command": {
                "response_identity": {
                    "operation": "dispatch_plan",
                    "idempotency_key": "wrong-key",
                    "correlation_id": "wrong-correlation",
                }
            }
        })
        adapter, _ = _adapter(transport=transport)
        result = adapter.dispatch_command(_command(), idempotency_key="response-mismatch-001")
        self.assertFalse(result.ok)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(adapter.store.records, {})

    def test_stable_idempotency_key_validation_rejects_unsafe_values_before_transport(self) -> None:
        transport = DryRunTransport()
        adapter, _ = _adapter(transport=transport)
        for key in ("bad key", 42):
            with self.subTest(key=key):
                result = adapter.dispatch_command(_command(), idempotency_key=key)
                self.assertFalse(result.ok)
        self.assertEqual(transport.requests, [])

    def test_contract_version_and_schema_rejection_are_before_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            source_vendor = ROOT / "vendor"
            import shutil
            shutil.copytree(source_vendor, root / "vendor")
            (root / "vendor/modeller-pipelines/contracts/VERSION").write_text("1.1\n", encoding="utf-8")
            adapter = TestudoGatewayAdapter(root=root)
            check = adapter.validate_contract()
            result = adapter.create_mission(_identity())
            self.assertFalse(check.ok)
            self.assertFalse(result.ok)
        adapter, transport = _adapter()
        bad = adapter.dispatch_command({
            **_command(),
            "contract_version": "1.1",
            "config": [],
        })
        self.assertFalse(bad.ok)
        self.assertEqual(transport.requests, [])

    def test_retention_policy_defaults_bounds_clock_and_invalid_values(self) -> None:
        policy = GatewayIdempotencyPolicy()
        self.assertEqual(policy.retention_days, 30)
        self.assertEqual(GatewayIdempotencyPolicy(retention_days=0).retention_days, 0)
        self.assertEqual(GatewayIdempotencyPolicy(retention_days=3650).retention_days, 3650)
        for value in (-1, 3651, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    GatewayIdempotencyPolicy(retention_days=value)
        with self.assertRaises(ValueError):
            GatewayIdempotencyPolicy(clock=lambda: datetime(2026, 1, 1))
        injected = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        clock_policy = GatewayIdempotencyPolicy(clock=lambda: injected)
        self.assertEqual(clock_policy.utc_now(), injected)
        self.assertEqual(clock_policy.retention_until(injected), injected + timedelta(days=30))

    def test_expiry_alone_never_reuses_key_and_purge_rollback_preserves_it(self) -> None:
        current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
        policy = GatewayIdempotencyPolicy(clock=lambda: current[0])
        store = InMemoryGatewayIdempotencyStore()
        adapter, transport = _adapter(policy=policy, store=store)
        first = adapter.dispatch_command(_command(), idempotency_key="retention-001")
        current[0] += timedelta(days=30)
        replay = adapter.dispatch_command(_command(), idempotency_key="retention-001")
        store.fail_purge = True
        with self.assertRaises(RuntimeError):
            adapter.purge_expired()
        after_rollback = adapter.dispatch_command(_command(), idempotency_key="retention-001")
        self.assertTrue(first.ok, first.errors)
        self.assertTrue(replay.duplicate)
        self.assertTrue(after_rollback.duplicate)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(len(store.records), 1)

    def test_successful_purge_returns_count_and_allows_post_purge_reuse(self) -> None:
        current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
        policy = GatewayIdempotencyPolicy(retention_days=0, clock=lambda: current[0])
        store = InMemoryGatewayIdempotencyStore()
        first_transport = DryRunTransport()
        adapter, _ = _adapter(policy=policy, store=store, transport=first_transport)
        first = adapter.dispatch_command(_command(), idempotency_key="retention-002")
        self.assertTrue(first.ok, first.errors)
        self.assertEqual(adapter.purge_expired(), 1)
        self.assertEqual(adapter.purge_expired(), 0)
        second_transport = DryRunTransport()
        restarted, _ = _adapter(policy=policy, store=store, transport=second_transport)
        reused = restarted.dispatch_command(_command(), idempotency_key="retention-002")
        self.assertTrue(reused.ok, reused.errors)
        self.assertFalse(reused.duplicate)
        self.assertEqual(len(second_transport.requests), 1)

    def test_activation_preparation_fixture_is_strict_and_zero_call(self) -> None:
        manifest = json.loads(ACTIVATION_FIXTURE.read_text(encoding="utf-8"))
        schema = json.loads(ACTIVATION_SCHEMA_FIXTURE.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["zero_call_assertions"]["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(manifest))
        self.assertEqual(manifest["contract_digest"], activation_preparation_contract_digest())
        self.assertEqual(manifest["evidence_digest"], activation_preparation_evidence_digest(manifest))

        class ExplodingTransport:
            def send(self, operation, payload, idempotency_key):
                raise AssertionError(f"activation preparation called transport: {operation}")

        adapter, _ = _adapter(transport=ExplodingTransport())
        validation = adapter.validate_activation_preparation(manifest)
        self.assertTrue(validation.ok, validation.errors)
        self.assertEqual(validation.zero_call_assertions, {"network_calls": 0, "transport_calls": 0})
        self.assertEqual(adapter.validate_activation_preparation_manifest(manifest).to_dict(), validation.to_dict())

    def test_activation_preparation_rejects_unsafe_or_mismatched_cases_before_transport(self) -> None:
        accepted = json.loads(ACTIVATION_FIXTURE.read_text(encoding="utf-8"))
        cases = {
            "activation": {"activation": True},
            "network": {"network_calls_allowed": True},
            "transport": {"transport_calls_allowed": True},
            "production credentials": {"credential_source": "production_secret"},
            "owner placeholder": {"activation_owner": "TBD"},
            "abort placeholder": {"abort_authority": "placeholder"},
            "canary placeholder": {"canary_stop_criteria": ["TODO"]},
            "rollback placeholder": {"rollback_steps": ["replace-me"]},
            "contract digest mismatch": {"contract_digest": "sha256:" + "b" * 64},
            "evidence digest mismatch": {"evidence_digest": "sha256:" + "c" * 64},
            "unknown property": {"unexpected": True},
            "nonzero call assertion": {"zero_call_assertions": {"network_calls": 1, "transport_calls": 0}},
        }
        for name, changes in cases.items():
            with self.subTest(case=name):
                transport = DryRunTransport()
                adapter, _ = _adapter(transport=transport)
                candidate = {**accepted, **changes}
                result = adapter.validate_activation_preparation(candidate)
                self.assertFalse(result.ok, result.errors)
                self.assertEqual(transport.requests, [])

    def test_activation_preparation_digest_helpers_are_typed_lowercase_sha256(self) -> None:
        manifest = json.loads(ACTIVATION_FIXTURE.read_text(encoding="utf-8"))
        for digest in (manifest["contract_digest"], manifest["evidence_digest"]):
            self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        changed = {**manifest, "contract_version": "1.1"}
        self.assertNotEqual(
            activation_preparation_contract_digest("aimsun-psp", "1.1"),
            manifest["contract_digest"],
        )
        self.assertNotEqual(activation_preparation_evidence_digest(changed), manifest["evidence_digest"])


if __name__ == "__main__":
    unittest.main()
