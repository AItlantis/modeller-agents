from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .workflow import (
    DEFAULT_WORKFLOW,
    _artifact_step,
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
        artifact_refs.append(_artifact_ref(root, root / "bundles" / f"{decision.bundle}.bundle.json", "bundle"))
    for rel_path in decision.reference_packs:
        artifact_refs.append(_artifact_ref(root, root / rel_path, f"reference-pack:{rel_path}", kind="reference-pack"))
    for rel_path in decision.knowledge_packs:
        artifact_refs.append(_artifact_ref(root, root / rel_path, f"knowledge-pack:{rel_path}", kind="knowledge-pack"))

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
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    state_ref = _artifact_ref(root, _state_path(root, workflow, run_id), "workflow-state", kind="workflow-state")
    workflow_ref = _artifact_ref(
        root,
        root / "method" / "workflows" / f"{workflow_id}.workflow.json",
        "workflow-definition",
        kind="workflow-definition",
    )
    artifact_refs = _workflow_artifact_refs(root, workflow, run_id)
    gate = check_current_step(root, run_id, workflow_id)
    close_gate = evaluate_close_gate(root, run_id, workflow_id=workflow_id)
    context_receipts = []
    if envelope_path is not None:
        context_receipts.append(build_context_receipt(root, envelope_path, run_id=run_id))

    current_step = workflow["steps"][state["current_step_index"]]
    return {
        "schema_version": TRACEABILITY_SCHEMA_VERSION,
        "manifest_id": _digest_id("run", [state_ref, workflow_ref, *artifact_refs]),
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
        "subagents": [],
        "outputs": [],
        "gates": {
            "current_step": _gate_to_dict(gate),
            "all_steps": evaluate_all_artifact_gates(root, run_id, workflow_id=workflow_id),
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


def evaluate_close_gate(root: Path, run_id: str, *, workflow_id: str = DEFAULT_WORKFLOW) -> dict:
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
    digest_refs_ok = bool(artifact_refs) and all(ref.get("sha256") for ref in artifact_refs)
    state_ref = _artifact_ref(root, _state_path(root, workflow, run_id), "workflow-state", kind="workflow-state")
    workflow_ref = _artifact_ref(
        root,
        root / "method" / "workflows" / f"{workflow_id}.workflow.json",
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
    return _validate_traceability_shape(
        receipt,
        required=["schema_version", "receipt_id", "algorithm_version", "retrieval_query", "selection", "retained_refs"],
        ref_arrays=["retained_refs"],
    )


def validate_run_manifest(manifest: dict) -> TraceabilityCheck:
    return _validate_traceability_shape(
        manifest,
        required=["schema_version", "manifest_id", "algorithm_version", "run", "workflow", "artifacts", "gates"],
        ref_arrays=["artifacts"],
    )


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
            for ref_key in ["id", "path", "sha256"]:
                if not ref.get(ref_key):
                    errors.append(f"{key}[{index}].{ref_key} is required")
    return TraceabilityCheck(ok=not errors, errors=errors)


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
