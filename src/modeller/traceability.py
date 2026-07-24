from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .runtime import runtime_path
from .subagents import load_persisted_subagent_lane_receipts
from .vcycle import (
    STANDARD_ARTIFACTS,
    check_v_cycle_stage,
    check_v_cycle_current_stage,
    is_v_cycle_run,
    load_v_cycle_state,
)
from .workflow import (
    DEFAULT_WORKFLOW,
    _artifact_step,
    _section,
    _state_path,
    _validate_artifact,
    _validate_run_id,
    artifact_path,
    check_current_step,
    load_state,
    load_workflow,
)


TRACEABILITY_SCHEMA_VERSION = 1
CONTEXT_RECEIPT_ALGORITHM = "context-receipt-v1"
RUN_MANIFEST_ALGORITHM = "run-manifest-v1"


@dataclass
class TraceabilityCheck:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def format(self) -> str:
        lines = [f"traceability check: {'OK' if self.ok else 'FAIL'}"]
        lines.extend(f"warning: {warning}" for warning in self.warnings)
        lines.extend(f"error: {error}" for error in self.errors)
        return "\n".join(lines)


def build_context_receipt(root: Path, envelope_path: Path, *, run_id: str | None = None) -> dict:
    """Build a receipt for routed context without copying selected content."""
    from .route import route_envelope

    envelope_path = envelope_path.resolve()
    envelope = json.loads(envelope_path.read_text(encoding="utf-8-sig"))
    decision = route_envelope(root, envelope_path, run_id=run_id)
    intent = envelope.get("intent", {})
    policy = envelope.get("execution_policy", {})

    artifact_refs = [_artifact_ref(root, envelope_path, "context-envelope", kind="context-envelope")]
    if decision.bundle:
        artifact_refs.append(_artifact_ref(root, runtime_path(root, "bundles", f"{decision.bundle}.bundle.json"), "bundle"))
    for rel_path in decision.reference_packs:
        artifact_refs.append(_artifact_ref(root, runtime_path(root, rel_path), f"reference-pack:{rel_path}", kind="reference-pack"))
    for rel_path in decision.knowledge_packs:
        artifact_refs.append(_artifact_ref(root, runtime_path(root, rel_path), f"knowledge-pack:{rel_path}", kind="knowledge-pack"))

    receipt = {
        "schema_version": TRACEABILITY_SCHEMA_VERSION,
        "receipt_id": _digest_id("context", artifact_refs),
        "algorithm_version": CONTEXT_RECEIPT_ALGORITHM,
        "created_at": _now(),
        "retrieval_query": {
            "target_repository": intent.get("target_repository"),
            "requested_capability": intent.get("requested_capability") or "workflow",
            "requested_domains": list(intent.get("domains", [])),
            "run_id": run_id or policy.get("run_id") or intent.get("run_id"),
        },
        "selection": {
            "ok": decision.ok,
            "skill": decision.skill,
            "bundle": decision.bundle,
            "routing_key_kind": decision.routing_key_kind,
            "reference_packs": decision.reference_packs,
            "knowledge_domains": decision.knowledge_domains,
            "knowledge_packs": decision.knowledge_packs,
            "knowledge_budget": decision.knowledge_budget,
        },
        "candidate_refs": artifact_refs,
        "retained_refs": artifact_refs,
        "excluded_refs": [],
        "permissions_applied": {
            "consent_required": decision.consent_required,
            "max_risk_level": decision.max_risk_level,
        },
        "warnings": decision.warnings,
        "errors": decision.errors,
    }
    return receipt


