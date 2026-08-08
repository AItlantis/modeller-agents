from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from modeller.contracts import CapabilityGrant, validate_dispatch_identity_binding, validate_dispatch_request
from modeller.orchestrator import build_chat_handoff_prompt, orchestrate_prompt
from modeller.subagents import build_subagent_work_order, persist_subagent_lane_receipt, validate_subagent_lane_receipt
from modeller.vcycle import (
    advance_v_cycle,
    apply_human_review_provider,
    check_v_cycle_current_stage,
    load_v_cycle_state,
)


ROOT = Path(__file__).resolve().parents[1]


class OrchestratorTests(unittest.TestCase):
    def test_natural_brief_recon_initializes_v_cycle_and_writes_work_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            payload = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp domains/_41_MacroscopicResult/pipelines/rendering_geh.",
                target_repository="aimsun-psp",
                run_id="rendering-geh-orchestrate",
                agent_id="recon-agent",
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["status"], "awaiting-user-approval")
            self.assertEqual(payload["run_id"], "rendering-geh-orchestrate")
            self.assertEqual(payload["intent"]["requested_capability"], "v-cycle")
            self.assertEqual(payload["intent"]["v_cycle_stage"], "project-governance")
            self.assertTrue((root / payload["envelope_path"]).exists(), payload)
            self.assertTrue((root / payload["work_order_path"]).exists(), payload)
            self.assertEqual(payload["route"]["run_id"], "rendering-geh-orchestrate")
            self.assertEqual(payload["work_order"]["stage_id"], "project-governance")
            self.assertIn("brief", payload["work_order"]["required_artifacts"])
            self.assertIn("recon", payload["work_order"]["required_artifacts"])
            self.assertIn(
                "domains/_41_MacroscopicResult/pipelines/rendering_geh",
                payload["work_order"]["allowed_paths"],
            )
            self.assertFalse(payload["current_gate"]["ok"])
            self.assertTrue(any("human review receipt" in error for error in payload["current_gate"]["errors"]))

    def test_orchestrate_cli_binds_prompt_without_manual_plan_init_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            result = _run_modeller_cli(
                root,
                "orchestrate",
                "--prompt",
                "Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                "--target-repository",
                "aimsun-psp",
                "--run-id",
                "cli-orchestrate",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["route"]["skill"], "v-cycle")
            self.assertTrue((root / ".modeller/runs/cli-orchestrate/state.json").exists())
            self.assertTrue((root / payload["work_order_path"]).exists(), payload)

    def test_orchestrate_cli_writes_chat_handoff_for_interactive_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            result = _run_modeller_cli(
                root,
                "orchestrate",
                "--prompt",
                "Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                "--target-repository",
                "aimsun-psp",
                "--run-id",
                "chat-handoff-run",
                "--chat-output",
                ".modeller/runs/chat-handoff-run/chat-handoff.md",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["chat_handoff_path"], ".modeller/runs/chat-handoff-run/chat-handoff.md")
            handoff = (root / payload["chat_handoff_path"]).read_text(encoding="utf-8")
            self.assertIn("Use the `modeller:orchestrator` agent behavior", handoff)
            self.assertIn("Create a brief.md and recon.md", handoff)
            self.assertIn("run_id: chat-handoff-run", handoff)
            self.assertIn("context_envelope:", handoff)
            self.assertIn("subagent_work_order:", handoff)
            self.assertIn("Wait for explicit human approval", handoff)

    def test_launch_chat_json_reports_command_without_executing_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            result = _run_modeller_cli(
                root,
                "orchestrate",
                "--prompt",
                "Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                "--target-repository",
                "aimsun-psp",
                "--run-id",
                "launch-chat-json",
                "--launch-chat",
                "codex",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["chat_handoff_path"], ".modeller/runs/launch-chat-json/chat-handoff.md")
            self.assertTrue(Path(payload["chat_launch_command"][0]).name.lower().startswith("codex"))
            self.assertIn("chat-handoff.md", payload["chat_launch_command"][1])
            self.assertEqual(payload["chat_cwd"], str(root.resolve()))
            self.assertTrue((root / payload["chat_handoff_path"]).exists())

    def test_cli_chat_handoff_from_runtime_host_targets_sibling_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp), root_name="aimsun-psp")
            knowledge = Path(tmp) / "AItlantis" / "modelling-knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / ".git").mkdir()
            (knowledge / "README.md").write_text("# modelling knowledge\n", encoding="utf-8")

            result = _run_modeller_cli(
                root,
                "orchestrate",
                "--prompt",
                "analyse the structure of the memory within the obsidian vault",
                "--target-repository",
                "modelling-knowledge",
                "--run-id",
                "knowledge-analysis",
                "--chat-output",
                ".modeller/chat-handoffs/knowledge-analysis.md",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["intent"]["requested_capability"], "review")
            self.assertEqual(payload["chat_cwd"], str(knowledge.resolve()))
            self.assertIsNone(payload["work_order"])
            handoff = (root / payload["chat_handoff_path"]).read_text(encoding="utf-8")
            self.assertIn(f"source_root: {knowledge.resolve()}", handoff)
            self.assertIn("allowed_runtime_root:", handoff)
            self.assertIn("Treat this as read-only", handoff)
            self.assertNotIn("subagent work order", handoff)

    def test_chat_handoff_prompt_contains_gate_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            payload = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="chat-prompt-run",
            )

            handoff = build_chat_handoff_prompt(root, payload)

            self.assertIn("# modeller orchestrator handoff", handoff)
            self.assertIn("stage_id: project-governance", handoff)
            self.assertIn("human review receipt is required", handoff)
            self.assertIn("python -m modeller.cli workflow", handoff)

    def test_orchestrate_reuses_existing_run_without_resetting_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            first = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="reuse-run",
            )
            created_at = first["workflow_state"]["created_at"]

            second = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="reuse-run",
            )

            self.assertTrue(second["ok"], second)
            self.assertEqual(second["workflow_state"]["created_at"], created_at)

    def test_orchestrate_blocks_existing_run_stage_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Refactor aimsun-psp code and update tests",
                target_repository="aimsun-psp",
                run_id="mismatch-run",
            )
            self.assertTrue(setup["ok"], setup)
            envelope_before = (root / setup["envelope_path"]).read_text(encoding="utf-8")

            payload = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="mismatch-run",
            )

            self.assertFalse(payload["ok"], payload)
            self.assertTrue(any("does not match requested stage" in error for error in payload["errors"]), payload)
            self.assertEqual((root / setup["envelope_path"]).read_text(encoding="utf-8"), envelope_before)

    def test_docs_lookup_orchestrate_routes_read_only_without_workflow_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            payload = orchestrate_prompt(
                root,
                prompt="Find docs for testudo source boundary; do not edit files",
                target_repository="testudo",
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["intent"]["requested_capability"], "review")
            self.assertIsNone(payload["run_id"])
            self.assertIsNone(payload["work_order"])
            self.assertFalse((root / ".modeller").exists())

    def test_analysis_prompt_routes_read_only_review_for_modelling_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp), root_name="aimsun-psp")
            knowledge = Path(tmp) / "AItlantis" / "modelling-knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / ".git").mkdir()
            (knowledge / "README.md").write_text("# modelling knowledge\n", encoding="utf-8")

            payload = orchestrate_prompt(
                root,
                prompt="analyse the structure of the memory within the obsidian vault",
                target_repository="modelling-knowledge",
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["intent"]["requested_capability"], "review")
            self.assertEqual(payload["intent"]["requires_workflow"], False)
            self.assertEqual(payload["plan"]["alignment_contract"]["source_root"], str(knowledge.resolve()))
            self.assertIsNone(payload["work_order"])
            self.assertFalse((root / ".modeller").exists())

    def test_target_path_override_is_reported_and_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            payload = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about rendering_geh pipeline",
                target_repository="aimsun-psp",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                run_id="target-path-run",
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(
                payload["intent"]["target_path"],
                "domains/_41_MacroscopicResult/pipelines/rendering_geh",
            )
            envelope = json.loads((root / payload["envelope_path"]).read_text(encoding="utf-8"))
            self.assertEqual(
                envelope["intent"]["target_path"],
                "domains/_41_MacroscopicResult/pipelines/rendering_geh",
            )
            self.assertEqual(
                payload["work_order"]["target_path"],
                "domains/_41_MacroscopicResult/pipelines/rendering_geh",
            )

    def test_unsafe_target_path_blocks_before_writing_work_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            payload = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about rendering_geh pipeline",
                target_repository="aimsun-psp",
                target_path="C:\\Users\\public\\outside",
                run_id="unsafe-target-path",
            )

            self.assertFalse(payload["ok"], payload)
            self.assertTrue(any("safe relative path" in error for error in payload["errors"]), payload)
            self.assertFalse((root / ".modeller/runs/unsafe-target-path/state.json").exists())
            self.assertFalse((root / ".modeller/runs/unsafe-target-path/work-orders").exists())

    def test_fixture_e2e_advances_all_selected_stages_with_human_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            first_setup = orchestrate_prompt(
                root,
                prompt="Create a functional specification for aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="paired-fixture-e2e",
                agent_id="spec-agent",
                invocation_mode="paired-review",
            )
            self.assertTrue(first_setup["ok"], first_setup)
            self.assertEqual(
                first_setup["workflow_state"]["selected_stages"],
                ["functional-specification", "system-validation"],
            )
            first_lane = persist_subagent_lane_receipt(
                root,
                first_setup["work_order"],
                _lane_receipt(first_setup["work_order"], receipt_id="lane-functional-specification"),
            )
            self.assertTrue(first_lane["ok"], first_lane)

            first_review = _complete_current_stage_and_fixture_review(root, "paired-fixture-e2e")
            first_gate = check_v_cycle_current_stage(root, "paired-fixture-e2e")
            first_advance = advance_v_cycle(root, "paired-fixture-e2e")
            after_first = load_v_cycle_state(root, "paired-fixture-e2e")
            second_setup = orchestrate_prompt(
                root,
                prompt="Validate behavior for aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="paired-fixture-e2e",
                agent_id="validation-agent",
            )
            self.assertTrue(second_setup["ok"], second_setup)
            second_lane = persist_subagent_lane_receipt(
                root,
                second_setup["work_order"],
                _lane_receipt(second_setup["work_order"], receipt_id="lane-system-validation"),
            )
            self.assertTrue(second_lane["ok"], second_lane)
            second_review = _complete_current_stage_and_fixture_review(root, "paired-fixture-e2e")
            second_gate = check_v_cycle_current_stage(root, "paired-fixture-e2e")
            second_advance = advance_v_cycle(root, "paired-fixture-e2e")
            final_state = load_v_cycle_state(root, "paired-fixture-e2e")

            self.assertTrue(first_review["ok"], first_review)
            self.assertTrue(first_gate.ok, first_gate.errors)
            self.assertTrue(first_advance.ok, first_advance.errors)
            self.assertEqual(after_first["current_stage_index"], 1)
            self.assertEqual(after_first["stages"][0]["status"], "closed")
            self.assertEqual(after_first["stages"][1]["id"], "system-validation")
            self.assertEqual(after_first["stages"][1]["status"], "draft")
            self.assertTrue(second_review["ok"], second_review)
            self.assertTrue(second_gate.ok, second_gate.errors)
            self.assertTrue(second_advance.ok, second_advance.errors)
            self.assertEqual(final_state["status"], "complete")
            self.assertEqual([stage["status"] for stage in final_state["stages"]], ["closed", "closed"])

    def test_orchestrated_stage_cannot_advance_without_lane_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="no-lane-advance",
            )
            self.assertTrue(setup["ok"], setup)

            review = _complete_current_stage_and_fixture_review(root, "no-lane-advance")
            gate = check_v_cycle_current_stage(root, "no-lane-advance")
            advance = advance_v_cycle(root, "no-lane-advance")

            self.assertTrue(review["ok"], review)
            self.assertFalse(gate.ok)
            self.assertTrue(any("subagent lane receipt" in error for error in gate.errors), gate.errors)
            self.assertFalse(advance.ok)
            self.assertTrue(any("subagent lane receipt" in error for error in advance.errors), advance.errors)

    def test_forged_trace_receipt_does_not_satisfy_lane_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="forged-lane-trace",
            )
            self.assertTrue(setup["ok"], setup)
            trace_path = root / setup["workflow_state"]["artifact_root"] / "v-trace.json"
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            trace["subagent_receipts"].append(
                {
                    "receipt_id": "fake",
                    "work_order_id": setup["work_order"]["work_order_id"],
                    "stage_id": "project-governance",
                    "agent_id": setup["work_order"]["agent_id"],
                    "exit_status": "complete",
                    "output_digest": "sha256:" + "2" * 64,
                    "receipt_ref": ".modeller/runs/forged-lane-trace/subagents/project-governance/fake.json",
                    "work_order_ref": ".modeller/runs/forged-lane-trace/subagents/project-governance/fake.work-order.json",
                    "receipt_sha256": "sha256:" + "3" * 64,
                    "work_order_sha256": "sha256:" + "4" * 64,
                }
            )
            trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
            review = _complete_current_stage_and_fixture_review(root, "forged-lane-trace")

            gate = check_v_cycle_current_stage(root, "forged-lane-trace")
            advance = advance_v_cycle(root, "forged-lane-trace")

            self.assertTrue(review["ok"], review)
            self.assertFalse(gate.ok)
            self.assertTrue(any("subagent lane receipt" in error for error in gate.errors), gate.errors)
            self.assertFalse(advance.ok)

    def test_human_review_rejects_subagent_self_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="self-review-run",
                agent_id="project-lead",
            )
            self.assertTrue(setup["ok"], setup)
            lane = persist_subagent_lane_receipt(root, setup["work_order"], _lane_receipt(setup["work_order"]))
            self.assertTrue(lane["ok"], lane)
            _complete_generated_markdown(root / setup["workflow_state"]["artifact_root"])
            metadata = _write_fixture_metadata(root, "self-review-run", "project-governance")

            review = apply_human_review_provider(
                root,
                "self-review-run",
                provider="test-fixture",
                fixture_metadata_path=metadata,
                reviewer_id="project-lead",
                reviewer_role="project-lead",
                allow_test_fixture=True,
            )

            self.assertFalse(review["ok"], review)
            self.assertTrue(any("must not match" in error for error in review["errors"]), review)

    def test_later_stage_cannot_complete_if_closed_stage_material_artifact_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            first_setup = orchestrate_prompt(
                root,
                prompt="Create a functional specification for aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="stale-closed-stage",
                invocation_mode="paired-review",
            )
            self.assertTrue(first_setup["ok"], first_setup)
            first_lane = persist_subagent_lane_receipt(
                root,
                first_setup["work_order"],
                _lane_receipt(first_setup["work_order"], receipt_id="lane-first-stale"),
            )
            self.assertTrue(first_lane["ok"], first_lane)
            first_review = _complete_current_stage_and_fixture_review(root, "stale-closed-stage")
            first_advance = advance_v_cycle(root, "stale-closed-stage")
            self.assertTrue(first_review["ok"], first_review)
            self.assertTrue(first_advance.ok, first_advance.errors)
            state = load_v_cycle_state(root, "stale-closed-stage")
            brief = root / state["artifact_root"] / "BRIEF.md"
            brief.write_text(brief.read_text(encoding="utf-8") + "\nmaterial change after first review\n", encoding="utf-8")
            second_setup = orchestrate_prompt(
                root,
                prompt="Validate behavior for aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="stale-closed-stage",
                agent_id="validation-agent",
            )
            self.assertTrue(second_setup["ok"], second_setup)
            second_lane = persist_subagent_lane_receipt(
                root,
                second_setup["work_order"],
                _lane_receipt(second_setup["work_order"], receipt_id="lane-second-stale"),
            )
            self.assertTrue(second_lane["ok"], second_lane)
            second_review = _complete_current_stage_and_fixture_review(root, "stale-closed-stage")

            second_advance = advance_v_cycle(root, "stale-closed-stage")

            self.assertTrue(second_review["ok"], second_review)
            self.assertFalse(second_advance.ok)
            self.assertTrue(any("closed stage" in error for error in second_advance.errors), second_advance.errors)

    def test_ambiguous_prompt_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            payload = orchestrate_prompt(
                root,
                prompt="Find docs and deploy aimsun-psp",
                target_repository="aimsun-psp",
            )

            self.assertFalse(payload["ok"], payload)
            self.assertTrue(any("ambiguous natural-language intent" in error for error in payload["errors"]), payload)

    def test_orchestrate_does_not_review_or_advance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))

            payload = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="no-advance-run",
            )

            self.assertTrue(payload["ok"], payload)
            state = json.loads((root / ".modeller/runs/no-advance-run/state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current_stage_index"], 0)
            self.assertEqual(state["stages"][0]["status"], "draft")
            self.assertEqual(state["stages"][0]["review"]["status"], "missing")


