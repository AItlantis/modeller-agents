from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modeller.subagents import (
    build_subagent_work_order,
    ingest_subagent_lane_receipt_into_v_cycle_artifacts,
    persist_subagent_lane_receipt,
    validate_subagent_lane_receipt,
    validate_subagent_work_order,
)
from modeller.traceability import build_run_manifest, validate_run_manifest
from modeller.vcycle import (
    check_v_cycle_stage,
    init_v_cycle_run,
    load_v_cycle_state,
    review_v_cycle_stage,
    stage_artifact_digest,
    trace_check_v_cycle,
)
from modeller.workflow import write_task_checkpoint


ROOT = Path(__file__).resolve().parents[1]


class SubagentContractTests(unittest.TestCase):
    def test_builds_valid_v_cycle_work_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-lane", invocation_mode="stage", requested_stage="project-governance")

            work_order = build_subagent_work_order(
                root,
                run_id="run-lane",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )

            check = validate_subagent_work_order(work_order)
            self.assertTrue(check.ok, check.errors)
            self.assertEqual(work_order["workflow_family"], "v-cycle")
            self.assertEqual(work_order["stage_id"], "project-governance")
            self.assertIn("domains/_41_MacroscopicResult/pipelines/rendering_geh", work_order["allowed_paths"])
            self.assertIn(".modeller/runs/run-lane/artifacts", work_order["allowed_paths"])

    def test_work_order_validation_rejects_missing_run_id(self) -> None:
        payload = {
            "schema_version": 1,
            "work_order_id": "wo-test",
            "workflow_family": "v-cycle",
            "stage_id": "project-governance",
            "target_repository": "aimsun-psp",
            "allowed_paths": ["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
            "forbidden_actions": ["workflow advance"],
            "required_artifacts": ["planning-baseline"],
            "required_tests": [],
            "gate_commands": [["python", "-m", "modeller.cli", "workflow", "check", "--run-id", "run"]],
            "expected_result_schema": "schemas/subagent-lane-receipt.schema.json",
        }

        check = validate_subagent_work_order(payload)

        self.assertFalse(check.ok)
        self.assertIn("$.run_id is required", check.errors)

    def test_lane_receipt_accepts_valid_payload(self) -> None:
        work_order = _work_order()
        receipt = _receipt(work_order)

        check = validate_subagent_lane_receipt(work_order, receipt)

        self.assertTrue(check.ok, check.errors)

    def test_lane_receipt_rejects_mismatched_run_and_stage(self) -> None:
        work_order = _work_order()
        receipt = _receipt(work_order, run_id="other-run", stage_id="implementation")

        check = validate_subagent_lane_receipt(work_order, receipt)

        self.assertFalse(check.ok)
        self.assertTrue(any("$.run_id" in error for error in check.errors), check.errors)
        self.assertTrue(any("$.stage_id" in error for error in check.errors), check.errors)

    def test_lane_receipt_rejects_changed_files_outside_allowed_paths(self) -> None:
        work_order = _work_order()
        receipt = _receipt(work_order, files_changed=["domains/_04_Regulation/pipelines/sgfix/sgfix.py"])

        check = validate_subagent_lane_receipt(work_order, receipt)

        self.assertFalse(check.ok)
        self.assertTrue(any("outside allowed_paths" in error for error in check.errors), check.errors)

    def test_lane_receipt_rejects_workflow_advance_and_git_actions(self) -> None:
        work_order = _work_order()
        receipt = _receipt(
            work_order,
            commands_run=[
                ["python", "-m", "modeller.cli", "workflow", "advance", "--run-id", "run-lane"],
                ["git", "commit", "-m", "bad"],
            ],
            attempted_workflow_advance=True,
        )

        check = validate_subagent_lane_receipt(work_order, receipt)

        self.assertFalse(check.ok)
        self.assertTrue(any("attempted_workflow_advance" in error for error in check.errors), check.errors)
        self.assertTrue(any("workflow advance" in error for error in check.errors), check.errors)
        self.assertTrue(any("git commit" in error for error in check.errors), check.errors)

    def test_lane_receipt_rejects_flat_command_array_forbidden_action(self) -> None:
        work_order = _work_order()
        receipt = _receipt(
            work_order,
            commands_run=["python", "-m", "modeller.cli", "workflow", "advance", "--run-id", "run-lane"],
        )

        check = validate_subagent_lane_receipt(work_order, receipt)

        self.assertFalse(check.ok)
        self.assertTrue(any("workflow advance" in error for error in check.errors), check.errors)

    def test_work_order_and_lane_receipt_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-cli-lane", invocation_mode="stage", requested_stage="project-governance")
            work_order_path = root / ".modeller/runs/run-cli-lane/work-order.json"
            receipt_path = root / ".modeller/runs/run-cli-lane/lane-receipt.json"

            create = _run_modeller_cli(
                root,
                "workflow",
                "work-order",
                "--run-id",
                "run-cli-lane",
                "--target-repository",
                "aimsun-psp",
                "--target-path",
                "domains/_41_MacroscopicResult/pipelines/rendering_geh",
                "--task",
                "Create brief and recon evidence.",
                "--agent-id",
                "agent-recon",
                "--output",
                str(work_order_path),
            )
            self.assertEqual(create.returncode, 0, create.stdout + create.stderr)
            work_order = json.loads(work_order_path.read_text(encoding="utf-8"))
            receipt_path.write_text(json.dumps(_receipt(work_order), indent=2) + "\n", encoding="utf-8")

            validate = _run_modeller_cli(
                root,
                "workflow",
                "lane-receipt",
                "--work-order",
                str(work_order_path),
                "--receipt",
                str(receipt_path),
            )

            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            payload = json.loads(validate.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue((root / payload["stored_receipt"]).exists(), payload)
            self.assertTrue((root / payload["stored_work_order"]).exists(), payload)

    def test_persisted_lane_receipt_does_not_advance_v_cycle_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-record-lane", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-record-lane",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            before = load_v_cycle_state(root, "run-record-lane")

            result = persist_subagent_lane_receipt(root, work_order, _receipt(work_order))
            after = load_v_cycle_state(root, "run-record-lane")

            self.assertTrue(result["ok"], result)
            self.assertEqual(after["current_stage_index"], before["current_stage_index"])
            self.assertEqual(after["status"], before["status"])
            self.assertEqual(after["stages"][0]["status"], before["stages"][0]["status"])
            self.assertEqual(after["stages"][0]["review"], before["stages"][0]["review"])
            trace = json.loads((root / ".modeller/runs/run-record-lane/artifacts/v-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["subagent_receipts"][0]["receipt_id"], "lane-test")
            self.assertTrue(trace_check_v_cycle(root, "run-record-lane").ok)

    def test_v_cycle_run_manifest_includes_recorded_lane_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-v-manifest-lane", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-v-manifest-lane",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            record = persist_subagent_lane_receipt(root, work_order, _receipt(work_order))
            self.assertTrue(record["ok"], record)

            manifest = build_run_manifest(root, "run-v-manifest-lane")
            manifest_check = validate_run_manifest(manifest)

            self.assertTrue(manifest_check.ok, manifest_check.errors)
            self.assertEqual(manifest["run"]["workflow_id"], "v-cycle")
            self.assertEqual(manifest["run"]["current_step_id"], "project-governance")
            self.assertEqual(len(manifest["subagents"]), 1)
            self.assertTrue(manifest["subagents"][0]["receipt_ref"].get("sha256"), manifest["subagents"])
            self.assertTrue(manifest["subagents"][0]["work_order_ref"].get("sha256"), manifest["subagents"])

    def test_v_cycle_manifest_all_steps_reports_all_selected_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-v-paired-manifest", invocation_mode="paired-review", requested_stage="functional-specification")

            manifest = build_run_manifest(root, "run-v-paired-manifest")

            self.assertEqual(manifest["run"]["workflow_id"], "v-cycle")
            stage_ids = [item["stage_id"] for item in manifest["gates"]["all_steps"]["stage_results"]]
            self.assertEqual(stage_ids, ["functional-specification", "system-validation"])

    def test_invalid_lane_receipt_is_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-invalid-lane", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-invalid-lane",
                target_repository="aimsun-psp",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            receipt = _receipt(
                work_order,
                files_changed=["domains/_04_Regulation/pipelines/sgfix/sgfix.py"],
            )

            result = persist_subagent_lane_receipt(root, work_order, receipt)

            self.assertFalse(result["ok"], result)
            self.assertFalse((root / ".modeller/runs/run-invalid-lane/subagents").exists())

    def test_lane_receipt_rejects_unsafe_run_or_stage_path_tokens(self) -> None:
        work_order = _work_order()
        work_order["run_id"] = "run/escape"
        receipt = _receipt(work_order)

        check = validate_subagent_lane_receipt(work_order, receipt)

        self.assertFalse(check.ok)
        self.assertTrue(any("$.run_id" in error for error in check.errors), check.errors)

    def test_invalid_v_cycle_stage_receipt_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-bad-stage-lane", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-bad-stage-lane",
                target_repository="aimsun-psp",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            work_order["stage_id"] = "implementation"
            receipt = _receipt(work_order)

            result = persist_subagent_lane_receipt(root, work_order, receipt)

            self.assertFalse(result["ok"], result)
            self.assertFalse((root / ".modeller/runs/run-bad-stage-lane/subagents").exists())

    def test_ingest_lane_receipt_updates_v_cycle_artifacts_without_review_or_advance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-lane", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-lane",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            record = persist_subagent_lane_receipt(root, work_order, _receipt(work_order))
            self.assertTrue(record["ok"], record)
            before = load_v_cycle_state(root, "run-ingest-lane")

            result = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-lane",
                receipt_id="lane-test",
                artifacts=[
                    "brief",
                    "recon",
                    "workflow-plan",
                    "machine-evidence",
                    "handoff",
                    "planning-baseline",
                    "status-report",
                    "risk-register",
                    "decision-log",
                    "document-configuration-log",
                ],
            )
            after = load_v_cycle_state(root, "run-ingest-lane")

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["updated_artifacts"], result)
            self.assertEqual(after["current_stage_index"], before["current_stage_index"])
            self.assertEqual(after["status"], before["status"])
            self.assertEqual(after["stages"][0]["status"], before["stages"][0]["status"])
            self.assertEqual(after["stages"][0]["review"], before["stages"][0]["review"])
            self.assertNotEqual(after["updated_at"], before["updated_at"])
            brief = root / ".modeller/runs/run-ingest-lane/artifacts/BRIEF.md"
            brief_text = brief.read_text(encoding="utf-8")
            self.assertIn("Evidence-source: subagent lane receipt", brief_text)
            self.assertNotIn("TBD", brief_text)
            gate = check_v_cycle_stage(root, "run-ingest-lane", "project-governance")
            self.assertFalse(gate.ok)
            self.assertEqual(gate.errors, ["human review receipt is required before stage advance"])

    def test_ingest_lane_cli_requires_persisted_receipt_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-cli", invocation_mode="stage", requested_stage="project-governance")
            work_order_path = root / ".modeller/runs/run-ingest-cli/work-order.json"
            receipt_path = root / ".modeller/runs/run-ingest-cli/lane-receipt.json"
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-cli",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            work_order_path.write_text(json.dumps(work_order, indent=2) + "\n", encoding="utf-8")
            receipt_path.write_text(json.dumps(_receipt(work_order), indent=2) + "\n", encoding="utf-8")

            raw = _run_modeller_cli(
                root,
                "workflow",
                "ingest-lane-receipt",
                "--run-id",
                "run-ingest-cli",
                "--receipt-id",
                "missing-receipt",
                "--artifact",
                "recon",
            )
            self.assertNotEqual(raw.returncode, 0, raw.stdout + raw.stderr)

            record = _run_modeller_cli(
                root,
                "workflow",
                "lane-receipt",
                "--work-order",
                str(work_order_path),
                "--receipt",
                str(receipt_path),
            )
            self.assertEqual(record.returncode, 0, record.stdout + record.stderr)
            ingest = _run_modeller_cli(
                root,
                "workflow",
                "ingest-lane-receipt",
                "--run-id",
                "run-ingest-cli",
                "--receipt-id",
                "lane-test",
                "--artifact",
                "recon",
            )

            self.assertEqual(ingest.returncode, 0, ingest.stdout + ingest.stderr)
            payload = json.loads(ingest.stdout)
            self.assertTrue(payload["updated_artifacts"], payload)

    def test_ingest_lane_rejects_unknown_artifact_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-unknown", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-unknown",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            record = persist_subagent_lane_receipt(root, work_order, _receipt(work_order))
            self.assertTrue(record["ok"], record)
            before = (root / ".modeller/runs/run-ingest-unknown/artifacts/RECON.md").read_text(encoding="utf-8")

            result = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-unknown",
                receipt_id="lane-test",
                artifacts=["../../escape"],
            )

            self.assertFalse(result["ok"], result)
            after = (root / ".modeller/runs/run-ingest-unknown/artifacts/RECON.md").read_text(encoding="utf-8")
            self.assertEqual(after, before)

    def test_ingest_second_lane_appends_to_existing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-append", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-append",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            first = persist_subagent_lane_receipt(root, work_order, _receipt(work_order, receipt_id="lane-one"))
            second = persist_subagent_lane_receipt(root, work_order, _receipt(work_order, receipt_id="lane-two"))
            self.assertTrue(first["ok"], first)
            self.assertTrue(second["ok"], second)

            first_ingest = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-append",
                receipt_id="lane-one",
                artifacts=["recon"],
            )
            second_ingest = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-append",
                receipt_id="lane-two",
                artifacts=["recon"],
            )

            self.assertTrue(first_ingest["updated_artifacts"], first_ingest)
            self.assertTrue(second_ingest["updated_artifacts"], second_ingest)
            recon = (root / ".modeller/runs/run-ingest-append/artifacts/RECON.md").read_text(encoding="utf-8")
            self.assertIn("Subagent Lane Evidence: lane-one", recon)
            self.assertIn("Subagent Lane Evidence: lane-two", recon)

    def test_ingest_rejects_persisted_receipt_tampered_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-tamper", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-tamper",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            record = persist_subagent_lane_receipt(root, work_order, _receipt(work_order))
            self.assertTrue(record["ok"], record)
            stored = root / record["stored_receipt"]
            payload = json.loads(stored.read_text(encoding="utf-8"))
            payload["output_digest"] = "sha256:" + "4" * 64
            stored.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-tamper",
                receipt_id="lane-test",
                artifacts=["recon"],
            )

            self.assertFalse(result["ok"], result)
            self.assertTrue(any("v-trace" in error for error in result["errors"]), result)

    def test_trace_deduplication_is_stage_scoped_for_reused_receipt_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-stage-dedup", invocation_mode="paired-review", requested_stage="functional-specification")
            work_order_one = build_subagent_work_order(
                root,
                run_id="run-stage-dedup",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create first-stage evidence.",
                agent_id="agent-recon",
            )
            first = persist_subagent_lane_receipt(root, work_order_one, _receipt(work_order_one, receipt_id="lane-same"))
            self.assertTrue(first["ok"], first)
            state["current_stage_index"] = 1
            state["stages"][0]["status"] = "closed"
            state["stages"][1]["status"] = "draft"
            (root / ".modeller/runs/run-stage-dedup/state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            work_order_two = build_subagent_work_order(
                root,
                run_id="run-stage-dedup",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create second-stage evidence.",
                agent_id="agent-recon",
            )
            second = persist_subagent_lane_receipt(root, work_order_two, _receipt(work_order_two, receipt_id="lane-same"))
            self.assertTrue(second["ok"], second)

            trace = json.loads((root / ".modeller/runs/run-stage-dedup/artifacts/v-trace.json").read_text(encoding="utf-8"))
            receipt_keys = {(item["stage_id"], item["receipt_id"]) for item in trace["subagent_receipts"]}

            self.assertIn(("functional-specification", "lane-same"), receipt_keys)
            self.assertIn(("system-validation", "lane-same"), receipt_keys)

    def test_human_review_after_ingestion_uses_new_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-review", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-review",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            record = persist_subagent_lane_receipt(root, work_order, _receipt(work_order))
            self.assertTrue(record["ok"], record)
            ingest = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-review",
                receipt_id="lane-test",
                artifacts=[
                    "brief",
                    "recon",
                    "workflow-plan",
                    "machine-evidence",
                    "handoff",
                    "planning-baseline",
                    "status-report",
                    "risk-register",
                    "decision-log",
                    "document-configuration-log",
                ],
            )
            self.assertTrue(ingest["ok"], ingest)
            state = load_v_cycle_state(root, "run-ingest-review")
            digest = stage_artifact_digest(root, state, state["stages"][0])
            receipt = _write_human_receipt(root, "run-ingest-review", "project-governance", "project-lead", digest)

            review = review_v_cycle_stage(root, "run-ingest-review", receipt)
            gate = check_v_cycle_stage(root, "run-ingest-review", "project-governance")

            self.assertTrue(review["ok"], review)
            self.assertTrue(gate.ok, gate.errors)


    def test_work_order_binds_valid_mission_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-identity", invocation_mode="stage", requested_stage="project-governance")
            mission_identity = {
                "schema_version": 1,
                "project_id": "proj-alpha",
                "mission_id": "mission-001",
                "task_id": "task-001",
                "created_at": "2026-08-08T00:00:00Z",
                "lineage": [],
            }

            work_order = build_subagent_work_order(
                root,
                run_id="run-identity",
                target_repository="aimsun-psp",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
                mission_identity=mission_identity,
            )

            self.assertEqual(work_order["mission_identity"]["mission_id"], "mission-001")
            check = validate_subagent_work_order(work_order)
            self.assertTrue(check.ok, check.errors)

    def test_work_order_rejects_invalid_mission_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-identity-bad", invocation_mode="stage", requested_stage="project-governance")

            with self.assertRaises(ValueError):
                build_subagent_work_order(
                    root,
                    run_id="run-identity-bad",
                    target_repository="aimsun-psp",
                    task="Create brief and recon evidence.",
                    agent_id="agent-recon",
                    mission_identity={"project_id": "not a safe token!"},
                )

    def test_lane_receipt_requires_matching_mission_identity_when_work_order_binds_one(self) -> None:
        work_order = _work_order()
        work_order["mission_identity"] = {
            "schema_version": 1,
            "project_id": "proj-alpha",
            "mission_id": "mission-001",
            "task_id": "task-001",
            "created_at": "2026-08-08T00:00:00Z",
            "lineage": [],
        }
        receipt_missing = _receipt(work_order)
        receipt_mismatched = _receipt(work_order)
        receipt_mismatched["mission_identity"] = {**work_order["mission_identity"], "task_id": "task-999"}
        receipt_matching = _receipt(work_order)
        receipt_matching["mission_identity"] = dict(work_order["mission_identity"])

        missing_check = validate_subagent_lane_receipt(work_order, receipt_missing)
        mismatched_check = validate_subagent_lane_receipt(work_order, receipt_mismatched)
        matching_check = validate_subagent_lane_receipt(work_order, receipt_matching)

        self.assertFalse(missing_check.ok)
        self.assertTrue(any("mission_identity" in error for error in missing_check.errors), missing_check.errors)
        self.assertFalse(mismatched_check.ok)
        self.assertTrue(any("task_id" in error for error in mismatched_check.errors), mismatched_check.errors)
        self.assertTrue(matching_check.ok, matching_check.errors)

    def test_persist_lane_receipt_fails_closed_on_missing_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-lane-cp-missing", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-lane-cp-missing",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            receipt = _receipt(work_order)
            receipt["checkpoint_id"] = "cp-never-written"

            result = persist_subagent_lane_receipt(root, work_order, receipt)

            self.assertFalse(result["ok"], result)
            self.assertTrue(any("checkpoint verification failed" in error for error in result["errors"]), result)
            self.assertFalse((root / ".modeller/runs/run-lane-cp-missing/subagents").exists())

    def test_persist_lane_receipt_succeeds_with_verified_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-lane-cp-ok", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-lane-cp-ok",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            written = write_task_checkpoint(
                root,
                "run-lane-cp-ok",
                task_id="task-001",
                project_id="proj-alpha",
                mission_id="mission-001",
                actor_id="reviewer-1",
                actor_role="developer",
                decision="approved",
            )
            receipt = _receipt(work_order)
            receipt["checkpoint_id"] = written["checkpoint_id"]

            result = persist_subagent_lane_receipt(root, work_order, receipt)

            self.assertTrue(result["ok"], result)

    def test_ingest_lane_receipt_fails_closed_on_stale_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-ingest-cp-stale", invocation_mode="stage", requested_stage="project-governance")
            work_order = build_subagent_work_order(
                root,
                run_id="run-ingest-cp-stale",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                task="Create brief and recon evidence.",
                agent_id="agent-recon",
            )
            written = write_task_checkpoint(
                root,
                "run-ingest-cp-stale",
                task_id="task-001",
                project_id="proj-alpha",
                mission_id="mission-001",
                actor_id="reviewer-1",
                actor_role="developer",
                decision="approved",
            )
            receipt = _receipt(work_order)
            receipt["checkpoint_id"] = written["checkpoint_id"]
            record = persist_subagent_lane_receipt(root, work_order, receipt)
            self.assertTrue(record["ok"], record)
            # Corrupt the persisted checkpoint file itself so re-verification at ingest time
            # fails closed (malformed), simulating a checkpoint that no longer reflects a
            # trustworthy mission/task/authorization binding.
            (root / ".modeller/runs/run-ingest-cp-stale/checkpoints" / f"{written['checkpoint_id']}.json").write_text(
                json.dumps({"mission_identity": {}, "checkpoint_receipt": {}}, indent=2) + "\n",
                encoding="utf-8",
            )

            result = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id="run-ingest-cp-stale",
                receipt_id="lane-test",
                artifacts=["recon"],
            )

            self.assertFalse(result["ok"], result)
            self.assertTrue(any("checkpoint verification failed" in error for error in result["errors"]), result)