def build_run_manifest(
    root: Path,
    run_id: str,
    *,
    workflow_id: str = DEFAULT_WORKFLOW,
    envelope_path: Path | None = None,
) -> dict:
    _validate_run_id(run_id)
    if is_v_cycle_run(root, run_id):
        return _build_v_cycle_run_manifest(root, run_id, envelope_path=envelope_path)
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    state_ref = _artifact_ref(root, _state_path(root, workflow, run_id), "workflow-state", kind="workflow-state")
    workflow_ref = _artifact_ref(
        root,
        runtime_path(root, "method", "workflows", f"{workflow_id}.workflow.json"),
        "workflow-definition",
        kind="workflow-definition",
    )
    artifact_refs = _workflow_artifact_refs(root, workflow, run_id)
    subagents = _subagent_receipt_refs(root, run_id)
    context_receipts = []
    if envelope_path is not None:
        context_receipts.append(build_context_receipt(root, envelope_path, run_id=run_id))
    gate = check_current_step(root, run_id, workflow_id)
    close_gate = evaluate_close_gate(root, run_id, workflow_id=workflow_id, context_receipts=context_receipts)

    current_step = workflow["steps"][state["current_step_index"]]
    return {
        "schema_version": TRACEABILITY_SCHEMA_VERSION,
        "manifest_id": _digest_id("run", [state_ref, workflow_ref, *artifact_refs, *_subagent_manifest_id_refs(subagents)]),
        "algorithm_version": RUN_MANIFEST_ALGORITHM,
        "created_at": _now(),
        "run": {
            "run_id": run_id,
            "workflow_id": workflow["workflow_id"],
            "status": state.get("status"),
            "current_step_id": current_step["id"],
            "artifact_root": state.get("artifact_root"),
        },
        "workflow": {
            "definition_ref": workflow_ref,
            "state_ref": state_ref,
            "steps": state.get("steps", []),
        },
        "context_receipts": context_receipts,
        "artifacts": artifact_refs,
        "subagents": subagents,
        "outputs": [],
        "gates": {
            "current_step": _gate_to_dict(gate),
            "all_steps": evaluate_all_artifact_gates(root, run_id, workflow_id=workflow_id),
            "close": close_gate,
        },
        "candidate_links": [],
    }


def _build_v_cycle_run_manifest(root: Path, run_id: str, *, envelope_path: Path | None = None) -> dict:
    state = load_v_cycle_state(root, run_id)
    state_ref = _artifact_ref(
        root,
        root / ".modeller" / "runs" / run_id / "state.json",
        "workflow-state",
        kind="workflow-state",
    )
    workflow_ref = _artifact_ref(
        root,
        runtime_path(root, "method", "workflows", "v-cycle.family.yaml"),
        "workflow-definition",
        kind="workflow-definition",
    )
    stages_ref = _artifact_ref(
        root,
        runtime_path(root, "method", "workflows", "v-cycle.stages.yaml"),
        "workflow-stages",
        kind="workflow-definition",
    )
    artifact_refs = _v_cycle_artifact_refs(root, state)
    subagents = _subagent_receipt_refs(root, run_id)
    context_receipts = []
    if envelope_path is not None:
        context_receipts.append(build_context_receipt(root, envelope_path, run_id=run_id))
    gate = check_v_cycle_current_stage(root, run_id)
    all_stage_gates = _evaluate_all_v_cycle_stage_gates(root, state)
    close_gate = _evaluate_v_cycle_close_gate(state, gate, all_stage_gates, artifact_refs, context_receipts)
    current = state["stages"][int(state["current_stage_index"])]
    return {
        "schema_version": TRACEABILITY_SCHEMA_VERSION,
        "manifest_id": _digest_id(
            "run",
            [state_ref, workflow_ref, stages_ref, *artifact_refs, *_subagent_manifest_id_refs(subagents)],
        ),
        "algorithm_version": RUN_MANIFEST_ALGORITHM,
        "created_at": _now(),
        "run": {
            "run_id": run_id,
            "workflow_id": "v-cycle",
            "status": state.get("status"),
            "current_step_id": current.get("id"),
            "artifact_root": state.get("artifact_root"),
        },
        "workflow": {
            "definition_ref": workflow_ref,
            "state_ref": state_ref,
            "steps": state.get("stages", []),
            "stage_definition_ref": stages_ref,
        },
        "context_receipts": context_receipts,
        "artifacts": artifact_refs,
        "subagents": subagents,
        "outputs": [],
        "gates": {
            "current_step": gate.to_dict(),
            "all_steps": all_stage_gates,
            "close": close_gate,
        },
        "candidate_links": [],
    }


