from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from modeller.planning import build_execution_plan, discover_repository_capabilities, load_workflow_catalog


ROOT = Path(__file__).resolve().parents[1]


class PlanningTests(unittest.TestCase):
    def test_capability_manifest_discovers_local_runtime_assets(self) -> None:
        manifest = discover_repository_capabilities(ROOT)

        self.assertFalse(manifest.errors, manifest.errors)
        self.assertIn("review", manifest.capabilities)
        self.assertIn("testudo", {bundle["id"] for bundle in manifest.bundles})
        self.assertIn("workflow", manifest.skills)
        self.assertIn("modeller-agents-build", {workflow["workflow_id"] for workflow in manifest.workflows})

    def test_workflow_catalog_exposes_step_owners(self) -> None:
        catalog = load_workflow_catalog(ROOT)

        self.assertFalse(catalog.errors, catalog.errors)
        workflow = catalog.workflows[0]
        self.assertEqual(workflow["workflow_id"], "modeller-agents-build")
        owners = {step["id"]: step["owner"] for step in workflow["steps"]}
        self.assertEqual(owners["implementation"], "executor")
        self.assertEqual(owners["handoff"], "orchestrator")

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


if __name__ == "__main__":
    unittest.main()