def _work_order() -> dict:
    return {
        "schema_version": 1,
        "work_order_id": "wo-test",
        "created_at": "2026-07-15T00:00:00Z",
        "agent_id": "agent-recon",
        "task": "Create brief and recon evidence.",
        "run_id": "run-lane",
        "workflow_family": "v-cycle",
        "stage_id": "project-governance",
        "target_repository": "aimsun-psp",
        "target_path": "domains/_41_MacroscopicResult/pipelines/rendering_geh",
        "allowed_paths": [
            "domains/_41_MacroscopicResult/pipelines/rendering_geh",
            ".modeller/runs/run-lane/artifacts",
        ],
        "forbidden_actions": ["workflow advance", "workflow review", "git commit", "git push", "git reset"],
        "required_artifacts": ["planning-baseline"],
        "required_tests": [],
        "gate_commands": [["python", "-m", "modeller.cli", "workflow", "check", "--run-id", "run-lane"]],
        "expected_result_schema": "schemas/subagent-lane-receipt.schema.json",
    }


def _receipt(
    work_order: dict,
    *,
    receipt_id: str = "lane-test",
    run_id: str | None = None,
    stage_id: str | None = None,
    files_changed: list[str] | None = None,
    commands_run: list[list[str]] | None = None,
    attempted_workflow_advance: bool = False,
) -> dict:
    return {
        "schema_version": 1,
        "receipt_id": receipt_id,
        "work_order_id": work_order["work_order_id"],
        "agent_id": work_order["agent_id"],
        "run_id": run_id or work_order["run_id"],
        "stage_id": stage_id or work_order["stage_id"],
        "files_read": ["domains/_41_MacroscopicResult/pipelines/rendering_geh/README.md"],
        "files_changed": files_changed or [
            "domains/_41_MacroscopicResult/pipelines/rendering_geh/docs/recon.md"
        ],
        "commands_run": commands_run or [["python", "-m", "pytest", "tests"]],
        "tests_run": [],
        "exit_status": "complete",
        "artifact_refs": [".modeller/runs/run-lane/artifacts/RECON.md"],
        "output_digest": "sha256:" + "0" * 64,
        "risks": [],
        "no_git_assertion": True,
        "attempted_workflow_advance": attempted_workflow_advance,
    }