def evaluate_all_artifact_gates(root: Path, run_id: str, *, workflow_id: str = DEFAULT_WORKFLOW) -> dict:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    errors: list[str] = []
    checked: list[str] = []
    for artifact in workflow.get("artifacts", {}):
        step = _artifact_step(workflow, artifact)
        checked.append(artifact)
        errors.extend(_validate_artifact(artifact_path(root, workflow, run_id, artifact), workflow, run_id, artifact, step))
    return {
        "ok": not errors,
        "checked_artifacts": checked,
        "errors": errors,
    }


def evaluate_close_gate(
    root: Path,
    run_id: str,
    *,
    workflow_id: str = DEFAULT_WORKFLOW,
    context_receipts: list[dict] | None = None,
    envelope_expected: bool | None = None,
) -> dict:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    all_gates = evaluate_all_artifact_gates(root, run_id, workflow_id=workflow_id)
    artifact_refs = _workflow_artifact_refs(root, workflow, run_id)
    implementation_ref = next((ref for ref in artifact_refs if ref.get("id") == "artifact:implementation"), None)
    implementation_errors: list[str] = []
    if implementation_ref:
        implementation_errors = _validate_artifact(
            artifact_path(root, workflow, run_id, "implementation"),
            workflow,
            run_id,
            "implementation",
            _artifact_step(workflow, "implementation"),
        )
    implementation_ok = bool(implementation_ref and implementation_ref.get("sha256") and not implementation_errors)
    final_parity_ref = next((ref for ref in artifact_refs if ref.get("id") == "artifact:handoff"), None)
    final_parity_errors = _validate_final_parity_evidence(root, workflow, run_id)
    final_parity_ok = bool(final_parity_ref and final_parity_ref.get("sha256") and not final_parity_errors)
    if envelope_expected is None:
        envelope_expected = _state_expects_context_receipt(state)
    receipt_errors = _validate_expected_context_receipts(context_receipts or [], expected=True)
    receipt_ok = not receipt_errors
    digest_refs_ok = bool(artifact_refs) and all(ref.get("sha256") for ref in artifact_refs)
    state_ref = _artifact_ref(root, _state_path(root, workflow, run_id), "workflow-state", kind="workflow-state")
    workflow_ref = _artifact_ref(
        root,
        runtime_path(root, "method", "workflows", f"{workflow_id}.workflow.json"),
        "workflow-definition",
        kind="workflow-definition",
    )
    digest_refs_ok = digest_refs_ok and bool(state_ref.get("sha256")) and bool(workflow_ref.get("sha256"))

    checks = [
        {
            "id": "returned_edits_evidence",
            "ok": implementation_ok,
            "evidence_refs": [implementation_ref] if implementation_ref else [],
            "errors": implementation_errors,
        },
        {
            "id": "workflow_gate_status",
            "ok": state.get("status") == "complete" and all_gates["ok"],
            "state_status": state.get("status"),
            "errors": all_gates["errors"],
        },
        {
            "id": "artifact_digest_references",
            "ok": digest_refs_ok,
            "evidence_refs": [state_ref, workflow_ref, *artifact_refs],
        },
        {
            "id": "context_receipt_presence",
            "ok": receipt_ok,
            "expected": True,
            "envelope_expected": bool(envelope_expected),
            "receipt_count": len(context_receipts or []),
            "errors": receipt_errors,
        },
        {
            "id": "final_parity_evidence",
            "ok": final_parity_ok,
            "evidence_refs": [final_parity_ref] if final_parity_ref else [],
            "errors": final_parity_errors,
        },
    ]
    errors: list[str] = []
    if state.get("status") != "complete":
        errors.append("workflow state status must be complete before close")
    errors.extend(all_gates["errors"])
    if not implementation_ref:
        errors.append("implementation artifact digest reference is required for close")
    elif implementation_errors:
        errors.append("implementation artifact must pass its returned-edits evidence gate before close")
    if not digest_refs_ok:
        errors.append("all workflow, state, and artifact references must include sha256 digests")
    errors.extend(receipt_errors)
    if final_parity_errors:
        errors.extend(final_parity_errors)
    return {
        "ok": not errors and all(check["ok"] for check in checks),
        "checks": checks,
        "errors": errors,
    }


