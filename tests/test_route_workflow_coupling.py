from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from modeller.cli import main
from modeller.route import route_envelope
from modeller.vcycle import init_v_cycle_run
from modeller.workflow import _validate_artifact, check_current_step, complete_artifact, init_workflow


ROOT = Path(__file__).resolve().parents[1]


class RouteWorkflowCouplingTests(unittest.TestCase):
    def test_orchestrate_route_blocks_without_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            envelope = _write_envelope(root, "orchestrate")

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(
                any("run_id" in error for error in decision.errors),
                decision.errors,
            )
            self.assertIsNone(decision.run_id)

    def test_orchestrate_route_blocks_on_failing_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            init_workflow(root, "run-gate-fail")
            envelope = _write_envelope(root, "orchestrate", run_id="run-gate-fail")

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(
                any("gate not satisfied" in error for error in decision.errors),
                decision.errors,
            )

    def test_orchestrate_route_passes_when_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            init_workflow(root, "run-gate-pass")
            complete_artifact(
                root=root,
                run_id="run-gate-pass",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            gate = check_current_step(root, "run-gate-pass")
            self.assertTrue(gate.ok, gate.errors)
            envelope = _write_envelope(root, "orchestrate", run_id="run-gate-pass")

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.run_id, "run-gate-pass")
            self.assertFalse(
                any("workflow gate" in error or "gate not satisfied" in error for error in decision.errors),
                decision.errors,
            )

    def test_orchestrate_route_run_id_cli_override_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            init_workflow(root, "run-gate-pass")
            complete_artifact(
                root=root,
                run_id="run-gate-pass",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            # Envelope carries a bogus run_id; the explicit override must win.
            envelope = _write_envelope(root, "orchestrate", run_id="does-not-exist")

            decision = route_envelope(root, envelope, run_id="run-gate-pass")

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.run_id, "run-gate-pass")

    def test_cli_route_accepts_run_id_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            init_workflow(root, "run-gate-pass")
            complete_artifact(
                root=root,
                run_id="run-gate-pass",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            envelope = _write_envelope(root, "orchestrate")

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--root",
                        str(root),
                        "route",
                        "--envelope",
                        str(envelope),
                        "--run-id",
                        "run-gate-pass",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["run_id"], "run-gate-pass")

    def test_non_orchestrate_route_is_backward_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["review"])
            envelope = _write_envelope(root, "review")

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.skill, "review")
            self.assertIsNone(decision.run_id)
            self.assertFalse(
                any("run_id" in error or "gate" in error for error in decision.errors),
                decision.errors,
            )

    def test_v_cycle_route_requires_run_id_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_v_cycle_route_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["v-cycle"])
            envelope = _write_envelope(root, "v-cycle")

            missing_run = route_envelope(root, envelope)

            self.assertFalse(missing_run.ok)
            self.assertTrue(any("run_id" in error for error in missing_run.errors), missing_run.errors)

            init_v_cycle_run(root, "run-v-cycle", invocation_mode="stage", requested_stage="implementation")
            gated = route_envelope(root, envelope, run_id="run-v-cycle")

            self.assertFalse(gated.ok)
            self.assertEqual(gated.run_id, "run-v-cycle")
            self.assertTrue(any("workflow gate not satisfied" in error for error in gated.errors), gated.errors)

    def test_v_cycle_route_blocks_stage_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_v_cycle_route_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["v-cycle"])
            init_v_cycle_run(root, "run-v-cycle", invocation_mode="stage", requested_stage="implementation")
            envelope = _write_envelope(
                root,
                "v-cycle",
                run_id="run-v-cycle",
                intent_extra={"workflow_family": "v-cycle", "v_cycle_stage": "unit-testing"},
                policy_extra={"requires_workflow": True, "workflow_family": "v-cycle"},
            )

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(any("does not match requested stage" in error for error in decision.errors), decision.errors)

    def test_v_cycle_bind_run_policy_accepts_initialized_run_before_exit_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_v_cycle_route_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["v-cycle"])
            init_v_cycle_run(root, "run-v-cycle", invocation_mode="stage", requested_stage="implementation")
            envelope = _write_envelope(
                root,
                "v-cycle",
                run_id="run-v-cycle",
                intent_extra={"workflow_family": "v-cycle", "v_cycle_stage": "implementation"},
                policy_extra={
                    "requires_workflow": True,
                    "workflow_family": "v-cycle",
                    "gate_policy": "bind-run",
                },
            )

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.run_id, "run-v-cycle")

    def test_v_cycle_route_respects_explicit_no_workflow_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_v_cycle_route_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["v-cycle"])
            envelope = _write_envelope(root, "v-cycle", policy_extra={"requires_workflow": False})

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertIsNone(decision.run_id)

    def test_provenance_binding_rejects_evidence_without_marker(self) -> None:
        workflow = json.loads(
            (ROOT / "method/workflows/modeller-agents-build.workflow.json").read_text(encoding="utf-8")
        )
        step = next(s for s in workflow["steps"] if s["id"] == "requirements")
        self.assertTrue(step.get("requires_agent_evidence"))

        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-provenance")
            # Advance to the requirements step by completing the intake artifact.
            complete_artifact(
                root=root,
                run_id="run-provenance",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            from modeller.workflow import advance_workflow

            advance_gate = advance_workflow(root, "run-provenance")
            self.assertTrue(advance_gate.ok, advance_gate.errors)

            complete_artifact(
                root=root,
                run_id="run-provenance",
                artifact="prd",
                updated_by="planner",
                evidence="Evidence: requirements, acceptance, and non-goals were drafted by hand.",
                output="Output: PRD drafted.",
            )
            complete_artifact(
                root=root,
                run_id="run-provenance",
                artifact="decisions",
                updated_by="planner",
                evidence="Evidence: accepted, rejected, and pending boundary choices recorded.",
                output="Output: decisions drafted.",
            )

            gate = check_current_step(root, "run-provenance")
            self.assertFalse(gate.ok)
            self.assertTrue(
                any("provenance" in error.lower() or "must cite" in error for error in gate.errors),
                gate.errors,
            )

    def test_provenance_binding_accepts_evidence_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-provenance-ok")
            complete_artifact(
                root=root,
                run_id="run-provenance-ok",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            from modeller.workflow import advance_workflow

            advance_gate = advance_workflow(root, "run-provenance-ok")
            self.assertTrue(advance_gate.ok, advance_gate.errors)

            complete_artifact(
                root=root,
                run_id="run-provenance-ok",
                artifact="prd",
                updated_by="planner",
                evidence=(
                    "Evidence: requirements, acceptance, and non-goals were drafted, incorporating "
                    "subagent findings from the requirements-recon subagent run."
                ),
                output="Output: PRD drafted.",
            )
            complete_artifact(
                root=root,
                run_id="run-provenance-ok",
                artifact="decisions",
                updated_by="planner",
                evidence=(
                    "Evidence: accepted, rejected, and pending boundary choices recorded, "
                    "produced by subagent recon and incorporated here."
                ),
                output="Output: decisions drafted.",
            )

            gate = check_current_step(root, "run-provenance-ok")
            self.assertTrue(gate.ok, gate.errors)

    def test_validate_artifact_directly_flags_missing_provenance(self) -> None:
        workflow = json.loads(
            (ROOT / "method/workflows/modeller-agents-build.workflow.json").read_text(encoding="utf-8")
        )
        step = next(s for s in workflow["steps"] if s["id"] == "requirements")

        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-direct")
            from modeller.workflow import artifact_path

            path = artifact_path(root, workflow, "run-direct", "prd")
            complete_artifact(
                root=root,
                run_id="run-direct",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            from modeller.workflow import advance_workflow

            advance_workflow(root, "run-direct")

            complete_artifact(
                root=root,
                run_id="run-direct",
                artifact="prd",
                updated_by="planner",
                evidence="Evidence: requirements, acceptance, and non-goals were drafted.",
                output="Output: PRD drafted.",
            )
            errors_without_marker = _validate_artifact(path, workflow, "run-direct", "prd", step)
            self.assertTrue(
                any("provenance" in e.lower() or "must cite" in e for e in errors_without_marker),
                errors_without_marker,
            )

            complete_artifact(
                root=root,
                run_id="run-direct",
                artifact="prd",
                updated_by="planner",
                evidence=(
                    "Evidence: requirements, acceptance, and non-goals were drafted; "
                    "produced by subagent recon and incorporated here."
                ),
                output="Output: PRD drafted.",
            )
            errors_with_marker = _validate_artifact(path, workflow, "run-direct", "prd", step)
            self.assertFalse(
                any("provenance" in e.lower() or "must cite" in e for e in errors_with_marker),
                errors_with_marker,
            )


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


def _copy_minimal_v_cycle_route_root(tmp: Path) -> Path:
    root = _copy_minimal_workflow_root(tmp)
    for rel in [
        "method/policies",
        "schemas",
        ".claude/plugins/modeller/skills/v-cycle",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel in [
        "method/workflows/v-cycle.family.yaml",
        "method/workflows/v-cycle.stages.yaml",
        "method/policies/v-cycle-vigilance.yaml",
        "schemas/v-cycle-trace.schema.json",
        "schemas/human-review-receipt.schema.json",
        ".claude/plugins/modeller/skills/v-cycle/SKILL.md",
    ]:
        (root / rel).write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return root


def _write_bundle_and_pack(root: Path, skills: list[str]) -> None:
    (root / "bundles").mkdir(parents=True, exist_ok=True)
    (root / "reference-packs").mkdir(parents=True, exist_ok=True)
    (root / "bundles" / "demo.bundle.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "status": "draft",
                "routingKeyKind": "repository",
                "skills": skills,
                "referencePacks": ["reference-packs/demo.toml"],
            }
        ),
        encoding="utf-8",
    )
    (root / "reference-packs" / "demo.toml").write_text(
        "\n".join(
            [
                'id = "demo"',
                'status = "draft"',
                'source_repository = "demo"',
                'owner = "demo"',
                "central_skills = " + json.dumps(skills),
                "local_agents_stay_in_source = true",
            ]
        ),
        encoding="utf-8",
    )


def _write_envelope(
    root: Path,
    requested_capability: str,
    run_id: str | None = None,
    intent_extra: dict | None = None,
    policy_extra: dict | None = None,
) -> Path:
    envelope = root / "envelope.json"
    execution_policy: dict = {"consent_required": True, "max_risk_level": "low"}
    if run_id is not None:
        execution_policy["run_id"] = run_id
    if policy_extra:
        execution_policy.update(policy_extra)
    intent = {"target_repository": "demo", "requested_capability": requested_capability}
    if intent_extra:
        intent.update(intent_extra)
    envelope.write_text(
        json.dumps(
            {
                "intent": intent,
                "execution_policy": execution_policy,
            }
        ),
        encoding="utf-8",
    )
    return envelope


if __name__ == "__main__":
    unittest.main()
