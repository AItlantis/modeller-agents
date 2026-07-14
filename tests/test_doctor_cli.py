from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import modeller.install as install_mod
from modeller.backend import check_backend
from modeller.cli import main
from modeller.doctor import (
    CAPABILITY_SKILLS,
    DoctorResult,
    _check_packaging,
    _check_reference_packs,
    _check_skill_surface,
    run_doctor,
)
from modeller.install import MANIFEST_RELATIVE_PATH, install_plugin
from modeller.readiness import build_readiness_report
from modeller.run import run_backend_pipeline, validate_backend_json, validate_result_json
from modeller.route import route_envelope
from modeller.sync import plan_sync
from modeller.workflow import advance_workflow, check_current_step, complete_artifact, init_workflow, load_state


ROOT = Path(__file__).resolve().parents[1]


class DoctorCliTests(unittest.TestCase):
    def test_doctor_warns_about_deactivated_domain_on_current_repo(self) -> None:
        # F-A: domain routability is intentionally disabled in the vault and
        # mirrored locally as draft/routable:false. Normal doctor should accept
        # that development state while keeping the disabled axis visible.
        result = run_doctor(ROOT)

        self.assertTrue(result.ok, result.format())
        self.assertTrue(
            any("domain accessibility: disabled in vault export" in warning for warning in result.warnings),
            result.warnings,
        )
        self.assertIn("workflow", result.skills)
        self.assertIn("aimsun-psp", result.backends)

    def test_packaging_gate_rejects_broken_console_script_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_packaging_root(root, script="modeller.bad:main")
            result = DoctorResult(root=root)

            _check_packaging(root, result)

            self.assertFalse(result.ok)
            self.assertIn("pyproject.toml project.scripts.modeller must be modeller.cli:main", result.errors)

    def test_doctor_rejects_broken_workflow_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            workflow = root / "method/workflows/modeller-agents-build.workflow.json"
            data = json.loads(workflow.read_text(encoding="utf-8"))
            data["steps"][0].pop("owner")
            workflow.write_text(json.dumps(data), encoding="utf-8")

            result = run_doctor(root)

            self.assertFalse(result.ok)
            self.assertTrue(any("steps[0].owner" in error for error in result.errors), result.errors)

    def test_skill_surface_gate_rejects_docs_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_skill_surface(root, docs_skills=["workflow"], readme_skills=["workflow", "review"])
            result = DoctorResult(root=root, skills=["workflow", "review"])

            _check_skill_surface(root, result)

            self.assertFalse(result.ok)
            self.assertTrue(any("docs skill index missing entries" in error for error in result.errors), result.errors)

    def test_skill_surface_gate_requires_direct_route_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_skill_surface(root, docs_skills=["workflow", "review"], readme_skills=["workflow", "review"])
            result = DoctorResult(root=root, skills=["workflow", "review"])
            original = dict(CAPABILITY_SKILLS)
            try:
                CAPABILITY_SKILLS["review"] = "workflow"
                _check_skill_surface(root, result)
            finally:
                CAPABILITY_SKILLS.clear()
                CAPABILITY_SKILLS.update(original)

            self.assertFalse(result.ok)
            self.assertTrue(any("map every canonical skill name directly" in error for error in result.errors), result.errors)

    def test_reference_pack_gate_uses_selected_pack_union(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_skill_surface(
                root,
                docs_skills=["workflow", "review"],
                readme_skills=["workflow", "review"],
                pack_skills=["workflow"],
            )
            result = DoctorResult(root=root, skills=["workflow", "review"])

            _check_reference_packs(root, result, strict=False)

            self.assertFalse(result.ok)
            self.assertTrue(any("not authorized by selected reference packs" in error for error in result.errors), result.errors)

    def test_doctor_strict_rejects_readiness_warnings(self) -> None:
        result = run_doctor(ROOT, strict=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("not planned" in error for error in result.errors), result.errors)
        self.assertTrue(any("to be pinned" in error for error in result.errors), result.errors)
        self.assertTrue(any("sibling fallback" in error for error in result.errors), result.errors)
        codes = {blocker["code"] for blocker in result.readiness_blockers}
        self.assertIn("reference-pack-not-active", codes)
        self.assertIn("vendor-not-synced", codes)
        self.assertIn("vendor-not-pinned", codes)
        self.assertIn("schema-sibling-fallback", codes)
        self.assertIn("backend-not-active", codes)

    def test_doctor_cli_strict_returns_failure(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--root", str(ROOT), "doctor", "--strict"])
        self.assertEqual(exit_code, 1)
        output = stdout.getvalue()
        self.assertIn("modeller doctor: FAIL", output)
        self.assertIn("strict readiness", output)

    def test_doctor_cli_json_is_machine_readable(self) -> None:
        # The disabled knowledge axis is a normal development warning, while
        # this test still verifies the JSON payload shape.
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--root", str(ROOT), "doctor", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertIn("workflow", payload["skills"])
        self.assertIn("warnings", payload)
        self.assertIn("errors", payload)
        self.assertTrue(
            any("domain accessibility: disabled in vault export" in warning for warning in payload["warnings"]),
            payload["warnings"],
        )

    def test_modeller_agents_compat_cli_json_is_machine_readable(self) -> None:
        # The compat CLI delegates to the same normal doctor; disabled domains
        # remain warnings, not structural errors.
        from modeller_agents.cli import main as compat_main

        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = compat_main(["--root", str(ROOT), "doctor", "--json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertIn("workflow", payload["skills"])
        self.assertTrue(
            any("domain accessibility: disabled in vault export" in warning for warning in payload["warnings"]),
            payload["warnings"],
        )

    def test_doctor_cli_strict_json_returns_failure_payload(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--root", str(ROOT), "doctor", "--strict", "--json"])
        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["ok"])
        self.assertTrue(any("strict readiness" in error for error in payload["errors"]), payload)
        self.assertTrue(payload["readiness_blockers"])
        self.assertTrue(any(blocker["code"] == "vendor-not-pinned" for blocker in payload["readiness_blockers"]))
        self.assertTrue(any(blocker["code"] == "backend-not-active" for blocker in payload["readiness_blockers"]))

    def test_readiness_report_maps_strict_blockers_to_actions(self) -> None:
        report = build_readiness_report(ROOT)

        self.assertFalse(report.ok)
        codes = {action.code for action in report.actions}
        self.assertIn("vendor-not-synced", codes)
        self.assertIn("schema-sibling-fallback", codes)
        self.assertIn("backend-not-active", codes)
        commands = "\n".join(command for action in report.actions for command in action.commands)
        self.assertIn("modeller.cli sync", commands)
        self.assertIn("modeller.cli run", commands)

    def test_readiness_cli_json_is_machine_readable(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--root", str(ROOT), "readiness", "--json"])

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["blocker_count"], len(payload["readiness_blockers"]))
        self.assertTrue(payload["actions"])

    def test_backend_check_accepts_planned_backend_without_local_root(self) -> None:
        result = check_backend(ROOT, "aimsun-psp")
        self.assertTrue(result.ok, result)
        self.assertIn("planned", result.status)

    def test_sync_plan_does_not_execute_git(self) -> None:
        plan = plan_sync(ROOT, "modeller-pipelines")
        self.assertEqual(plan.command[:3], ["git", "subtree", "pull"])
        self.assertIn("--squash", plan.command)

    def test_validate_backend_template_manifest(self) -> None:
        manifest = ROOT.parent / "modeller-pipelines" / "template" / "backend.json"
        result = validate_backend_json(manifest, expected_id="template", root=ROOT)
        self.assertTrue(result.ok, result.errors)
        self.assertIsNotNone(result.schema_path)

    def test_validate_result_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_json = Path(tmp) / "result.json"
            result_json.write_text(
                json.dumps(
                    {
                        "contract_version": "1.0",
                        "backend_id": "template",
                        "pipeline_id": "smoke",
                        "pipeline_version": "0.1",
                        "run_id": "run-001",
                        "status": "success",
                        "timestamps": {
                            "started_at": "2026-07-10T00:00:00Z",
                            "completed_at": "2026-07-10T00:00:01Z",
                        },
                        "config_path": "config.yml",
                        "steps": [{"status": "success", "step_id": 1, "step_name": "smoke"}],
                        "artifacts": [{"name": "result", "path": "result.json"}],
                    }
                ),
                encoding="utf-8",
            )
            result = validate_result_json(result_json, root=ROOT)
            self.assertTrue(result.ok, result.errors)
            self.assertIsNotNone(result.schema_path)

    def test_validate_result_json_rejects_absolute_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_json = Path(tmp) / "result.json"
            result_json.write_text(
                json.dumps(
                    {
                        "contract_version": "1.0",
                        "backend_id": "template",
                        "pipeline_id": "smoke",
                        "pipeline_version": "0.1",
                        "run_id": "run-001",
                        "status": "success",
                        "timestamps": {
                            "started_at": "2026-07-10T00:00:00Z",
                            "completed_at": "2026-07-10T00:00:01Z",
                        },
                        "config_path": "config.yml",
                        "steps": [{"status": "success", "step_id": 1, "step_name": "smoke"}],
                        "artifacts": [{"name": "bad", "path": str(Path(tmp) / "bad.txt")}],
                    }
                ),
                encoding="utf-8",
            )
            result = validate_result_json(result_json, root=ROOT)
            self.assertFalse(result.ok)
            self.assertIn("artifacts[0].path must be relative to run dir", result.errors)

    def test_validate_result_json_rejects_empty_proof_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_json = Path(tmp) / "result.json"
            result_json.write_text(
                json.dumps(
                    {
                        "contract_version": "1.0",
                        "backend_id": "template",
                        "pipeline_id": "smoke",
                        "pipeline_version": "0.1",
                        "run_id": "run-001",
                        "status": "success",
                        "timestamps": {
                            "started_at": "2026-07-10T00:00:00Z",
                            "completed_at": "2026-07-10T00:00:01Z",
                        },
                        "config_path": "config.yml",
                        "steps": [],
                        "artifacts": [],
                    }
                ),
                encoding="utf-8",
            )
            result = validate_result_json(result_json, root=ROOT)
            self.assertFalse(result.ok)
            self.assertIn("successful results must include at least one step", result.errors)
            self.assertIn("successful results must include at least one artifact", result.errors)

    def test_contract_schema_rejects_malformed_backend_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "backend.json"
            manifest.write_text(
                json.dumps(
                    {
                        "backend_id": "bad backend id",
                        "contract_version": "1.0",
                        "runner": {"command": [], "interpreter": "system-python", "platform": []},
                        "pipelines": [],
                    }
                ),
                encoding="utf-8",
            )
            result = validate_backend_json(manifest, root=ROOT)
            self.assertFalse(result.ok)
            self.assertTrue(any("schema" in error for error in result.errors), result.errors)

    def test_install_dry_run_records_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = install_plugin(ROOT, Path(tmp), dry_run=True)
            self.assertEqual(len(result.actions), 5)
            self.assertTrue(result.dry_run)
            self.assertTrue(any("write Python import bootstrap" in action for action in result.actions), result.actions)
            self.assertTrue(any("write install manifest" in action for action in result.actions), result.actions)

    def test_install_runtime_assets_dry_run_records_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = install_plugin(ROOT, Path(tmp), dry_run=True, include_runtime_assets=True)
            self.assertTrue(result.dry_run)
            self.assertEqual(len(result.actions), 11)
            self.assertTrue(any("copy runtime directory" in action for action in result.actions), result.actions)
            self.assertTrue(any("copy runtime file" in action for action in result.actions), result.actions)

    def test_install_python_path_dry_run_records_user_site_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = install_plugin(ROOT, Path(tmp), dry_run=True, install_python_path=True)

            self.assertTrue(result.dry_run)
            self.assertTrue(any("write user-site Python path file" in action for action in result.actions), result.actions)

    def test_install_runtime_assets_apply_copies_central_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            result = install_plugin(ROOT, target, dry_run=False, include_runtime_assets=True)
            self.assertFalse(result.dry_run)
            self.assertTrue((target / ".claude/plugins/modeller").exists())
            self.assertTrue((target / ".modeller/runtime/method/workflows/modeller-agents-build.workflow.json").exists())
            self.assertTrue((target / ".modeller/runtime/reference-packs/testudo.toml").exists())
            self.assertTrue((target / ".modeller/runtime/bundles/testudo.bundle.json").exists())
            self.assertTrue((target / ".modeller/runtime/schemas/run-manifest.schema.json").exists())
            self.assertTrue((target / ".modeller/runtime/backends.toml").exists())
            self.assertTrue((target / ".modeller/runtime/vendors.toml").exists())
            self.assertTrue((target / "sitecustomize.py").exists())
            self.assertIn("modeller-agents", (target / "sitecustomize.py").read_text(encoding="utf-8"))
            manifest = json.loads((target / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertTrue(manifest["include_runtime_assets"])
            self.assertEqual(manifest["runtime_root"], ".modeller/runtime")
            self.assertEqual(manifest["python_path_bootstrap"], "sitecustomize.py")
            self.assertIn(".modeller/runtime/method", manifest["copied_runtime_assets"])
            self.assertIn(".modeller/runtime/schemas", manifest["copied_runtime_assets"])
            self.assertIn(".modeller/runtime/vendors.toml", manifest["copied_runtime_assets"])
            self.assertIn("available", manifest["source_git"])
            self.assertIn(
                manifest["source_git"]["status"],
                {"dirty-worktree-copy", "clean-worktree-copy", "not-a-git-worktree", "git-metadata-unavailable"},
            )

    def test_install_reconciles_stale_memory_mcp_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            target_mcp = target / ".mcp.json"
            target_mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "modeller-memory": {
                                "command": "python",
                                "args": ["-m", "modeller_memory.mcp"],
                                "env": {},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            install_plugin(ROOT, target, dry_run=False, include_runtime_assets=True)

            mcp = json.loads(target_mcp.read_text(encoding="utf-8"))
            self.assertEqual(mcp, {"mcpServers": {}})

    def test_install_runtime_assets_migrates_legacy_root_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "method").mkdir()
            (target / "reference-packs").mkdir()
            (target / "bundles").mkdir()
            (target / "schemas").mkdir()
            (target / "backends.toml").write_text("legacy\n", encoding="utf-8")
            (target / "vendors.toml").write_text("legacy\n", encoding="utf-8")
            (target / ".modeller").mkdir()
            (target / MANIFEST_RELATIVE_PATH).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "installer": "modeller-agents",
                        "source_root": str(ROOT),
                        "target_root": str(target),
                        "include_runtime_assets": True,
                        "copied_runtime_assets": [
                            "method",
                            "reference-packs",
                            "bundles",
                            "schemas",
                            "backends.toml",
                            "vendors.toml",
                        ],
                    }
                ),
                encoding="utf-8",
            )

            install_plugin(ROOT, target, dry_run=False, include_runtime_assets=True)

            self.assertFalse((target / "method").exists())
            self.assertFalse((target / "backends.toml").exists())
            self.assertTrue((target / ".modeller/runtime/method").exists())
            self.assertTrue((target / ".modeller/runtime/backends.toml").exists())

    def test_doctor_warns_about_deactivated_domain_on_installed_runtime_target(self) -> None:
        # Installed runtime assets carry the same mirrored disabled domain
        # state, which should be visible as a warning but not fail doctor.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            install_plugin(ROOT, target, dry_run=False, include_runtime_assets=True)

            result = run_doctor(target)

            self.assertTrue(result.ok, result.format())
            self.assertTrue(
                any("domain accessibility: disabled in vault export" in warning for warning in result.warnings),
                result.warnings,
            )
            self.assertIn("workflow", result.skills)
            self.assertIn("aimsun-psp", result.backends)

    def test_install_uses_packaged_runtime_when_requested_root_has_no_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            requested_root = tmp_root / "empty"
            target = tmp_root / "target"
            runtime = tmp_root / "runtime"
            requested_root.mkdir()
            _write_minimal_runtime_assets(runtime)
            original_runtime = install_mod.PACKAGED_RUNTIME_ROOT
            try:
                install_mod.PACKAGED_RUNTIME_ROOT = runtime
                result = install_plugin(requested_root, target, dry_run=False, include_runtime_assets=True)
            finally:
                install_mod.PACKAGED_RUNTIME_ROOT = original_runtime

            self.assertFalse(result.dry_run)
            self.assertTrue((target / ".claude/plugins/modeller").exists())
            self.assertTrue((target / ".modeller/runtime/method").exists())
            self.assertTrue((target / ".modeller/runtime/schemas").exists())
            self.assertTrue((target / ".modeller/runtime/vendors.toml").exists())
            self.assertTrue((target / "sitecustomize.py").exists())
            manifest = json.loads((target / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_root"], str(runtime.resolve()))

    def test_route_example_envelope(self) -> None:
        envelope = ROOT / "examples" / "testudo-context-envelope.json"
        decision = route_envelope(ROOT, envelope)
        self.assertTrue(decision.ok, decision.errors)
        self.assertEqual(decision.target_repository, "testudo")
        self.assertEqual(decision.skill, "review")
        self.assertEqual(decision.bundle, "testudo")
        self.assertEqual(decision.routing_key_kind, "repository")
        self.assertEqual(decision.knowledge_domains, [])
        self.assertEqual(decision.knowledge_packs, [])

    def test_run_backend_pipeline_uses_runner_command_seam(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend_root = Path(tmp)
            runner = backend_root / "runner.py"
            runner.write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "from pathlib import Path",
                        "args = sys.argv[1:]",
                        "run_dir = Path(args[args.index('--run-dir') + 1])",
                        "run_dir.mkdir(parents=True, exist_ok=True)",
                        "result = run_dir / 'result.json'",
                        "result.write_text(json.dumps({",
                        "  'contract_version': '1.0',",
                        "  'backend_id': 'aimsun-psp',",
                        "  'pipeline_id': 'smoke',",
                        "  'pipeline_version': '0.1',",
                        "  'run_id': 'run-001',",
                        "  'status': 'success',",
                        "  'timestamps': {'started_at': '2026-07-10T00:00:00Z', 'completed_at': '2026-07-10T00:00:01Z'},",
                        "  'config_path': 'config.yml',",
                        "  'steps': [{'status': 'success', 'step_id': 1, 'step_name': 'smoke'}],",
                        "  'artifacts': [{'name': 'result', 'path': 'result.json'}]",
                        "}), encoding='utf-8')",
                        "print(str(result.resolve()))",
                    ]
                ),
                encoding="utf-8",
            )
            (backend_root / "backend.json").write_text(
                json.dumps(
                    {
                        "backend_id": "aimsun-psp",
                        "contract_version": "1.0",
                        "runner": {
                            "command": [sys.executable, "runner.py"],
                            "interpreter": "system-python",
                            "platform": ["any"],
                        },
                        "pipelines": [{"id": "smoke", "definition": "smoke.pipeline.yml"}],
                    }
                ),
                encoding="utf-8",
            )
            config = backend_root / "config.yml"
            config.write_text("{}", encoding="utf-8")
            result = run_backend_pipeline(
                root=ROOT,
                backend_id="aimsun-psp",
                pipeline_id="smoke",
                config=config,
                run_dir=backend_root / "run",
                backend_root=backend_root,
                timeout_s=10,
            )
            self.assertTrue(result.ok, result.format())
            self.assertIn("runner.py", result.command)

    def test_workflow_blocks_until_required_artifact_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-001")
            gate = check_current_step(root, "run-001")
            self.assertFalse(gate.ok)
            self.assertTrue(any("status" in error for error in gate.errors), gate.errors)
            complete_artifact(
                root=root,
                run_id="run-001",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: source-boundary decision and user objective inspected. "
                    "The outcome, scope, source-of-truth repositories, constraints, "
                    "and acceptance evidence are recorded."
                ),
                output="Output: scoped brief accepted for deterministic workflow run.",
            )
            gate = advance_workflow(root, "run-001")
            self.assertTrue(gate.ok, gate.errors)
            state = load_state(root, "run-001")
            self.assertEqual(state["steps"][0]["status"], "complete")
            self.assertEqual(state["steps"][1]["status"], "in_progress")

    def test_workflow_rejects_invalid_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            for run_id in ["..\\escape", "../escape", "a/b", "..", ".", "a..b"]:
                with self.subTest(run_id=run_id):
                    with self.assertRaises(ValueError):
                        init_workflow(root, run_id)

    def test_workflow_rejects_future_step_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-001")
            with self.assertRaises(ValueError):
                complete_artifact(
                    root=root,
                    run_id="run-001",
                    artifact="prd",
                    updated_by="planner",
                    evidence="Evidence: requirements, acceptance, and non-goals were drafted.",
                    output="Output: PRD drafted.",
                )

    def test_workflow_rejects_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-001")
            with self.assertRaises(ValueError):
                complete_artifact(
                    root=root,
                    run_id="run-001",
                    artifact="brief",
                    updated_by="executor",
                    evidence=(
                        "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                        "constraints, and acceptance evidence are present."
                    ),
                    output="Output: brief drafted.",
                )

    def test_workflow_rejects_missing_artifact_specific_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-001")
            complete_artifact(
                root=root,
                run_id="run-001",
                artifact="brief",
                updated_by="orchestrator",
                evidence="Evidence: a brief was drafted.",
                output="Output: brief drafted.",
            )
            gate = check_current_step(root, "run-001")
            self.assertFalse(gate.ok)
            self.assertTrue(any("required evidence term" in error for error in gate.errors), gate.errors)

    def test_workflow_gate_rejects_manually_edited_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-001")
            path = complete_artifact(
                root=root,
                run_id="run-001",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            path.write_text(path.read_text(encoding="utf-8").replace("updated_by: orchestrator", "updated_by: executor"), encoding="utf-8")
            gate = check_current_step(root, "run-001")
            self.assertFalse(gate.ok)
            self.assertTrue(any("updated_by must be owner" in error for error in gate.errors), gate.errors)


def _copy_minimal_workflow_root(tmp: Path) -> Path:
    root = tmp / "repo"
    workflow_dir = root / "method" / "workflows"
    template_dir = root / "method" / "templates"
    workflow_dir.mkdir(parents=True)
    template_dir.mkdir(parents=True)
    (workflow_dir / "modeller-agents-build.workflow.json").write_text(
        (ROOT / "method/workflows/modeller-agents-build.workflow.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (template_dir / "workflow-artifact.md").write_text(
        (ROOT / "method/templates/workflow-artifact.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return root


def _write_minimal_packaging_root(root: Path, script: str = "modeller.cli:main") -> None:
    (root / "src/modeller").mkdir(parents=True)
    (root / "src/modeller_agents").mkdir(parents=True)
    (root / ".claude/plugins/modeller").mkdir(parents=True)
    (root / "method").mkdir()
    (root / "reference-packs").mkdir()
    (root / "bundles").mkdir()
    (root / "schemas").mkdir()
    (root / "src/modeller/__init__.py").write_text("", encoding="utf-8")
    (root / "src/modeller/cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "src/modeller_agents/__init__.py").write_text("", encoding="utf-8")
    (root / "src/modeller_agents/cli.py").write_text("from modeller.cli import main\n", encoding="utf-8")
    (root / ".claude/settings.json").write_text("{}", encoding="utf-8")
    (root / ".mcp.json.example").write_text("{}", encoding="utf-8")
    (root / "backends.toml").write_text('schema_version = "0.1"\n', encoding="utf-8")
    (root / "schemas/context-receipt.schema.json").write_text("{}", encoding="utf-8")
    (root / "schemas/run-manifest.schema.json").write_text("{}", encoding="utf-8")
    (root / "vendors.toml").write_text('schema_version = "0.1"\n', encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "LICENSE").write_text("Demo license\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["hatchling>=1.25"]',
                'build-backend = "hatchling.build"',
                "",
                "[project]",
                'name = "modeller-agents"',
                'version = "0.1.0"',
                'readme = "README.md"',
                'license = { file = "LICENSE" }',
                "",
                "[project.scripts]",
                f'modeller = "{script}"',
                "",
                "[tool.hatch.build.targets.wheel]",
                'packages = ["src/modeller", "src/modeller_agents"]',
                "",
                "[tool.hatch.build.targets.wheel.force-include]",
                '".claude/plugins/modeller" = "modeller/runtime/.claude/plugins/modeller"',
                '".claude/settings.json" = "modeller/runtime/.claude/settings.json"',
                '".mcp.json.example" = "modeller/runtime/.mcp.json.example"',
                '"method" = "modeller/runtime/method"',
                '"reference-packs" = "modeller/runtime/reference-packs"',
                '"bundles" = "modeller/runtime/bundles"',
                '"schemas" = "modeller/runtime/schemas"',
                '"backends.toml" = "modeller/runtime/backends.toml"',
                '"vendors.toml" = "modeller/runtime/vendors.toml"',
            ]
        ),
        encoding="utf-8",
    )


def _write_minimal_runtime_assets(root: Path) -> None:
    (root / ".claude/plugins/modeller").mkdir(parents=True)
    (root / "method").mkdir()
    (root / "reference-packs").mkdir()
    (root / "bundles").mkdir()
    (root / "schemas").mkdir()
    (root / ".claude/plugins/modeller/README.md").write_text("# Plugin\n", encoding="utf-8")
    (root / ".claude/settings.json").write_text("{}", encoding="utf-8")
    (root / ".mcp.json.example").write_text("{}", encoding="utf-8")
    (root / "backends.toml").write_text('schema_version = "0.1"\n', encoding="utf-8")
    (root / "schemas/context-receipt.schema.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    (root / "schemas/run-manifest.schema.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    (root / "vendors.toml").write_text('schema_version = "0.1"\n', encoding="utf-8")


def _write_minimal_skill_surface(
    root: Path,
    docs_skills: list[str],
    readme_skills: list[str],
    pack_skills: list[str] | None = None,
) -> None:
    (root / "docs/skills/modeller").mkdir(parents=True)
    (root / ".claude/plugins/modeller").mkdir(parents=True)
    (root / "bundles").mkdir()
    (root / "reference-packs").mkdir()
    (root / "modeller-modules.yaml").write_text(
        "\n".join(
            [
                "schema_version: 0.1",
                "skills:",
                "  - workflow",
                "  - review",
                "bundles:",
                "  - id: demo",
                "    path: bundles/demo.bundle.json",
                "reference_packs:",
                "  - reference-packs/demo.toml",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs/skills/modeller/SKILL_INDEX.md").write_text(
        "# Index\n\n## Seed Skills\n\n" + "\n".join(f"- `{skill}`" for skill in docs_skills) + "\n",
        encoding="utf-8",
    )
    (root / ".claude/plugins/modeller/README.md").write_text(
        "# Plugin\n\n## Seed Skills\n\n" + "\n".join(f"- `{skill}`" for skill in readme_skills) + "\n",
        encoding="utf-8",
    )
    (root / "bundles/demo.bundle.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "status": "draft",
                "routingKeyKind": "repository",
                "skills": ["workflow", "review"],
                "referencePacks": ["reference-packs/demo.toml"],
            }
        ),
        encoding="utf-8",
    )
    (root / "reference-packs/demo.toml").write_text(
        "\n".join(
            [
                'id = "demo"',
                'status = "draft"',
                'source_repository = "demo"',
                'owner = "demo"',
                "central_skills = " + json.dumps(pack_skills or ["workflow", "review"]),
                "local_agents_stay_in_source = true",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