def write_run_manifest(
    root: Path,
    run_id: str,
    *,
    workflow_id: str = DEFAULT_WORKFLOW,
    envelope_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    manifest = build_run_manifest(root, run_id, workflow_id=workflow_id, envelope_path=envelope_path)
    if output_path is None:
        output_path = root / ".modeller" / "runs" / run_id / "run-manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output_path


def validate_context_receipt(receipt: dict) -> TraceabilityCheck:
    check = _validate_traceability_shape(
        receipt,
        required=["schema_version", "receipt_id", "algorithm_version", "retrieval_query", "selection", "retained_refs"],
        ref_arrays=["retained_refs", "candidate_refs"],
    )
    selection = receipt.get("selection")
    if not isinstance(selection, dict):
        check.errors.append("selection must be an object")
    elif selection.get("ok") is not True:
        check.errors.append("selection.ok must be true")
    if receipt.get("errors"):
        check.errors.append("errors must be empty")
    check.ok = not check.errors
    return check


def validate_run_manifest(manifest: dict) -> TraceabilityCheck:
    check = _validate_traceability_shape(
        manifest,
        required=["schema_version", "manifest_id", "algorithm_version", "run", "workflow", "artifacts", "gates"],
        ref_arrays=["artifacts"],
    )
    workflow = manifest.get("workflow")
    if not isinstance(workflow, dict):
        check.errors.append("workflow must be an object")
    else:
        for key in ["definition_ref", "state_ref"]:
            errors = _validate_artifact_ref(workflow.get(key), f"workflow.{key}")
            check.errors.extend(errors)
    for index, receipt in enumerate(manifest.get("context_receipts", []) or []):
        if not isinstance(receipt, dict):
            check.errors.append(f"context_receipts[{index}] must be an object")
            continue
        receipt_check = validate_context_receipt(receipt)
        check.errors.extend(f"context_receipts[{index}]: {error}" for error in receipt_check.errors)
    for index, subagent in enumerate(manifest.get("subagents", []) or []):
        if not isinstance(subagent, dict):
            check.errors.append(f"subagents[{index}] must be an object")
            continue
        check.errors.extend(_validate_artifact_ref(subagent.get("receipt_ref"), f"subagents[{index}].receipt_ref"))
        check.errors.extend(_validate_artifact_ref(subagent.get("work_order_ref"), f"subagents[{index}].work_order_ref"))
        for key in ["receipt_id", "work_order_id", "agent_id", "run_id", "stage_id", "exit_status", "output_digest"]:
            if not subagent.get(key):
                check.errors.append(f"subagents[{index}].{key} is required")
    close_gate = manifest.get("gates", {}).get("close") if isinstance(manifest.get("gates"), dict) else None
    if not isinstance(close_gate, dict):
        check.errors.append("gates.close must be an object")
    check.ok = not check.errors
    return check


def _state_expects_context_receipt(state: dict) -> bool:
    context = state.get("context") if isinstance(state.get("context"), dict) else {}
    return any(
        bool(value)
        for value in [
            state.get("context_receipt_expected"),
            state.get("context_envelope_expected"),
            state.get("expected_context_receipt"),
            state.get("expected_context_receipts"),
            state.get("context_envelope"),
            state.get("envelope_path"),
            context.get("receipt_expected"),
            context.get("envelope_expected"),
            context.get("envelope_path"),
        ]
    )


def _validate_expected_context_receipts(receipts: list[dict], *, expected: bool) -> list[str]:
    if not expected and not receipts:
        return []
    if not receipts:
        return ["ContextReceipt is required for workflow close"]
    errors: list[str] = []
    for index, receipt in enumerate(receipts):
        check = validate_context_receipt(receipt)
        errors.extend(f"ContextReceipt[{index}]: {error}" for error in check.errors)
    return errors


def _validate_final_parity_evidence(root: Path, workflow: dict, run_id: str) -> list[str]:
    handoff_path = artifact_path(root, workflow, run_id, "handoff")
    if not handoff_path.exists():
        return ["final parity evidence is required in the handoff artifact before close"]
    text = handoff_path.read_text(encoding="utf-8")
    verification = _section(_body_without_frontmatter(text), "Verification").lower()
    if "final parity" not in verification and "parity evidence" not in verification:
        return ["final parity evidence is required in the handoff Verification section before close"]
    return []


def _body_without_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + len("\n---\n") :]


