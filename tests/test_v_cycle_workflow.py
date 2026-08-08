from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modeller.vcycle import (
    apply_human_review_provider,
    check_v_cycle_stage,
    init_v_cycle_run,
    list_v_cycle_workflows,
    review_v_cycle_stage,
    stage_artifact_digest,
    trace_check_v_cycle,
)
from modeller.workflow import (
    advance_workflow,
    complete_artifact,
    init_workflow,
    resume_workflow_from_checkpoint,
    verify_task_checkpoint,
    write_task_checkpoint,
)


ROOT = Path(__file__).resolve().parents[1]


class VCycleWorkflowTests(unittest.TestCase):
    def test_catalog_discovers_v_cycle_family_and_stage_contracts(self) -> None:
        catalog = list_v_cycle_workflows(ROOT)

        self.assertEqual(catalog[0]["workflow_family"], "v-cycle")
        self.assertEqual(catalog[0]["skill"], "v-cycle")
        self.assertEqual(catalog[0]["stage_count"], 13)
        stages = {stage["id"]: stage for stage in catalog[0]["stages"]}
        self.assertEqual(stages["functional-specification"]["paired_stage"], "system-validation")
        self.assertEqual(stages["deployment"]["vigilance_level"], "V4")

    def test_stage_only_initialization_creates_only_requested_stage_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))

            state = init_v_cycle_run(
                root,
                "run-stage",
                invocation_mode="stage",
                requested_stage="functional-specification",
            )

            self.assertEqual(state["selected_stages"], ["functional-specification"])
            artifact_root = root / state["artifact_root"]
            self.assertTrue((artifact_root / "BRIEF.md").exists())
            self.assertTrue((artifact_root / "stages/functional-specification/requirement-register.md").exists())
            self.assertFalse((artifact_root / "stages/needs-analysis").exists())
            prereqs = state["stages"][0]["prerequisites"]
            self.assertEqual(prereqs, [{"stage_id": "needs-analysis", "status": "missing"}])

    def test_paired_review_selects_requested_and_paired_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))

            state = init_v_cycle_run(
                root,
                "run-pair",
                invocation_mode="paired-review",
                requested_stage="functional-specification",
            )

            self.assertEqual(state["selected_stages"], ["functional-specification", "system-validation"])

    def test_trace_check_accepts_initialized_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-trace", invocation_mode="stage", requested_stage="implementation")

            gate = trace_check_v_cycle(root, "run-trace")

            self.assertTrue(gate.ok, gate.errors)

    def test_human_review_receipt_gates_advance_and_stale_digest_invalidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-review", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            stage = state["stages"][0]
            digest = stage_artifact_digest(root, state, stage)
            receipt = _write_receipt(root, "run-review", "implementation", "developer", digest)

            before_review = check_v_cycle_stage(root, "run-review", "implementation")
            self.assertFalse(before_review.ok)
            self.assertTrue(any("human review receipt" in error for error in before_review.errors), before_review.errors)

            review = review_v_cycle_stage(root, "run-review", receipt)
            self.assertTrue(review["ok"], review)
            after_review = check_v_cycle_stage(root, "run-review", "implementation")
            self.assertTrue(after_review.ok, after_review.errors)

            implementation_record = root / state["artifact_root"] / "stages/implementation/implementation-record.md"
            implementation_record.write_text(
                implementation_record.read_text(encoding="utf-8") + "\nmaterial change after review\n",
                encoding="utf-8",
            )
            stale = check_v_cycle_stage(root, "run-review", "implementation")
            self.assertFalse(stale.ok)
            self.assertTrue(any("invalidated" in error for error in stale.errors), stale.errors)

    def test_review_rejects_ai_actor_and_wrong_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-ai", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            digest = stage_artifact_digest(root, state, state["stages"][0])
            receipt = _write_receipt(root, "run-ai", "implementation", "architect", digest, actor_type="ai")

            review = review_v_cycle_stage(root, "run-ai", receipt)

            self.assertFalse(review["ok"])
            self.assertTrue(any("actor_type" in error for error in review["errors"]), review)
            self.assertTrue(any("reviewer.role" in error for error in review["errors"]), review)

    def test_review_rejects_schema_invalid_reviewer_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-schema", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            receipt = _write_receipt(root, "run-schema", "implementation", "", "sha256:not-enough")

            review = review_v_cycle_stage(root, "run-schema", receipt)

            self.assertFalse(review["ok"])
            self.assertTrue(any("artifact_digest" in error for error in review["errors"]), review)
            self.assertTrue(any("reviewer.role" in error for error in review["errors"]), review)

    def test_review_rejects_malformed_receipt_json_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            init_v_cycle_run(root, "run-malformed", invocation_mode="stage", requested_stage="implementation")
            non_object = root / "non-object-review.json"
            invalid = root / "invalid-review.json"
            non_object.write_text("[]", encoding="utf-8")
            invalid.write_text("{not-json", encoding="utf-8")

            non_object_result = review_v_cycle_stage(root, "run-malformed", non_object)
            invalid_result = review_v_cycle_stage(root, "run-malformed", invalid)

            self.assertFalse(non_object_result["ok"], non_object_result)
            self.assertIn("receipt must be a JSON object", non_object_result["errors"])
            self.assertFalse(invalid_result["ok"], invalid_result)
            self.assertTrue(any("not valid JSON" in error for error in invalid_result["errors"]), invalid_result)

    def test_test_fixture_review_provider_requires_metadata_and_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-fixture-denied", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            metadata = _write_fixture_metadata(root, "run-fixture-denied", "implementation")

            denied = apply_human_review_provider(
                root,
                "run-fixture-denied",
                provider="test-fixture",
                reviewer_id="fixture-human",
                reviewer_role="developer",
                allow_test_fixture=True,
            )
            missing_flag = apply_human_review_provider(
                root,
                "run-fixture-denied",
                provider="test-fixture",
                fixture_metadata_path=metadata,
                reviewer_id="fixture-human",
                reviewer_role="developer",
                allow_test_fixture=False,
            )

            self.assertFalse(denied["ok"], denied)
            self.assertTrue(any("--fixture-metadata" in error for error in denied["errors"]), denied)
            self.assertFalse(missing_flag["ok"], missing_flag)
            self.assertTrue(any("requires --allow-test-fixture" in error for error in missing_flag["errors"]), missing_flag)

    def test_test_fixture_review_provider_applies_digest_bound_human_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-fixture-ok", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            metadata = _write_fixture_metadata(root, "run-fixture-ok", "implementation")

            payload = apply_human_review_provider(
                root,
                "run-fixture-ok",
                provider="test-fixture",
                fixture_metadata_path=metadata,
                reviewer_id="fixture-human",
                reviewer_role="developer",
                allow_test_fixture=True,
            )
            gate = check_v_cycle_stage(root, "run-fixture-ok", "implementation")

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["provider"], "test-fixture")
            self.assertTrue(gate.ok, gate.errors)

    def test_receipt_file_provider_applies_user_supplied_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-provider-file", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            digest = stage_artifact_digest(root, state, state["stages"][0])
            receipt = _write_receipt(root, "run-provider-file", "implementation", "developer", digest)

            payload = apply_human_review_provider(
                root,
                "run-provider-file",
                provider="receipt-file",
                receipt_path=receipt,
            )

            self.assertTrue(payload["ok"], payload)

    def test_human_review_provider_cli_fixture_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_v_cycle_runtime(Path(tmp))
            state = init_v_cycle_run(root, "run-cli-fixture", invocation_mode="stage", requested_stage="implementation")
            _complete_generated_markdown(root / state["artifact_root"])
            metadata = _write_fixture_metadata(root, "run-cli-fixture", "implementation")

            result = _run_modeller_cli(
                "workflow",
                "--root",
                str(root),
                "request-review",
                "--run-id",
                "run-cli-fixture",
                "--provider",
                "test-fixture",
                "--fixture-metadata",
                str(metadata.relative_to(root)),
                "--reviewer-id",
                "fixture-human",
                "--reviewer-role",
                "developer",
                "--allow-test-fixture",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])

    def test_cli_recommend_maps_deployment_prompt(self) -> None:
        result = _run_modeller_cli("workflow", "recommend", "--prompt", "prepare deployment rollback approval")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["requested_stage"], "deployment")
        self.assertEqual(payload["stage"]["vigilance_level"], "V4")