def _write_human_receipt(root: Path, run_id: str, stage_id: str, role: str, digest: str) -> Path:
    receipt = root / f"{run_id}-{stage_id}-receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "review_id": f"review-{run_id}-{stage_id}",
                "run_id": run_id,
                "stage_id": stage_id,
                "artifact_refs": [f".modeller/runs/{run_id}/artifacts/stages/{stage_id}"],
                "artifact_digest": digest,
                "review_type": "approval",
                "reviewer": {"id": "human-reviewer", "role": role, "actor_type": "human"},
                "decision": "approved",
                "reservations": [],
                "accepted_risks": [],
                "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return receipt


def _copy_v_cycle_runtime(tmp: Path) -> Path:
    root = tmp / "repo"
    for rel in [
        "method/workflows",
        "method/policies",
        "method/templates",
        "schemas",
        ".claude/plugins/modeller/skills/v-cycle",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel in [
        "method/workflows/modeller-agents-build.workflow.json",
        "method/workflows/v-cycle.family.yaml",
        "method/workflows/v-cycle.stages.yaml",
        "method/policies/v-cycle-vigilance.yaml",
        "method/templates/workflow-artifact.md",
        "schemas/v-cycle-trace.schema.json",
        "schemas/human-review-receipt.schema.json",
        "schemas/mission-identity.schema.json",
        "schemas/checkpoint-receipt.schema.json",
        ".claude/plugins/modeller/skills/v-cycle/SKILL.md",
    ]:
        (root / rel).write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return root


def _run_modeller_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "modeller.cli", "--root", str(root), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
