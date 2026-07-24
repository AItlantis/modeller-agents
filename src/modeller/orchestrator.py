from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .planning import ExecutionPlan, build_execution_plan, write_context_envelope
from .route import route_envelope, route_payload
from .subagents import build_subagent_work_order, validate_subagent_work_order, write_json
from .vcycle import check_v_cycle_current_stage, format_v_cycle_status, init_v_cycle_run, is_v_cycle_run, load_v_cycle_state


def orchestrate_prompt(
    root: Path,
    *,
    prompt: str,
    target_repository: str | None = None,
    run_id: str | None = None,
    target_path: str | None = None,
    agent_id: str = "subagent",
    invocation_mode: str = "stage",
    required_tests: list[str] | None = None,
    envelope_output: Path | None = None,
    work_order_output: Path | None = None,
) -> dict:
    initial_plan = build_execution_plan(
        root=root,
        prompt=prompt,
        target_repository=target_repository,
        run_id=run_id,
        envelope_output=envelope_output,
    )
    non_run_errors = _non_initialization_errors(initial_plan.tool_plan.blocked_by)
    route_errors = _non_initialization_errors(initial_plan.skill_plan.errors)
    if initial_plan.intent_draft.errors or route_errors or non_run_errors:
        return _payload(
            ok=False,
            status="blocked",
            plan=initial_plan,
            errors=list(initial_plan.intent_draft.errors)
            + route_errors
            + non_run_errors,
        )
    try:
        explicit_target_path = _normalise_relative_path(target_path) if target_path else None
    except ValueError as exc:
        return _payload(
            ok=False,
            status="blocked",
            plan=initial_plan,
            errors=[str(exc)],
            run_id=run_id,
        )

    workflow_required = bool(initial_plan.intent_draft.requires_workflow)
    workflow_family = initial_plan.intent_draft.workflow_family
    stage_id = initial_plan.intent_draft.v_cycle_stage
    if workflow_required and workflow_family != "v-cycle":
        return _payload(
            ok=False,
            status="blocked",
            plan=initial_plan,
            errors=["orchestrate currently supports automatic initialization for V-cycle workflow runs only"],
        )
    if invocation_mode not in {"stage", "paired-review"}:
        return _payload(
            ok=False,
            status="blocked",
            plan=initial_plan,
            errors=["orchestrate supports invocation_mode stage or paired-review"],
            run_id=run_id,
        )

    resolved_run_id = run_id
    state = None
    if workflow_required:
        if not stage_id:
            return _payload(
                ok=False,
                status="blocked",
                plan=initial_plan,
                errors=["V-cycle orchestration requires an inferred or explicit stage"],
            )
        resolved_run_id = run_id or _stable_run_id(initial_plan)
        if not is_v_cycle_run(root, resolved_run_id):
            state = init_v_cycle_run(
                root,
                resolved_run_id,
                invocation_mode=invocation_mode,
                requested_stage=stage_id,
            )
        else:
            state = load_v_cycle_state(root, resolved_run_id)

    envelope_path = envelope_output
    if envelope_path is None and resolved_run_id:
        envelope_path = root / ".modeller" / "runs" / resolved_run_id / "context-envelope.json"

    plan = build_execution_plan(
        root=root,
        prompt=prompt,
        target_repository=target_repository,
        run_id=resolved_run_id,
        envelope_output=envelope_path,
        gate_policy="bind-run" if workflow_required else None,
    )
    if explicit_target_path:
        plan.context_envelope.setdefault("intent", {})["target_path"] = explicit_target_path
        plan.intent_draft.target_path = explicit_target_path

    route = route_payload(root, plan.context_envelope, run_id=resolved_run_id)
    if route.errors:
        return _payload(
            ok=False,
            status="blocked",
            plan=plan,
            errors=list(route.errors),
            run_id=resolved_run_id,
            route=route.to_dict(),
            workflow_state=state,
        )
    if envelope_path is not None:
        write_context_envelope(envelope_path, plan.context_envelope)
    work_order_path = None
    work_order = None
    gate = None
    status_text = ""
    next_commands = []
    if workflow_required and route.ok and resolved_run_id:
        state = state or load_v_cycle_state(root, resolved_run_id)
        current_stage = state["stages"][int(state["current_stage_index"])]
        effective_target_path = target_path or plan.intent_draft.target_path
        work_order = build_subagent_work_order(
            root=root,
            run_id=resolved_run_id,
            target_repository=plan.intent_draft.target_repository,
            task=prompt,
            agent_id=agent_id,
            stage_id=str(current_stage["id"]),
            target_path=effective_target_path,
            required_tests=required_tests or [],
        )
        _add_standard_required_artifacts(work_order, plan)
        work_order_check = validate_subagent_work_order(work_order)
        if not work_order_check.ok:
            return _payload(
                ok=False,
                status="blocked",
                plan=plan,
                errors=work_order_check.errors,
                run_id=resolved_run_id,
                envelope_path=_display_path(root, envelope_path),
                route=route.to_dict(),
                workflow_state=state,
                work_order=work_order,
            )
        work_order_path = work_order_output or (
            root
            / ".modeller"
            / "runs"
            / resolved_run_id
            / "work-orders"
            / f"{current_stage['id']}-{agent_id}.json"
        )
        write_json(work_order_path, work_order)
        gate = check_v_cycle_current_stage(root, resolved_run_id)
        status_text = format_v_cycle_status(root, resolved_run_id)
        next_commands = _v_cycle_next_commands(root, resolved_run_id, envelope_path, work_order_path)

    errors = list(plan.intent_draft.errors) + list(plan.skill_plan.errors)
    status = "awaiting-user-approval" if not errors and workflow_required else ("ready" if not errors else "blocked")
    payload = _payload(
        ok=not errors,
        status=status,
        plan=plan,
        errors=errors,
        run_id=resolved_run_id,
        envelope_path=_display_path(root, envelope_path),
        route=route.to_dict(),
        workflow_state=state,
        workflow_status=status_text,
        current_gate=gate.to_dict() if gate else None,
        work_order_path=_display_path(root, work_order_path) if work_order_path else None,
        work_order=work_order,
        next_commands=next_commands,
    )
    if workflow_required and payload["ok"]:
        payload["approval_request"] = {
            "required": True,
            "message": "Review the run status and approve before executing the subagent work order.",
        }
    return payload