def _validate_traceability_shape(payload: dict, *, required: list[str], ref_arrays: list[str]) -> TraceabilityCheck:
    errors: list[str] = []
    for key in required:
        if key not in payload:
            errors.append(f"missing {key}")
    if payload.get("schema_version") != TRACEABILITY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TRACEABILITY_SCHEMA_VERSION}")
    for key in ref_arrays:
        refs = payload.get(key)
        if not isinstance(refs, list):
            errors.append(f"{key} must be a list")
            continue
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"{key}[{index}] must be an object")
                continue
            errors.extend(_validate_artifact_ref(ref, f"{key}[{index}]"))
    return TraceabilityCheck(ok=not errors, errors=errors)


def _validate_artifact_ref(ref: object, label: str) -> list[str]:
    if not isinstance(ref, dict):
        return [f"{label} must be an object"]
    errors: list[str] = []
    for ref_key in ["id", "path", "sha256"]:
        if not ref.get(ref_key):
            errors.append(f"{label}.{ref_key} is required")
    return errors


def _workflow_artifact_refs(root: Path, workflow: dict, run_id: str) -> list[dict]:
    refs = []
    for artifact in workflow.get("artifacts", {}):
        refs.append(
            _artifact_ref(
                root,
                artifact_path(root, workflow, run_id, artifact),
                f"artifact:{artifact}",
                kind="workflow-artifact",
            )
        )
    return refs


def _v_cycle_artifact_refs(root: Path, state: dict) -> list[dict]:
    run_id = str(state["run_id"])
    artifact_root = root / str(state["artifact_root"])
    paths = [artifact_root / filename for filename in STANDARD_ARTIFACTS.values()]
    paths.append(artifact_root / "v-trace.json")
    for stage in state.get("stages", []):
        stage_dir = artifact_root / "stages" / str(stage.get("id", ""))
        for artifact in stage.get("artifacts", []):
            paths.append(stage_dir / f"{artifact}.md")
        paths.append(stage_dir / "human-review-receipt.json")
    refs = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        rel = _display_path(root, path)
        refs.append(_artifact_ref(root, path, f"v-cycle-artifact:{run_id}:{rel}", kind="workflow-artifact"))
    return refs


