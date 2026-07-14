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

    def test_close_gate_requires_context_receipt_when_envelope_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            init_workflow(root, "run-receipt-required")
            _complete_full_workflow(root, "run-receipt-required")
            _mark_context_receipt_expected(root, "run-receipt-required")

            gate = evaluate_close_gate(root, "run-receipt-required")

            self.assertFalse(gate["ok"], gate)
            self.assertTrue(any("ContextReceipt is required" in error for error in gate["errors"]), gate)
            receipt_check = next(check for check in gate["checks"] if check["id"] == "context_receipt_presence")
            self.assertFalse(receipt_check["ok"], receipt_check)

    def test_close_gate_accepts_expected_envelope_when_receipt_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            envelope = _write_envelope(root, "orchestrate", run_id="run-receipt-present")
            init_workflow(root, "run-receipt-present")
            _complete_full_workflow(root, "run-receipt-present")
            _mark_context_receipt_expected(root, "run-receipt-present")

            manifest = build_run_manifest(root, "run-receipt-present", envelope_path=envelope)

            self.assertTrue(manifest["gates"]["close"]["ok"], manifest["gates"]["close"])
            self.assertEqual(len(manifest["context_receipts"]), 1)

    def test_close_gate_requires_final_parity_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-no-parity")
            _complete_full_workflow(root, "run-no-parity", final_parity=False)

            gate = evaluate_close_gate(root, "run-no-parity")

            self.assertFalse(gate["ok"], gate)
            self.assertTrue(any("final parity evidence" in error for error in gate["errors"]), gate)
            parity_check = next(check for check in gate["checks"] if check["id"] == "final_parity_evidence")
            self.assertFalse(parity_check["ok"], parity_check)

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

    def test_workflow_close_module_cli_fails_incomplete_run_with_manifest_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-cli-incomplete")

            result = _run_modeller_cli(root, "workflow", "close", "--run-id", "run-cli-incomplete")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"], payload)
            self.assertTrue(payload["manifest_check"]["ok"], payload)
            self.assertFalse(payload["close_gate"]["ok"], payload)
            self.assertTrue(
                any("workflow state status" in error for error in payload["close_gate"]["errors"]),
                payload,
            )
            manifest_path = root / ".modeller" / "runs" / "run-cli-incomplete" / "run-manifest.json"
            self.assertTrue(manifest_path.exists())

    def test_workflow_close_module_cli_fails_when_expected_receipt_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-cli-missing-receipt")
            _complete_full_workflow(root, "run-cli-missing-receipt")
            _mark_context_receipt_expected(root, "run-cli-missing-receipt")

            result = _run_modeller_cli(root, "workflow", "close", "--run-id", "run-cli-missing-receipt")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"], payload)
            self.assertFalse(payload["close_gate"]["ok"], payload)
            receipt_check = next(
                check for check in payload["close_gate"]["checks"] if check["id"] == "context_receipt_presence"
            )
            self.assertFalse(receipt_check["ok"], receipt_check)
            self.assertTrue(any("ContextReceipt is required" in error for error in receipt_check["errors"]), payload)

    def test_workflow_close_module_cli_fails_completed_run_without_context_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            init_workflow(root, "run-cli-no-receipt")
            _complete_full_workflow(root, "run-cli-no-receipt")

            result = _run_modeller_cli(root, "workflow", "close", "--run-id", "run-cli-no-receipt")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"], payload)
            receipt_check = next(
                check for check in payload["close_gate"]["checks"] if check["id"] == "context_receipt_presence"
            )
            self.assertFalse(receipt_check["ok"], receipt_check)
            self.assertTrue(receipt_check["expected"], receipt_check)
            self.assertEqual(receipt_check["receipt_count"], 0)
            self.assertTrue(any("ContextReceipt is required" in error for error in receipt_check["errors"]), payload)

    def test_workflow_close_module_cli_fails_supplied_invalid_context_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            envelope = _write_envelope(root, "unknown-capability", run_id="run-cli-bad-receipt")
            init_workflow(root, "run-cli-bad-receipt")
            _complete_full_workflow(root, "run-cli-bad-receipt")

            result = _run_modeller_cli(
                root,
                "workflow",
                "close",
                "--run-id",
                "run-cli-bad-receipt",
                "--envelope",
                str(envelope),
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"], payload)
            self.assertFalse(payload["manifest_check"]["ok"], payload)
            self.assertTrue(
                any("selection.ok must be true" in error for error in payload["manifest_check"]["errors"]),
                payload,
            )
            receipt_check = next(
                check for check in payload["close_gate"]["checks"] if check["id"] == "context_receipt_presence"
            )
            self.assertFalse(receipt_check["ok"], receipt_check)

    def test_workflow_close_module_cli_valid_run_has_traceability_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_minimal_workflow_root(Path(tmp))
            _write_bundle_and_pack(root, skills=["orchestrate"])
            envelope = _write_envelope(root, "orchestrate", run_id="run-cli-valid")
            init_workflow(root, "run-cli-valid")
            _complete_full_workflow(root, "run-cli-valid")

            result = _run_modeller_cli(
                root,
                "workflow",
                "close",
                "--run-id",
                "run-cli-valid",
                "--envelope",
                str(envelope),
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertTrue(payload["manifest_check"]["ok"], payload)
            self.assertTrue(payload["close_gate"]["ok"], payload)
            checks = {check["id"]: check for check in payload["close_gate"]["checks"]}
            self.assertTrue(checks["returned_edits_evidence"]["ok"], checks)
            self.assertTrue(checks["context_receipt_presence"]["ok"], checks)
            self.assertEqual(checks["context_receipt_presence"]["receipt_count"], 1)
            self.assertTrue(checks["final_parity_evidence"]["ok"], checks)
            manifest = json.loads(Path(payload["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["context_receipts"]), 1)
            self.assertTrue(all(ref.get("sha256") for ref in manifest["artifacts"]), manifest["artifacts"])


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


def _mark_context_receipt_expected(root: Path, run_id: str) -> None:
    state_path = root / ".modeller" / "runs" / run_id / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["context_receipt_expected"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _complete_full_workflow(root: Path, run_id: str, *, final_parity: bool = True) -> None:
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
            verification = None
            if artifact == "handoff" and final_parity:
                verification = (
                    "Verification: final parity evidence was checked against the final tree; "
                    "residual risks, next actions, and subagent findings remain recorded."
                )
            complete_artifact(
                root=root,
                run_id=run_id,
                artifact=artifact,
                updated_by=owner,
                evidence=evidence,
                output=output,
                verification=verification,
            )
        gate = advance_workflow(root, run_id)
        if not gate.ok:
            raise AssertionError(gate.errors)


if __name__ == "__main__":
    unittest.main()