def format_orchestration(payload: dict) -> str:
    lines = [f"orchestration: {'OK' if payload.get('ok') else 'BLOCKED'}"]
    lines.append(f"status: {payload.get('status')}")
    intent = payload.get("intent", {})
    if intent:
        lines.append(f"target_repository: {intent.get('target_repository') or '<missing>'}")
        lines.append(f"requested_capability: {intent.get('requested_capability')}")
        if intent.get("workflow_family"):
            lines.append(f"workflow_family: {intent.get('workflow_family')}")
        if intent.get("v_cycle_stage"):
            lines.append(f"stage_id: {intent.get('v_cycle_stage')}")
    if payload.get("run_id"):
        lines.append(f"run_id: {payload['run_id']}")
    if payload.get("envelope_path"):
        lines.append(f"envelope: {payload['envelope_path']}")
    if payload.get("work_order_path"):
        lines.append(f"work_order: {payload['work_order_path']}")
    if payload.get("workflow_status"):
        lines.append("workflow_status:")
        lines.extend(f"  {line}" for line in str(payload["workflow_status"]).splitlines())
    gate = payload.get("current_gate")
    if isinstance(gate, dict):
        lines.append(f"current_gate: {'OK' if gate.get('ok') else 'FAIL'}")
        for error in gate.get("errors", []):
            lines.append(f"  - {error}")
    if payload.get("approval_request", {}).get("required"):
        lines.append(f"approval: {payload['approval_request']['message']}")
    if payload.get("errors"):
        lines.append("errors:")
        lines.extend(f"  - {error}" for error in payload["errors"])
    if payload.get("next_commands"):
        lines.append("next_commands:")
        lines.extend("  - " + " ".join(command) for command in payload["next_commands"])
    return "\n".join(lines)