def _evaluate_all_v_cycle_stage_gates(root: Path, state: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[str] = []
    stage_results = []
    run_id = str(state["run_id"])
    for stage in state.get("stages", []):
        stage_id = str(stage.get("id", ""))
        gate = check_v_cycle_stage(root, run_id, stage_id)
        stage_results.append(gate.to_dict())
        checked.extend(gate.checked_artifacts)
        errors.extend(gate.errors)
        warnings.extend(gate.warnings)
    return {
        "ok": not errors,
        "checked_artifacts": _dedupe(checked),
        "stage_results": stage_results,
        "errors": errors,
        "warnings": warnings,
    }


def _evaluate_v_cycle_close_gate(
    state: dict,
    current_gate,
    all_stage_gates: dict,
    artifact_refs: list[dict],
    context_receipts: list[dict],
) -> dict:
    receipt_errors = _validate_expected_context_receipts(context_receipts, expected=bool(context_receipts))
    digest_refs_ok = bool(artifact_refs) and all(ref.get("sha256") for ref in artifact_refs)
    errors: list[str] = []
    if state.get("status") != "complete":
        errors.append("workflow state status must be complete before close")
    if not current_gate.ok:
        errors.extend(current_gate.errors)
    if not all_stage_gates.get("ok"):
        errors.extend(all_stage_gates.get("errors", []))
    if not digest_refs_ok:
        errors.append("all V-cycle artifact references must include sha256 digests")
    errors.extend(receipt_errors)
    checks = [
        {
            "id": "v_cycle_current_stage_gate",
            "ok": current_gate.ok,
            "checked_artifacts": current_gate.checked_artifacts,
            "errors": current_gate.errors,
            "warnings": current_gate.warnings,
        },
        {
            "id": "v_cycle_all_stage_gates",
            "ok": bool(all_stage_gates.get("ok")),
            "checked_artifacts": list(all_stage_gates.get("checked_artifacts", [])),
            "errors": list(all_stage_gates.get("errors", [])),
            "warnings": list(all_stage_gates.get("warnings", [])),
        },
        {
            "id": "artifact_digest_references",
            "ok": digest_refs_ok,
            "evidence_refs": artifact_refs,
        },
        {
            "id": "context_receipt_presence",
            "ok": not receipt_errors,
            "expected": bool(context_receipts),
            "receipt_count": len(context_receipts),
            "errors": receipt_errors,
        },
    ]
    return {
        "ok": not errors and all(check["ok"] for check in checks),
        "checks": checks,
        "errors": _dedupe(errors),
    }


def _subagent_receipt_refs(root: Path, run_id: str) -> list[dict]:
    refs = []
    for item in load_persisted_subagent_lane_receipts(root, run_id):
        payload = item.get("payload", {})
        path = root / str(item.get("path", ""))
        work_order_path = path.with_suffix(".work-order.json")
        refs.append(
            {
                "receipt_id": payload.get("receipt_id", ""),
                "work_order_id": payload.get("work_order_id", ""),
                "agent_id": payload.get("agent_id", ""),
                "run_id": payload.get("run_id", ""),
                "stage_id": payload.get("stage_id", ""),
                "exit_status": payload.get("exit_status", ""),
                "output_digest": payload.get("output_digest", ""),
                "artifact_refs": list(payload.get("artifact_refs", [])) if isinstance(payload.get("artifact_refs"), list) else [],
                "tests_run": list(payload.get("tests_run", [])) if isinstance(payload.get("tests_run"), list) else [],
                "files_changed": list(payload.get("files_changed", [])) if isinstance(payload.get("files_changed"), list) else [],
                "receipt_ref": _artifact_ref(root, path, f"subagent:{payload.get('receipt_id', path.stem)}", kind="subagent-lane-receipt"),
                "work_order_ref": _artifact_ref(
                    root,
                    work_order_path,
                    f"subagent-work-order:{payload.get('work_order_id', path.stem)}",
                    kind="subagent-work-order",
                ),
            }
        )
    return refs


def _subagent_manifest_id_refs(subagents: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for item in subagents:
        for key in ["receipt_ref", "work_order_ref"]:
            ref = item.get(key)
            if isinstance(ref, dict):
                refs.append(ref)
    return refs


def _artifact_ref(root: Path, path: Path, artifact_id: str, *, kind: str = "file") -> dict:
    ref = {
        "id": artifact_id,
        "kind": kind,
        "path": _display_path(root, path),
    }
    if path.exists() and path.is_file():
        ref["sha256"] = _sha256_file(path)
        ref["size_bytes"] = path.stat().st_size
    return ref


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_id(prefix: str, refs: list[dict]) -> str:
    digest = sha256()
    for ref in refs:
        digest.update(str(ref.get("id", "")).encode("utf-8"))
        digest.update(str(ref.get("path", "")).encode("utf-8"))
        digest.update(str(ref.get("sha256", "")).encode("utf-8"))
    return f"{prefix}:{digest.hexdigest()[:16]}"


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _gate_to_dict(gate) -> dict:
    return {
        "ok": gate.ok,
        "run_id": gate.run_id,
        "workflow_id": gate.workflow_id,
        "step_id": gate.step_id,
        "checked_artifacts": gate.checked_artifacts,
        "errors": gate.errors,
    }


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
