from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from modeller.cli import main
from modeller.traceability import (
    build_run_manifest,
    evaluate_close_gate,
    validate_context_receipt,
    validate_run_manifest,
)
from modeller.workflow import advance_workflow, complete_artifact, init_workflow, load_workflow


ROOT = Path(__file__).resolve().parents[1]


class TraceabilityTests(unittest.TestCase):
    def test_run_manifest_refs_artifacts_and_context_without_copying_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            envelope = _write_envelope(root, "orchestrate", run_id="run-trace")
            init_workflow(root, "run-trace")
            _complete_full_workflow(root, "run-trace")

            manifest = build_run_manifest(root, "run-trace", envelope_path=envelope)
            manifest_check = validate_run_manifest(manifest)
            receipt_check = validate_context_receipt(manifest["context_receipts"][0])

            self.assertTrue(manifest_check.ok, manifest_check.errors)
            self.assertTrue(receipt_check.ok, receipt_check.errors)
            self.assertTrue(manifest["gates"]["close"]["ok"], manifest["gates"]["close"])
            self.assertTrue(all(ref.get("sha256") for ref in manifest["artifacts"]), manifest["artifacts"])
            manifest_text = json.dumps(manifest)
            self.assertNotIn("Implementation artifact records changed files", manifest_text)
            self.assertNotIn("Handoff captures final state", manifest_text)

    def test_close_gate_requires_completed_workflow_not_subagent_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-open")
            complete_artifact(
                root=root,
                run_id="run-open",
                artifact="brief",
                updated_by="orchestrator",
                evidence=(
                    "Evidence: outcome, scope, source-of-truth repositories, source-boundary, "
                    "constraints, and acceptance evidence are present."
                ),
                output="Output: brief drafted.",
            )

            gate = evaluate_close_gate(root, "run-open")

            self.assertFalse(gate["ok"])
            self.assertTrue(any("workflow state status" in error for error in gate["errors"]), gate)
            returned_edits = next(check for check in gate["checks"] if check["id"] == "returned_edits_evidence")
            self.assertFalse(returned_edits["ok"], returned_edits)

    def test_workflow_close_cli_writes_manifest_and_returns_gate_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            envelope = _write_envelope(root, "orchestrate", run_id="run-cli-close")
            init_workflow(root, "run-cli-close")
            _complete_full_workflow(root, "run-cli-close")

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--root",
                        str(root),
                        "workflow",
                        "close",
                        "--run-id",
                        "run-cli-close",
                        "--envelope",
                        str(envelope),
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0, payload)
            self.assertTrue(payload["ok"], payload)
            manifest_path = root / ".modeller" / "runs" / "run-cli-close" / "run-manifest.json"
            self.assertEqual(Path(payload["manifest"]).resolve(), manifest_path.resolve())
            self.assertTrue(manifest_path.exists())


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


def _write_envelope(root: Path, requested_capability: str, run_id: str) -> Path:
    envelope = root / "envelope.json"
    envelope.write_text(
        json.dumps(
            {
                "intent": {"target_repository": "demo", "requested_capability": requested_capability},
                "execution_policy": {
                    "consent_required": True,
                    "max_risk_level": "low",
                    "run_id": run_id,
                },
            }
        ),
        encoding="utf-8",
    )
    return envelope


def _complete_full_workflow(root: Path, run_id: str) -> None:
    workflow = load_workflow(root)
    payloads = {
        "brief": (
            "orchestrator",
            "Evidence: outcome, scope, source-of-truth repositories, source-boundary, constraints, and acceptance evidence.",
            "Output: brief drafted.",
        ),
        "prd": (
            "planner",
            "Evidence: requirements, acceptance, and non-goals produced by subagent recon.",
            "Output: PRD drafted.",
        ),
        "decisions": (
            "planner",
            "Evidence: accepted, rejected, pending, and boundary choices produced by subagent recon.",
            "Output: decisions drafted.",
        ),
        "backlog": (
            "planner",
            "Evidence: priority, story, and verification terms are recorded.",
            "Output: backlog drafted.",
        ),
        "skills": (
            "architect",
            "Evidence: skill, trigger, and verification mapping produced by subagent design.",
            "Output: skills drafted.",
        ),
        "agents": (
            "architect",
            "Evidence: agent, authority, and scope mapping produced by subagent design.",
            "Output: agents drafted.",
        ),
        "memory": (
            "architect",
            "Evidence: memory, source, and retrieval policy produced by subagent design.",
            "Output: memory drafted.",
        ),
        "implementation": (
            "executor",
            "Evidence: changed files, commands run, and unresolved gaps are recorded.",
            "Output: Implementation artifact records changed files without copying source content.",
        ),
        "documentation": (
            "documenter",
            "Evidence: updated docs and runbook commands are recorded.",
            "Output: documentation drafted.",
        ),
        "handoff": (
            "orchestrator",
            "Evidence: final state, verification, residual risks, next actions, and subagent findings.",
            "Output: Handoff captures final state.",
        ),
    }
    for step in workflow["steps"]:
        for artifact in step["required_artifacts"]:
            owner, evidence, output = payloads[artifact]
            complete_artifact(root=root, run_id=run_id, artifact=artifact, updated_by=owner, evidence=evidence, output=output)
        gate = advance_workflow(root, run_id)
        if not gate.ok:
            raise AssertionError(gate.errors)


if __name__ == "__main__":
    unittest.main()