class CapabilityGrantDispatchTests(unittest.TestCase):
    """FR-003 mission-scoped capability grants, FR-004 hard identity binding,

    SEC-001 least privilege, SEC-003 path containment. These consume the
    generic dispatch validators in modeller.contracts and their wiring into
    modeller.subagents' work-order/receipt lane -- not a new pipeline
    capability-profile schema.
    """

    def test_dispatch_request_within_grant_is_accepted(self) -> None:
        grant = CapabilityGrant(
            role="build-worker",
            allowed_tools=["Read", "Edit", "Bash"],
            allowed_paths=["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
            forbidden_commands=["git commit", "git push"],
            write_scope=["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
        ).to_dict()
        request = {
            "role": "build-worker",
            "tools": ["Read", "Edit"],
            "paths": ["domains/_41_MacroscopicResult/pipelines/rendering_geh/step.py"],
            "commands": [["python", "-m", "pytest", "tests"]],
            "write_scope": ["domains/_41_MacroscopicResult/pipelines/rendering_geh/step.py"],
        }

        result = validate_dispatch_request(grant, request)

        self.assertTrue(result.ok, result.errors)

    def test_dispatch_request_rejects_tool_path_and_write_scope_overreach(self) -> None:
        grant = CapabilityGrant(
            role="build-worker",
            allowed_tools=["Read", "Edit"],
            allowed_paths=["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
            forbidden_commands=["git push"],
            write_scope=["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
        ).to_dict()
        request = {
            "role": "build-worker",
            "tools": ["Read", "Bash"],
            "paths": ["domains/_99_Other/pipelines/unrelated/file.py"],
            "commands": [["git", "push", "origin", "main"]],
            "write_scope": ["domains/_99_Other/pipelines/unrelated/file.py"],
        }

        result = validate_dispatch_request(grant, request)

        self.assertFalse(result.ok)
        self.assertTrue(any("ungranted tool" in error for error in result.errors), result.errors)
        self.assertTrue(any("outside granted allowed_paths" in error for error in result.errors), result.errors)
        self.assertTrue(any("forbidden command" in error for error in result.errors), result.errors)
        self.assertTrue(any("exceeds granted write_scope" in error for error in result.errors), result.errors)
        self.assertTrue(result.remediation, result.remediation)

    def test_dispatch_request_rejects_role_mismatch(self) -> None:
        grant = CapabilityGrant(role="build-worker").to_dict()
        request = {"role": "reviewer", "tools": [], "paths": [], "commands": [], "write_scope": []}

        result = validate_dispatch_request(grant, request)

        self.assertFalse(result.ok)
        self.assertTrue(any("does not match granted role" in error for error in result.errors), result.errors)

    def test_dispatch_request_rejects_unsafe_and_traversal_paths(self) -> None:
        grant = CapabilityGrant(
            role="build-worker",
            allowed_paths=["domains/_41_MacroscopicResult"],
            write_scope=["domains/_41_MacroscopicResult"],
        ).to_dict()
        request = {
            "role": "build-worker",
            "tools": [],
            "paths": ["../../etc/passwd", "C:\\Windows\\System32"],
            "commands": [],
            "write_scope": ["domains/_41_MacroscopicResult/../../outside.txt"],
        }

        result = validate_dispatch_request(grant, request)

        self.assertFalse(result.ok)
        self.assertTrue(any("$.paths contains unsafe path" in error for error in result.errors), result.errors)
        self.assertTrue(any("$.write_scope contains unsafe path" in error for error in result.errors), result.errors)

    def test_dispatch_identity_binding_accepts_matching_receipt(self) -> None:
        request = {
            "role": "build-worker",
            "agent_id": "build-agent-1",
            "provider": "codex",
            "request_digest": "wo-abc123",
        }
        receipt = {
            "role": "build-worker",
            "agent_id": "build-agent-1",
            "provider": "codex",
            "request_digest": "wo-abc123",
        }

        result = validate_dispatch_identity_binding(request, receipt)

        self.assertTrue(result.ok, result.errors)

    def test_dispatch_identity_binding_rejects_role_agent_provider_or_digest_spoof(self) -> None:
        request = {
            "role": "build-worker",
            "agent_id": "build-agent-1",
            "provider": "codex",
            "request_digest": "wo-abc123",
        }
        spoofed_role = dict(request, role="reviewer")
        spoofed_agent = dict(request, agent_id="a-different-agent")
        spoofed_provider = dict(request, provider="claude")
        spoofed_digest = dict(request, request_digest="wo-forged999")

        role_result = validate_dispatch_identity_binding(request, spoofed_role)
        agent_result = validate_dispatch_identity_binding(request, spoofed_agent)
        provider_result = validate_dispatch_identity_binding(request, spoofed_provider)
        digest_result = validate_dispatch_identity_binding(request, spoofed_digest)

        self.assertFalse(role_result.ok)
        self.assertTrue(any("$.role" in error for error in role_result.errors), role_result.errors)
        self.assertFalse(agent_result.ok)
        self.assertTrue(any("$.agent_id" in error for error in agent_result.errors), agent_result.errors)
        self.assertFalse(provider_result.ok)
        self.assertTrue(any("$.provider" in error for error in provider_result.errors), provider_result.errors)
        self.assertFalse(digest_result.ok)
        self.assertTrue(any("request_digest" in error for error in digest_result.errors), digest_result.errors)

    def test_build_subagent_work_order_rejects_capability_overreach_before_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="grant-overreach-run",
            )
            self.assertTrue(setup["ok"], setup)
            grant = CapabilityGrant(
                role="build-worker",
                allowed_tools=["Read"],
                allowed_paths=["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
                write_scope=["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
            ).to_dict()

            with self.assertRaises(ValueError) as ctx:
                build_subagent_work_order(
                    root,
                    run_id="grant-overreach-run",
                    target_repository="aimsun-psp",
                    task="attempt overreaching dispatch",
                    agent_id="build-agent-1",
                    target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                    capability_grant=grant,
                    role="build-worker",
                    provider="codex",
                    tools=["Read", "Bash"],
                )

            self.assertIn("ungranted tool", str(ctx.exception))
            self.assertFalse((root / ".modeller/runs/grant-overreach-run/subagents").exists())

    def test_build_subagent_work_order_binds_capability_grant_when_within_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="grant-ok-run",
            )
            self.assertTrue(setup["ok"], setup)
            grant = CapabilityGrant(
                role="build-worker",
                allowed_tools=["Read", "Edit"],
                allowed_paths=list(setup["work_order"]["allowed_paths"])
                + ["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
                write_scope=list(setup["work_order"]["allowed_paths"])
                + ["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
            ).to_dict()

            work_order = build_subagent_work_order(
                root,
                run_id="grant-ok-run",
                target_repository="aimsun-psp",
                task="dispatch within bounds",
                agent_id="build-agent-1",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                capability_grant=grant,
                role="build-worker",
                provider="codex",
                tools=["Read", "Edit"],
            )

            self.assertEqual(work_order["role"], "build-worker")
            self.assertEqual(work_order["provider"], "codex")
            self.assertEqual(work_order["capability_grant"], grant)
            self.assertEqual(work_order["dispatch_request"]["request_digest"], work_order["work_order_id"])

    def test_lane_receipt_with_spoofed_identity_is_rejected_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_runtime(Path(tmp))
            setup = orchestrate_prompt(
                root,
                prompt="Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                target_repository="aimsun-psp",
                run_id="identity-spoof-run",
            )
            self.assertTrue(setup["ok"], setup)
            grant = CapabilityGrant(
                role="build-worker",
                allowed_tools=["Read", "Edit"],
                allowed_paths=list(setup["work_order"]["allowed_paths"])
                + ["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
                write_scope=list(setup["work_order"]["allowed_paths"])
                + ["domains/_41_MacroscopicResult/pipelines/rendering_geh"],
            ).to_dict()
            work_order = build_subagent_work_order(
                root,
                run_id="identity-spoof-run",
                target_repository="aimsun-psp",
                task="dispatch bound to a mission-scoped grant",
                agent_id="build-agent-1",
                target_path="domains/_41_MacroscopicResult/pipelines/rendering_geh",
                capability_grant=grant,
                role="build-worker",
                provider="codex",
                tools=["Read", "Edit"],
            )
            receipt = _lane_receipt(work_order)
            receipt["agent_id"] = "impersonating-agent"
            receipt["role"] = "build-worker"
            receipt["provider"] = "codex"
            receipt["request_digest"] = work_order["work_order_id"]

            check = validate_subagent_lane_receipt(work_order, receipt)

            self.assertFalse(check.ok)
            self.assertTrue(any("agent_id" in error for error in check.errors), check.errors)


def _copy_runtime(tmp: Path, *, root_name: str = "repo") -> Path:
    root = tmp / root_name
    for rel in [
        "method/workflows",
        "method/policies",
        "method/templates",
        "schemas",
        "bundles",
        "reference-packs",
        ".claude/plugins/modeller/skills/v-cycle",
        ".claude/plugins/modeller/skills/workflow",
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
        "schemas/subagent-work-order.schema.json",
        "schemas/subagent-lane-receipt.schema.json",
        "bundles/aimsun-psp.bundle.json",
        "bundles/modelling-knowledge.bundle.json",
        "bundles/testudo.bundle.json",
        "reference-packs/aimsun-psp.toml",
        "reference-packs/modelling-knowledge.toml",
        "reference-packs/modeller-pipelines.toml",
        "reference-packs/testudo.toml",
        ".claude/plugins/modeller/skills/v-cycle/SKILL.md",
    ]:
        (root / rel).write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    (root / ".claude/plugins/modeller/skills/workflow/SKILL.md").write_text("# workflow\n", encoding="utf-8")
    return root


def _complete_current_stage_and_fixture_review(root: Path, run_id: str) -> dict:
    state = load_v_cycle_state(root, run_id)
    stage = state["stages"][int(state["current_stage_index"])]
    _complete_generated_markdown(root / state["artifact_root"])
    metadata = _write_fixture_metadata(root, run_id, str(stage["id"]))
    return apply_human_review_provider(
        root,
        run_id,
        provider="test-fixture",
        fixture_metadata_path=metadata,
        reviewer_id=f"fixture-{stage['id']}",
        reviewer_role=stage["human_owner_roles"][0],
        allow_test_fixture=True,
    )


def _write_fixture_metadata(root: Path, run_id: str, stage_id: str) -> Path:
    metadata = root / ".modeller" / "runs" / run_id / f"fixture-{stage_id}.json"
    metadata.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "stage_id": stage_id,
                "provider": "test-fixture",
                "fixture_run": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return metadata


def _lane_receipt(work_order: dict, *, receipt_id: str = "lane-test") -> dict:
    stage_id = str(work_order["stage_id"])
    run_id = str(work_order["run_id"])
    return {
        "schema_version": 1,
        "receipt_id": receipt_id,
        "work_order_id": work_order["work_order_id"],
        "agent_id": work_order["agent_id"],
        "run_id": run_id,
        "stage_id": stage_id,
        "files_read": [".modeller/runs/" + run_id + "/artifacts/workflow-plan.md"],
        "files_changed": [".modeller/runs/" + run_id + f"/artifacts/stages/{stage_id}/{work_order['required_artifacts'][0]}.md"],
        "commands_run": [["python", "-m", "pytest", "tests"]],
        "tests_run": [{"command": "python -m pytest tests", "status": "passed"}],
        "exit_status": "complete",
        "artifact_refs": [".modeller/runs/" + run_id + "/artifacts"],
        "output_digest": "sha256:" + "1" * 64,
        "risks": [],
        "no_git_assertion": True,
        "attempted_workflow_advance": False,
    }


def _complete_generated_markdown(artifact_root: Path) -> None:
    for path in artifact_root.rglob("*.md"):
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "TBD",
                "Completed fixture evidence with trace links, decisions or outputs, and AI usage disclosure.",
            ),
            encoding="utf-8",
        )


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