class TaskCheckpointTests(unittest.TestCase):
    def test_write_and_verify_checkpoint_roundtrips_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-checkpoint-ok")

            written = write_task_checkpoint(
                root,
                "run-checkpoint-ok",
                task_id="task-001",
                project_id="proj-alpha",
                mission_id="mission-001",
                actor_id="reviewer-1",
                actor_role="developer",
                decision="approved",
            )
            verification = verify_task_checkpoint(root, "run-checkpoint-ok", written["checkpoint_id"])

            self.assertTrue(verification.ok, verification.errors)
            self.assertEqual(verification.verification_status, "verified")

    def test_verify_checkpoint_fails_closed_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-checkpoint-missing")

            verification = verify_task_checkpoint(root, "run-checkpoint-missing", "cp-does-not-exist")

            self.assertFalse(verification.ok)
            self.assertEqual(verification.verification_status, "missing")
            self.assertTrue(verification.remediation)

    def test_verify_checkpoint_fails_closed_on_state_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-checkpoint-stale")
            written = write_task_checkpoint(
                root,
                "run-checkpoint-stale",
                task_id="task-001",
                project_id="proj-alpha",
                mission_id="mission-001",
                actor_id="reviewer-1",
                actor_role="developer",
                decision="approved",
            )

            complete_artifact(
                root=root,
                run_id="run-checkpoint-stale",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            advance_workflow(root, "run-checkpoint-stale")
            verification = verify_task_checkpoint(root, "run-checkpoint-stale", written["checkpoint_id"])

            self.assertFalse(verification.ok)
            self.assertEqual(verification.verification_status, "stale")

    def test_verify_checkpoint_fails_closed_on_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-checkpoint-malformed")
            checkpoint_dir = root / ".modeller/runs/run-checkpoint-malformed/checkpoints"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            (checkpoint_dir / "cp-bad.json").write_text("{not-json", encoding="utf-8")

            verification = verify_task_checkpoint(root, "run-checkpoint-malformed", "cp-bad")

            self.assertFalse(verification.ok)
            self.assertEqual(verification.verification_status, "malformed")

    def test_verify_checkpoint_fails_closed_on_non_approving_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-checkpoint-rejected")
            written = write_task_checkpoint(
                root,
                "run-checkpoint-rejected",
                task_id="task-001",
                project_id="proj-alpha",
                mission_id="mission-001",
                actor_id="reviewer-1",
                actor_role="developer",
                decision="rejected",
            )

            verification = verify_task_checkpoint(root, "run-checkpoint-rejected", written["checkpoint_id"])

            self.assertFalse(verification.ok)
            self.assertTrue(any("does not approve resume" in error for error in verification.errors), verification.errors)

    def test_write_task_checkpoint_rejects_unsafe_identity_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-checkpoint-badid")

            with self.assertRaises(ValueError):
                write_task_checkpoint(
                    root,
                    "run-checkpoint-badid",
                    task_id="task/../escape",
                    project_id="proj-alpha",
                    mission_id="mission-001",
                    actor_id="reviewer-1",
                    actor_role="developer",
                    decision="approved",
                )

    def test_resume_from_checkpoint_requires_verification_before_gate_reexecution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-resume-blocked")

            gate = resume_workflow_from_checkpoint(root, "run-resume-blocked", "cp-never-written")

            self.assertFalse(gate.ok)
            self.assertTrue(any("checkpoint verification failed" in error for error in gate.errors), gate.errors)

    def test_resume_from_checkpoint_still_re_executes_gate_after_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_deterministic_workflow_root(Path(tmp))
            init_workflow(root, "run-resume-gated")
            written = write_task_checkpoint(
                root,
                "run-resume-gated",
                task_id="task-001",
                project_id="proj-alpha",
                mission_id="mission-001",
                actor_id="reviewer-1",
                actor_role="developer",
                decision="approved",
            )

            # Checkpoint is verified-clean, but the current step's artifact is still an
            # incomplete placeholder, so gate re-execution must still fail: a verified
            # checkpoint alone can never stand in for re-running the declared gate.
            gate = resume_workflow_from_checkpoint(root, "run-resume-gated", written["checkpoint_id"])

            self.assertFalse(gate.ok)
            self.assertTrue(gate.errors)

            complete_artifact(
                root=root,
                run_id="run-resume-gated",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )
            advance_workflow(root, "run-resume-gated")
            gate_after = resume_workflow_from_checkpoint(root, "run-resume-gated", written["checkpoint_id"])
            # The checkpoint is now stale (state changed by advance), so resume must fail
            # closed even though the underlying step gate itself would now pass -- checkpoint
            # verification always runs before gate re-execution is even attempted.
            self.assertFalse(gate_after.ok)
            self.assertTrue(any("checkpoint verification failed" in error for error in gate_after.errors), gate_after.errors)


def _copy_deterministic_workflow_root(tmp: Path) -> Path:
    root = tmp / "repo"
    workflow_dir = root / "method" / "workflows"
    template_dir = root / "method" / "templates"
    schema_dir = root / "schemas"
    workflow_dir.mkdir(parents=True)
    template_dir.mkdir(parents=True)
    schema_dir.mkdir(parents=True)
    (workflow_dir / "modeller-agents-build.workflow.json").write_text(
        (ROOT / "method/workflows/modeller-agents-build.workflow.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (template_dir / "workflow-artifact.md").write_text(
        (ROOT / "method/templates/workflow-artifact.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for name in ["mission-identity.schema.json", "checkpoint-receipt.schema.json"]:
        (schema_dir / name).write_text((ROOT / "schemas" / name).read_text(encoding="utf-8"), encoding="utf-8")
    return root


def _copy_v_cycle_runtime(tmp: Path) -> Path:
    root = tmp / "repo"
    for rel in [
        "method/workflows",
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


def _complete_generated_markdown(artifact_root: Path) -> None:
    for path in artifact_root.rglob("*.md"):
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "TBD",
                "Completed evidence with trace links, decisions or outputs, and AI usage disclosure.",
            ),
            encoding="utf-8",
        )


def _write_receipt(
    root: Path,
    run_id: str,
    stage_id: str,
    role: str,
    digest: str,
    *,
    actor_type: str = "human",
) -> Path:
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
                "reviewer": {"id": "human-reviewer", "role": role, "actor_type": actor_type},
                "decision": "approved",
                "reservations": [],
                "accepted_risks": [],
                "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return receipt


def _write_fixture_metadata(root: Path, run_id: str, stage_id: str) -> Path:
    path = root / ".modeller" / "runs" / run_id / "fixture-review.json"
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "stage_id": stage_id,
                "provider": "test-fixture",
                "fixture_run": True,
            }
        ),
        encoding="utf-8",
    )
    return path


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