def build_chat_handoff_prompt(root: Path, payload: dict) -> str:
    intent = payload.get("intent", {})
    plan = payload.get("plan", {})
    alignment = plan.get("alignment_contract", {})
    prompt = plan.get("intent_draft", {}).get("prompt") or intent.get("user_text") or ""
    lines = [
        "# modeller orchestrator handoff",
        "",
        "Use the `modeller:orchestrator` agent behavior for this session.",
        "",
        "## User request",
        "",
        prompt,
        "",
        "## Current orchestration state",
        "",
        f"- status: {payload.get('status')}",
        f"- target_repository: {intent.get('target_repository') or '<missing>'}",
        f"- requested_capability: {intent.get('requested_capability') or '<missing>'}",
    ]
    if intent.get("workflow_family"):
        lines.append(f"- workflow_family: {intent.get('workflow_family')}")
    if intent.get("v_cycle_stage"):
        lines.append(f"- stage_id: {intent.get('v_cycle_stage')}")
    if payload.get("run_id"):
        lines.append(f"- run_id: {payload.get('run_id')}")
    if alignment.get("source_root"):
        lines.append(f"- source_root: {alignment.get('source_root')}")
    if alignment.get("allowed_runtime_root"):
        lines.append(f"- allowed_runtime_root: {alignment.get('allowed_runtime_root')}")
    if payload.get("envelope_path"):
        lines.append(f"- context_envelope: {_absolute_display(root, payload.get('envelope_path'))}")
    if payload.get("work_order_path"):
        lines.append(f"- subagent_work_order: {_absolute_display(root, payload.get('work_order_path'))}")
    lines.extend(["", "## Required behavior", ""])
    if payload.get("work_order_path"):
        lines.extend(
            [
                "1. Read the context envelope and subagent work order before doing repository-local work.",
                "2. Report the selected intent, run id, current stage, gate policy, and current blockers to the human.",
                "3. Wait for explicit human approval before dispatching subagents or mutating files.",
                "4. Dispatch subagents only for the active run and current stage, using the generated work order as the contract.",
                "5. Treat subagent output as raw evidence until a valid lane receipt is persisted and ingested.",
                "6. Run the workflow gate after every lane receipt or artifact update.",
                "7. Request human review before advancing a stage; do not self-approve a stage.",
                "8. Advance only through `modeller.cli workflow advance` after the machine gate and human review pass.",
            ]
        )
    else:
        lines.extend(
            [
                "1. Work from `source_root`; use `allowed_runtime_root` only for modeller routing metadata.",
                "2. Treat this as read-only unless the human explicitly approves a mutation.",
                "3. Read the context envelope when one is listed, then inspect the requested repository content.",
                "4. Report the selected intent, source boundary, evidence read, findings, and any follow-up recommendations.",
                "5. Do not create workflow lane receipts, human-review receipts, or workflow advances for this read-only route.",
            ]
        )
    workflow_status = payload.get("workflow_status")
    if workflow_status:
        lines.extend(["", "## Workflow status", "", "```text", str(workflow_status), "```"])
    gate = payload.get("current_gate")
    if isinstance(gate, dict):
        lines.extend(["", "## Current gate", "", f"- ok: {gate.get('ok')}"])
        for error in gate.get("errors", []):
            lines.append(f"- blocker: {error}")
    next_commands = payload.get("next_commands") or []
    if next_commands:
        lines.extend(["", "## Deterministic commands", ""])
        for command in next_commands:
            lines.append("```powershell")
            lines.append(" ".join(command))
            lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _payload(
    *,
    ok: bool,
    status: str,
    plan: ExecutionPlan,
    errors: list[str],
    run_id: str | None = None,
    envelope_path: str | None = None,
    route: dict | None = None,
    workflow_state: dict | None = None,
    workflow_status: str = "",
    current_gate: dict | None = None,
    work_order_path: str | None = None,
    work_order: dict | None = None,
    next_commands: list[list[str]] | None = None,
) -> dict:
    draft = plan.intent_draft
    return {
        "ok": ok,
        "status": status,
        "intent": draft.to_dict(),
        "run_id": run_id,
        "envelope_path": envelope_path,
        "route": route,
        "workflow_state": workflow_state,
        "workflow_status": workflow_status,
        "current_gate": current_gate,
        "work_order_path": work_order_path,
        "work_order": work_order,
        "next_commands": next_commands or [],
        "errors": errors,
        "plan": plan.to_dict(),
    }


def _stable_run_id(plan: ExecutionPlan) -> str:
    draft = plan.intent_draft
    parts = [
        draft.intent_classification.primary_intent if draft.intent_classification else draft.requested_capability,
        draft.target_repository,
        draft.v_cycle_stage or "workflow",
    ]
    stem = "-".join(_slug(part) for part in parts if part)
    if not stem:
        stem = "orchestrate"
    digest = _stable_digest(json.dumps(draft.to_dict(), sort_keys=True))[:10]
    run_id = f"{stem[:48].strip('-')}-{digest}"
    return run_id[:64]


def _non_initialization_errors(errors: list[str]) -> list[str]:
    allowed_fragments = [
        "run_id",
        "active workflow run",
        "workflow run",
        "not found or not initialized",
        "no envelope_output",
    ]
    return [
        error
        for error in errors
        if not any(fragment in error for fragment in allowed_fragments)
    ]


def _add_standard_required_artifacts(work_order: dict, plan: ExecutionPlan) -> None:
    classification = plan.intent_draft.intent_classification
    if classification is None or classification.primary_intent != "brief-and-recon":
        return
    required = list(work_order.get("required_artifacts", []))
    for artifact in ["brief", "recon"]:
        if artifact not in required:
            required.append(artifact)
    work_order["required_artifacts"] = required


def _stable_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._").lower()
    return slug or "run"


def _normalise_relative_path(value: str) -> str:
    cleaned = value.replace("\\", "/")
    cleaned = re.sub(r"/+", "/", cleaned).strip("/")
    if (
        not cleaned
        or cleaned.startswith("/")
        or re.match(r"^[A-Za-z]:", cleaned)
        or cleaned.startswith("../")
        or "/../" in cleaned
        or cleaned == ".."
    ):
        raise ValueError("target_path must be a safe relative path")
    return cleaned


def _v_cycle_next_commands(root: Path, run_id: str, envelope_path: Path, work_order_path: Path) -> list[list[str]]:
    return [
        ["python", "-m", "modeller.cli", "route", "--root", str(root), "--envelope", str(envelope_path), "--run-id", run_id],
        ["python", "-m", "modeller.cli", "workflow", "--root", str(root), "lane-receipt", "--work-order", str(work_order_path), "--receipt", "<lane-receipt.json>"],
        ["python", "-m", "modeller.cli", "workflow", "--root", str(root), "check", "--run-id", run_id],
        ["python", "-m", "modeller.cli", "workflow", "--root", str(root), "request-review", "--run-id", run_id, "--provider", "receipt-file", "--receipt", "<human-review.json>"],
        ["python", "-m", "modeller.cli", "workflow", "--root", str(root), "advance", "--run-id", run_id],
    ]


def _display_path(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _absolute_display(root: Path, path: str | None) -> str:
    if not path:
        return ""
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((root / candidate).resolve())
