from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from modeller.cli import main
from modeller.install import install_plugin
from modeller.planning import build_execution_plan, discover_repository_capabilities, load_workflow_catalog


ROOT = Path(__file__).resolve().parents[1]


class PlanningTests(unittest.TestCase):
    def test_capability_manifest_discovers_local_runtime_assets(self) -> None:
        manifest = discover_repository_capabilities(ROOT)

        self.assertFalse(manifest.errors, manifest.errors)
        self.assertIn("review", manifest.capabilities)
        self.assertIn("testudo", {bundle["id"] for bundle in manifest.bundles})
        self.assertIn("workflow", manifest.skills)
        self.assertIn("v-cycle", manifest.skills)
        self.assertIn("modeller-agents-build", {workflow["workflow_id"] for workflow in manifest.workflows})
        self.assertIn("v-cycle", {workflow.get("workflow_family") for workflow in manifest.workflows})

    def test_workflow_catalog_exposes_step_owners(self) -> None:
        catalog = load_workflow_catalog(ROOT)

        self.assertFalse(catalog.errors, catalog.errors)
        workflow = catalog.workflows[0]
        self.assertEqual(workflow["workflow_id"], "modeller-agents-build")
        owners = {step["id"]: step["owner"] for step in workflow["steps"]}
        self.assertEqual(owners["implementation"], "executor")
        self.assertEqual(owners["handoff"], "orchestrator")
        v_cycle = next(workflow for workflow in catalog.workflows if workflow.get("workflow_family") == "v-cycle")
        self.assertEqual(v_cycle["stage_count"], 13)

    def test_execution_plan_infers_prompt_and_resolves_skill_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope_output = Path(tmp) / "testudo-envelope.json"

            plan = build_execution_plan(
                ROOT,
                "review testudo source boundary",
                envelope_output=envelope_output,
            )

            self.assertTrue(plan.ok, plan.to_dict())
            self.assertEqual(plan.intent_draft.target_repository, "testudo")
            self.assertEqual(plan.intent_draft.requested_capability, "review")
            self.assertEqual(plan.skill_plan.skill, "review")
            self.assertEqual(plan.skill_plan.bundle, "testudo")
            self.assertEqual(plan.tool_plan.status, "ready")
            self.assertTrue(any(command[3] == "route" for command in plan.tool_plan.commands), plan.tool_plan.commands)

    def test_plan_module_cli_writes_envelope_and_route_accepts_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope_output = Path(tmp) / "testudo-envelope.json"
            plan_result = _run_modeller_cli(
                "plan",
                "--prompt",
                "review testudo",
                "--json",
                "--envelope-output",
                str(envelope_output),
            )

            self.assertEqual(plan_result.returncode, 0, plan_result.stdout + plan_result.stderr)
            payload = json.loads(plan_result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["intent_draft"]["target_repository"], "testudo")
            self.assertEqual(payload["skill_plan"]["skill"], "review")
            self.assertTrue(envelope_output.exists())

            route_result = _run_modeller_cli("route", "--envelope", str(envelope_output))

            self.assertEqual(route_result.returncode, 0, route_result.stdout + route_result.stderr)
            route_payload = json.loads(route_result.stdout)
            self.assertTrue(route_payload["ok"], route_payload)
            self.assertEqual(route_payload["target_repository"], "testudo")
            self.assertEqual(route_payload["skill"], "review")

    def test_plan_cli_rejects_unknown_capability_before_route(self) -> None:
        result = _run_modeller_cli(
            "plan",
            "--prompt",
            "do an impossible capability for testudo",
            "--requested-capability",
            "not-a-skill",
            "--json",
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"], payload)
        self.assertIn("unknown requested_capability 'not-a-skill'", payload["intent_draft"]["errors"])

    def test_natural_docs_lookup_routes_read_only_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope_output = Path(tmp) / "docs-envelope.json"

            plan = build_execution_plan(
                ROOT,
                "Find docs for testudo source boundary; do not edit files",
                envelope_output=envelope_output,
            )

            self.assertTrue(plan.ok, plan.to_dict())
            self.assertEqual(plan.intent_draft.target_repository, "testudo")
            self.assertEqual(plan.intent_draft.requested_capability, "review")
            self.assertEqual(plan.intent_draft.requires_workflow, False)
            self.assertEqual(plan.intent_draft.max_risk_level, "low")
            self.assertEqual(plan.intent_draft.intent_classification.primary_intent, "documentation-lookup")
            self.assertEqual(plan.context_envelope["intent"]["classification"]["primary_intent"], "documentation-lookup")

    def test_natural_brief_recon_routes_v_cycle_governance(self) -> None:
        plan = build_execution_plan(
            ROOT,
            "Create a brief.md and recon.md about aimsun-psp domains/_41_MacroscopicResult/pipelines/rendering_geh.",
        )

        self.assertFalse(plan.ok, plan.to_dict())
        self.assertEqual(plan.intent_draft.target_repository, "aimsun-psp")
        self.assertEqual(
            plan.intent_draft.target_path,
            "domains/_41_MacroscopicResult/pipelines/rendering_geh",
        )
        self.assertEqual(
            plan.context_envelope["intent"]["target_path"],
            "domains/_41_MacroscopicResult/pipelines/rendering_geh",
        )
        self.assertEqual(plan.intent_draft.requested_capability, "v-cycle")
        self.assertEqual(plan.intent_draft.workflow_family, "v-cycle")
        self.assertEqual(plan.intent_draft.v_cycle_stage, "project-governance")
        self.assertEqual(plan.intent_draft.gate_policy, "bind-run")
        self.assertEqual(plan.intent_draft.requires_workflow, True)
        self.assertEqual(plan.intent_draft.mutation_scope, "workflow-artifacts")
        self.assertEqual(plan.intent_draft.max_risk_level, "medium")
        self.assertTrue(
            any("run_id" in blocker for blocker in plan.tool_plan.blocked_by),
            plan.tool_plan.blocked_by,
        )
        self.assertTrue(
            any(command[3:5] == ["workflow", "--root"] or "init" in command for command in plan.tool_plan.commands),
            plan.tool_plan.commands,
        )

    def test_natural_code_edit_routes_v_cycle_implementation(self) -> None:
        plan = build_execution_plan(
            ROOT,
            "Refactor aimsun-psp code and update tests",
        )

        self.assertFalse(plan.ok, plan.to_dict())
        self.assertEqual(plan.intent_draft.requested_capability, "v-cycle")
        self.assertEqual(plan.intent_draft.v_cycle_stage, "implementation")
        self.assertEqual(plan.intent_draft.gate_policy, "bind-run")
        self.assertEqual(plan.intent_draft.requires_workflow, True)
        self.assertEqual(plan.intent_draft.mutation_scope, "source-code")
        self.assertTrue(any("run_id" in blocker for blocker in plan.tool_plan.blocked_by), plan.tool_plan.blocked_by)

    def test_target_path_extraction_normalizes_windows_separators(self) -> None:
        plan = build_execution_plan(
            ROOT,
            "Create recon for aimsun-psp domains\\_41_MacroscopicResult\\pipelines\\rendering_geh",
        )

        self.assertEqual(
            plan.intent_draft.target_path,
            "domains/_41_MacroscopicResult/pipelines/rendering_geh",
        )

    def test_prompt_without_target_path_is_allowed(self) -> None:
        plan = build_execution_plan(
            ROOT,
            "Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
        )

        self.assertIsNone(plan.intent_draft.target_path)
        self.assertNotIn("target_path", plan.context_envelope["intent"])

    def test_natural_e2e_test_repair_routes_integration_testing(self) -> None:
        plan = build_execution_plan(
            ROOT,
            "Fix failing E2E tests for aimsun-psp",
        )

        self.assertFalse(plan.ok, plan.to_dict())
        self.assertEqual(plan.intent_draft.requested_capability, "v-cycle")
        self.assertEqual(plan.intent_draft.v_cycle_stage, "integration-testing")
        self.assertEqual(plan.intent_draft.requires_workflow, True)
        self.assertEqual(plan.intent_draft.mutation_scope, "tests")

    def test_ambiguous_natural_intent_blocks_for_clarification(self) -> None:
        plan = build_execution_plan(
            ROOT,
            "Find docs and deploy aimsun-psp",
        )

        self.assertFalse(plan.ok, plan.to_dict())
        self.assertEqual(plan.intent_draft.requested_capability, "workflow")
        self.assertTrue(
            any("ambiguous natural-language intent" in error for error in plan.intent_draft.errors),
            plan.intent_draft.errors,
        )

    def test_explicit_capability_and_workflow_override_win_over_natural_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope_output = Path(tmp) / "override-envelope.json"

            plan = build_execution_plan(
                ROOT,
                "Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                requested_capability="review",
                requires_workflow=False,
                envelope_output=envelope_output,
            )

            self.assertTrue(plan.ok, plan.to_dict())
            self.assertEqual(plan.intent_draft.requested_capability, "review")
            self.assertEqual(plan.intent_draft.requires_workflow, False)
            self.assertIsNone(plan.intent_draft.workflow_family)
            self.assertIsNone(plan.intent_draft.v_cycle_stage)
            self.assertIsNone(plan.intent_draft.gate_policy)
            self.assertEqual(plan.tool_plan.status, "ready")

    def test_plan_cli_resolves_installed_child_root_from_parent_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            target = workspace / "aimsun" / "aimsun-psp"
            target.mkdir(parents=True)
            install_plugin(ROOT, target, dry_run=False, include_runtime_assets=True)

            exit_code, payload = _run_main_json(
                "--root",
                str(workspace),
                "plan",
                "--prompt",
                "Find docs for aimsun-psp source boundary; do not edit files",
                "--target-repository",
                "aimsun-psp",
                "--json",
            )

            self.assertEqual(exit_code, 0, payload)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["alignment_contract"]["source_root"], str(target.resolve()))
            self.assertEqual(payload["skill_plan"]["bundle"], "aimsun-psp")

    def test_orchestrate_cli_writes_run_under_resolved_child_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            target = workspace / "aimsun" / "aimsun-psp"
            target.mkdir(parents=True)
            install_plugin(ROOT, target, dry_run=False, include_runtime_assets=True)

            exit_code, payload = _run_main_json(
                "--root",
                str(workspace),
                "orchestrate",
                "--prompt",
                "Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline",
                "--target-repository",
                "aimsun-psp",
                "--run-id",
                "parent-root-orchestrate",
                "--json",
            )

            self.assertEqual(exit_code, 0, payload)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["plan"]["alignment_contract"]["source_root"], str(target.resolve()))
            self.assertTrue((target / ".modeller/runs/parent-root-orchestrate/state.json").exists())
            self.assertFalse((workspace / ".modeller/runs/parent-root-orchestrate/state.json").exists())

    def test_parent_root_without_child_install_reports_precise_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()

            exit_code, payload = _run_main_json(
                "--root",
                str(workspace),
                "plan",
                "--prompt",
                "Find docs for aimsun-psp source boundary; do not edit files",
                "--target-repository",
                "aimsun-psp",
                "--json",
            )

            self.assertEqual(exit_code, 1, payload)
            self.assertFalse(payload["ok"], payload)
            self.assertEqual(payload["inspected_root"], str(workspace.resolve()))
            self.assertIn("searched_root_bundle", payload)
            self.assertIn("*", payload["searched_child_patterns"][1])
            self.assertIn("aimsun-psp", payload["searched_child_patterns"][1])
            self.assertTrue(any("no bundle found" in error for error in payload["errors"]), payload)
            self.assertIn("--root", payload["advice"])

    def test_parent_root_with_multiple_matching_child_installs_blocks_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            first = workspace / "one" / "aimsun-psp"
            second = workspace / "two" / "aimsun-psp"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            install_plugin(ROOT, first, dry_run=False, include_runtime_assets=True)
            install_plugin(ROOT, second, dry_run=False, include_runtime_assets=True)

            exit_code, payload = _run_main_json(
                "--root",
                str(workspace),
                "plan",
                "--prompt",
                "Find docs for aimsun-psp source boundary; do not edit files",
                "--target-repository",
                "aimsun-psp",
                "--json",
            )

            self.assertEqual(exit_code, 1, payload)
            self.assertTrue(any("multiple installed child roots" in error for error in payload["errors"]), payload)
            self.assertEqual(set(payload["matching_installed_child_candidates"]), {str(first.resolve()), str(second.resolve())})

    def test_existing_root_bundle_wins_without_child_scan_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            install_plugin(ROOT, workspace, dry_run=False, include_runtime_assets=True)
            child = workspace / "aimsun" / "aimsun-psp"
            child.mkdir(parents=True)
            install_plugin(ROOT, child, dry_run=False, include_runtime_assets=True)

            exit_code, payload = _run_main_json(
                "--root",
                str(workspace),
                "plan",
                "--prompt",
                "Find docs for aimsun-psp source boundary; do not edit files",
                "--target-repository",
                "aimsun-psp",
                "--json",
            )

            self.assertEqual(exit_code, 0, payload)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["alignment_contract"]["source_root"], str(workspace.resolve()))


def _run_modeller_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "modeller.cli", "--root", str(ROOT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_main_json(*args: str) -> tuple[int, dict]:
    stdout = StringIO()
    with redirect_stdout(stdout):
        exit_code = main(list(args))
    return exit_code, json.loads(stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
