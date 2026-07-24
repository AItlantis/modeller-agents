from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .vcycle import STANDARD_ARTIFACTS, is_v_cycle_run, load_v_cycle_state, record_v_cycle_subagent_receipt
from .workflow import DEFAULT_WORKFLOW, load_state, load_workflow


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass
class SubagentValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def build_subagent_work_order(
    root: Path,
    *,
    run_id: str,
    target_repository: str,
    task: str,
    agent_id: str,
    stage_id: str | None = None,
    target_path: str | None = None,
    allowed_paths: list[str] | None = None,
    required_tests: list[str] | None = None,
) -> dict:
    workflow_family, current_stage, artifact_root, required_artifacts = _current_workflow_context(root, run_id, stage_id)
    allowed = []
    if target_path:
        allowed.append(_normalise_relative_path(target_path))
    allowed.extend(_normalise_relative_path(path) for path in (allowed_paths or []))
    allowed.append(_normalise_relative_path(artifact_root))
    payload = {
        "schema_version": 1,
        "work_order_id": "",
        "created_at": _now(),
        "agent_id": agent_id,
        "task": task,
        "run_id": run_id,
        "workflow_family": workflow_family,
        "stage_id": current_stage,
        "target_repository": target_repository,
        "target_path": _normalise_relative_path(target_path) if target_path else "",
        "allowed_paths": _dedupe(allowed),
        "forbidden_actions": ["workflow advance", "workflow review", "git commit", "git push", "git reset"],
        "required_artifacts": required_artifacts,
        "required_tests": list(required_tests or []),
        "gate_commands": [["python", "-m", "modeller.cli", "workflow", "check", "--run-id", run_id]],
        "expected_result_schema": "schemas/subagent-lane-receipt.schema.json",
    }
    payload["work_order_id"] = "wo-" + _digest(payload)[:16]
    return payload


def validate_subagent_work_order(payload: dict) -> SubagentValidation:
    errors: list[str] = []
    required = [
        "schema_version",
        "work_order_id",
        "run_id",
        "workflow_family",
        "stage_id",
        "target_repository",
        "allowed_paths",
        "forbidden_actions",
        "required_artifacts",
        "required_tests",
        "gate_commands",
        "expected_result_schema",
    ]
    _require(payload, required, errors, "$")
    if payload.get("schema_version") != 1:
        errors.append("$.schema_version must be 1")
    for key in ["work_order_id", "run_id", "workflow_family", "stage_id", "target_repository"]:
        if key in payload and not _is_non_empty_string(payload.get(key)):
            errors.append(f"$.{key} must be a non-empty string")
    for key in ["run_id", "stage_id"]:
        if _is_non_empty_string(payload.get(key)) and not _is_safe_token(str(payload.get(key))):
            errors.append(f"$.{key} may only contain letters, numbers, dot, underscore, or dash")
    for key in ["allowed_paths", "forbidden_actions", "required_artifacts", "required_tests", "gate_commands"]:
        if key in payload and not isinstance(payload.get(key), list):
            errors.append(f"$.{key} must be a list")
    for path in payload.get("allowed_paths", []):
        if not _is_safe_relative_path(str(path)):
            errors.append(f"$.allowed_paths contains unsafe path {path!r}")
    return SubagentValidation(ok=not errors, errors=errors)


def validate_subagent_lane_receipt(work_order: dict, receipt: dict) -> SubagentValidation:
    errors: list[str] = []
    warnings: list[str] = []
    work_order_check = validate_subagent_work_order(work_order)
    errors.extend(f"work_order {error}" for error in work_order_check.errors)
    required = [
        "schema_version",
        "receipt_id",
        "work_order_id",
        "agent_id",
        "run_id",
        "stage_id",
        "files_read",
        "files_changed",
        "commands_run",
        "tests_run",
        "exit_status",
        "artifact_refs",
        "output_digest",
        "risks",
        "no_git_assertion",
        "attempted_workflow_advance",
    ]
    _require(receipt, required, errors, "$")
    if receipt.get("schema_version") != 1:
        errors.append("$.schema_version must be 1")
    for key in ["receipt_id", "work_order_id", "agent_id", "run_id", "stage_id"]:
        if key in receipt and not _is_non_empty_string(receipt.get(key)):
            errors.append(f"$.{key} must be a non-empty string")
    for key in ["receipt_id", "run_id", "stage_id"]:
        if _is_non_empty_string(receipt.get(key)) and not _is_safe_token(str(receipt.get(key))):
            errors.append(f"$.{key} may only contain letters, numbers, dot, underscore, or dash")
    for key in ["work_order_id", "run_id", "stage_id"]:
        if receipt.get(key) != work_order.get(key):
            errors.append(f"$.{key} must match work order {work_order.get(key)!r}")
    if receipt.get("agent_id") != work_order.get("agent_id"):
        warnings.append("$.agent_id differs from work order agent_id")
    if receipt.get("exit_status") not in {"complete", "blocked", "failed"}:
        errors.append("$.exit_status must be complete, blocked, or failed")
    if receipt.get("no_git_assertion") is not True:
        errors.append("$.no_git_assertion must be true")
    if receipt.get("attempted_workflow_advance") is not False:
        errors.append("$.attempted_workflow_advance must be false")
    output_digest = receipt.get("output_digest")
    if not isinstance(output_digest, str) or not SHA256_RE.match(output_digest):
        errors.append("$.output_digest must be sha256:<64 lowercase hex chars>")
    for key in ["files_read", "files_changed", "commands_run", "tests_run", "artifact_refs", "risks"]:
        if key in receipt and not isinstance(receipt.get(key), list):
            errors.append(f"$.{key} must be a list")
    allowed_paths = [_normalise_relative_path(path) for path in work_order.get("allowed_paths", [])]
    for changed in receipt.get("files_changed", []):
        changed_path = _normalise_relative_path(str(changed))
        if not _is_safe_relative_path(changed_path):
            errors.append(f"$.files_changed contains unsafe path {changed!r}")
        elif not _is_within_allowed_paths(changed_path, allowed_paths):
            errors.append(f"$.files_changed path {changed_path!r} is outside allowed_paths")
    forbidden = [str(action).lower() for action in work_order.get("forbidden_actions", [])]
    for command in _iter_commands(receipt.get("commands_run", [])):
        command_text = _command_text(command).lower()
        for action in forbidden:
            if action and action in command_text:
                errors.append(f"$.commands_run contains forbidden action {action!r}")
    return SubagentValidation(ok=not errors, errors=errors, warnings=warnings)


def persist_subagent_lane_receipt(root: Path, work_order: dict, receipt: dict) -> dict:
    check = validate_subagent_lane_receipt(work_order, receipt)
    if not check.ok:
        return {"ok": False, "errors": check.errors, "warnings": check.warnings}
    context_errors = _validate_receipt_workflow_context(root, work_order, receipt)
    if context_errors:
        return {"ok": False, "errors": context_errors, "warnings": check.warnings}
    stored = dict(receipt)
    stored["validated_at"] = _now()
    stored["work_order_ref"] = {
        "work_order_id": work_order["work_order_id"],
        "agent_id": work_order["agent_id"],
        "run_id": work_order["run_id"],
        "stage_id": work_order["stage_id"],
        "target_repository": work_order["target_repository"],
        "target_path": work_order.get("target_path", ""),
        "allowed_paths": list(work_order.get("allowed_paths", [])),
    }
    path = _lane_receipt_path(root, str(receipt["run_id"]), str(receipt["stage_id"]), str(receipt["receipt_id"]))
    work_order_path = path.with_suffix(".work-order.json")
    write_json(path, stored)
    write_json(work_order_path, work_order)
    if is_v_cycle_run(root, str(receipt["run_id"])):
        record_v_cycle_subagent_receipt(
            root,
            str(receipt["run_id"]),
            stage_id=str(receipt["stage_id"]),
            receipt_id=str(receipt["receipt_id"]),
            work_order_id=str(receipt["work_order_id"]),
            receipt_path=path,
            work_order_path=work_order_path,
            agent_id=str(receipt["agent_id"]),
            exit_status=str(receipt["exit_status"]),
            output_digest=str(receipt["output_digest"]),
        )
    return {
        "ok": True,
        "errors": [],
        "warnings": check.warnings,
        "stored_receipt": _display_path(root, path),
        "stored_work_order": _display_path(root, work_order_path),
    }


def load_persisted_subagent_lane_receipts(root: Path, run_id: str) -> list[dict]:
    store_root = root / ".modeller" / "runs" / run_id / "subagents"
    receipts: list[dict] = []
    if not store_root.exists():
        return receipts
    for path in sorted(store_root.glob("*/*.json"), key=lambda item: item.as_posix()):
        if path.name.endswith(".work-order.json"):
            continue
        try:
            payload = load_json(path)
        except json.JSONDecodeError:
            payload = {"receipt_id": path.stem, "errors": ["receipt is not valid JSON"]}
        receipts.append({"path": _display_path(root, path), "payload": payload})
    return receipts


def load_persisted_subagent_lane_receipt(
    root: Path,
    *,
    run_id: str,
    stage_id: str,
    receipt_id: str,
) -> tuple[dict, Path]:
    if not _is_safe_token(run_id) or not _is_safe_token(stage_id) or not _is_safe_token(receipt_id):
        raise ValueError("run_id, stage_id, and receipt_id must be safe path tokens")
    receipt_path = _lane_receipt_path(root, run_id, stage_id, receipt_id)
    return load_json(receipt_path), receipt_path


def ingest_subagent_lane_receipt_into_v_cycle_artifacts(
    root: Path,
    *,
    run_id: str,
    receipt_id: str,
    artifacts: list[str],
    stage_id: str | None = None,
) -> dict:
    if not artifacts:
        return {"ok": False, "errors": ["at least one --artifact is required"], "updated_artifacts": []}
    try:
        state = load_v_cycle_state(root, run_id)
    except Exception as exc:
        return {"ok": False, "errors": [f"V-cycle run is invalid: {exc}"], "updated_artifacts": []}
    current = state["stages"][int(state["current_stage_index"])]
    current_stage_id = str(current["id"])
    if stage_id and stage_id != current_stage_id:
        return {"ok": False, "errors": [f"stage_id must match current stage {current_stage_id!r}"], "updated_artifacts": []}
    try:
        receipt, receipt_path = load_persisted_subagent_lane_receipt(
            root,
            run_id=run_id,
            stage_id=current_stage_id,
            receipt_id=receipt_id,
        )
    except Exception as exc:
        return {"ok": False, "errors": [f"persisted lane receipt is invalid: {exc}"], "updated_artifacts": []}
    return ingest_persisted_subagent_lane_receipt_into_v_cycle_artifacts(
        root,
        receipt_path,
        artifacts=artifacts,
        stage_id=current_stage_id,
    )


def ingest_persisted_subagent_lane_receipt_into_v_cycle_artifacts(
    root: Path,
    receipt_path: Path,
    *,
    artifacts: list[str],
    stage_id: str | None = None,
) -> dict:
    receipt_path = receipt_path.resolve()
    try:
        receipt = load_json(receipt_path)
        work_order = load_json(receipt_path.with_suffix(".work-order.json"))
    except FileNotFoundError as exc:
        return {"ok": False, "errors": [f"missing persisted lane artifact: {exc.filename}"], "updated_artifacts": []}
    check = validate_subagent_lane_receipt(work_order, receipt)
    if not check.ok:
        return {"ok": False, "errors": check.errors, "warnings": check.warnings, "updated_artifacts": []}
    context_errors = _validate_receipt_workflow_context(root, work_order, receipt)
    if context_errors:
        return {"ok": False, "errors": context_errors, "warnings": check.warnings, "updated_artifacts": []}
    run_id = str(receipt["run_id"])
    receipt_stage_id = str(receipt["stage_id"])
    if stage_id and stage_id != receipt_stage_id:
        return {"ok": False, "errors": [f"receipt stage_id must match requested stage {stage_id!r}"], "updated_artifacts": []}
    if receipt.get("exit_status") != "complete":
        return {"ok": False, "errors": ["only complete lane receipts can be ingested into artifacts"], "updated_artifacts": []}
    if not is_v_cycle_run(root, run_id):
        return {"ok": False, "errors": ["lane artifact ingestion is only supported for V-cycle runs"], "updated_artifacts": []}
    if not _is_persisted_receipt_path(root, run_id, receipt_stage_id, receipt_path):
        return {
            "ok": False,
            "errors": ["receipt must be the persisted copy under .modeller/runs/<run-id>/subagents/<stage-id>/"],
            "updated_artifacts": [],
        }
    state = load_v_cycle_state(root, run_id)
    stage = _stage_state(state, receipt_stage_id)
    if str(state["stages"][int(state["current_stage_index"])]["id"]) != receipt_stage_id:
        return {"ok": False, "errors": ["receipt stage must be the current V-cycle stage"], "updated_artifacts": []}
    trace_errors = _require_receipt_in_trace(root, state, receipt, receipt_path, receipt_path.with_suffix(".work-order.json"))
    if trace_errors:
        return {"ok": False, "errors": trace_errors, "updated_artifacts": []}
    try:
        artifact_paths = _resolve_v_cycle_artifact_paths(root, state, stage, artifacts)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "updated_artifacts": []}
    if not artifact_paths:
        return {"ok": False, "errors": ["no artifacts resolved for ingestion"], "updated_artifacts": []}
    evidence = _lane_evidence_block(receipt, work_order, root=root, receipt_path=receipt_path)
    updated = []
    artifact_updates = []
    for path in artifact_paths:
        before_digest = _sha256_file(path)
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        after = _append_lane_evidence_to_markdown(before, evidence, receipt_id=str(receipt["receipt_id"]))
        if after != before:
            path.write_text(after, encoding="utf-8")
            rel = _display_path(root, path)
            after_digest = _sha256_file(path)
            updated.append(rel)
            artifact_updates.append({"path": rel, "before_sha256": before_digest, "after_sha256": after_digest})
    _record_v_cycle_lane_ingestion(root, state, receipt, artifact_updates)
    _touch_v_cycle_state(root, state)
    return {
        "ok": True,
        "errors": [],
        "warnings": check.warnings,
        "run_id": run_id,
        "stage_id": receipt_stage_id,
        "receipt_id": receipt["receipt_id"],
        "updated_artifacts": updated,
        "artifact_updates": artifact_updates,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _current_workflow_context(root: Path, run_id: str, requested_stage: str | None) -> tuple[str, str, str, list[str]]:
    if is_v_cycle_run(root, run_id):
        state = load_v_cycle_state(root, run_id)
        current = state["stages"][int(state["current_stage_index"])]
        stage_id = str(current["id"])
        if requested_stage and requested_stage != stage_id:
            raise ValueError(f"requested stage {requested_stage!r} does not match current stage {stage_id!r}")
        return (
            "v-cycle",
            stage_id,
            str(state["artifact_root"]),
            list(current.get("artifacts", [])),
        )
    workflow = load_workflow(root, DEFAULT_WORKFLOW)
    state = load_state(root, run_id, DEFAULT_WORKFLOW)
    step = workflow["steps"][int(state["current_step_index"])]
    step_id = str(step["id"])
    if requested_stage and requested_stage != step_id:
        raise ValueError(f"requested step {requested_stage!r} does not match current step {step_id!r}")
    return (
        str(workflow["workflow_id"]),
        step_id,
        str(state["artifact_root"]),
        list(step.get("required_artifacts", [])),
    )


def _validate_receipt_workflow_context(root: Path, work_order: dict, receipt: dict) -> list[str]:
    run_id = str(receipt.get("run_id", ""))
    stage_id = str(receipt.get("stage_id", ""))
    try:
        workflow_family, current_stage, _artifact_root, _required_artifacts = _current_workflow_context(
            root,
            run_id,
            stage_id,
        )
    except Exception as exc:
        return [f"workflow context is invalid: {exc}"]
    errors: list[str] = []
    if work_order.get("workflow_family") != workflow_family:
        errors.append(f"$.workflow_family must match active run {workflow_family!r}")
    if current_stage != stage_id:
        errors.append(f"$.stage_id must match active stage {current_stage!r}")
    return errors


def _is_persisted_receipt_path(root: Path, run_id: str, stage_id: str, receipt_path: Path) -> bool:
    expected_root = (root / ".modeller" / "runs" / run_id / "subagents" / stage_id).resolve()
    try:
        receipt_path.relative_to(expected_root)
    except ValueError:
        return False
    return receipt_path.suffix == ".json" and not receipt_path.name.endswith(".work-order.json")


def _stage_state(state: dict, stage_id: str) -> dict:
    for stage in state.get("stages", []):
        if stage.get("id") == stage_id:
            return stage
    raise KeyError(stage_id)


def _resolve_v_cycle_artifact_paths(root: Path, state: dict, stage: dict, artifact_ids: list[str]) -> list[Path]:
    artifact_root = root / str(state["artifact_root"])
    known: dict[str, Path] = {artifact_id: artifact_root / filename for artifact_id, filename in STANDARD_ARTIFACTS.items()}
    stage_dir = artifact_root / "stages" / str(stage["id"])
    for artifact in stage.get("artifacts", []):
        known[str(artifact)] = stage_dir / f"{artifact}.md"
    paths: list[Path] = []
    for artifact_id in artifact_ids:
        if artifact_id not in known:
            raise ValueError(f"unknown or inactive V-cycle artifact id {artifact_id!r}")
        path = known[artifact_id]
        if not path.exists():
            raise ValueError(f"artifact file does not exist for {artifact_id!r}: {_display_path(root, path)}")
        if path not in paths:
            paths.append(path)
    return paths


def _require_receipt_in_trace(root: Path, state: dict, receipt: dict, receipt_path: Path, work_order_path: Path) -> list[str]:
    trace_path = root / str(state["artifact_root"]) / "v-trace.json"
    trace = load_json(trace_path)
    receipts = trace.get("subagent_receipts")
    if not isinstance(receipts, list):
        return ["v-trace.json subagent_receipts must be a list before ingestion"]
    for item in receipts:
        if not isinstance(item, dict):
            continue
        if (
            item.get("receipt_id") == receipt.get("receipt_id")
            and item.get("work_order_id") == receipt.get("work_order_id")
            and item.get("stage_id") == receipt.get("stage_id")
        ):
            errors: list[str] = []
            expected = {
                "agent_id": receipt.get("agent_id"),
                "exit_status": receipt.get("exit_status"),
                "output_digest": receipt.get("output_digest"),
                "receipt_ref": _display_path(root, receipt_path),
                "work_order_ref": _display_path(root, work_order_path),
                "receipt_sha256": _sha256_file(receipt_path),
                "work_order_sha256": _sha256_file(work_order_path),
            }
            for key, value in expected.items():
                if item.get(key) != value:
                    errors.append(f"v-trace subagent receipt {key} does not match persisted lane receipt")
            return errors
    return ["persisted lane receipt is not represented in v-trace.json"]


def _record_v_cycle_lane_ingestion(root: Path, state: dict, receipt: dict, artifact_updates: list[dict]) -> None:
    trace_path = root / str(state["artifact_root"]) / "v-trace.json"
    trace = load_json(trace_path)
    ingestions = trace.setdefault("subagent_ingestions", [])
    if not isinstance(ingestions, list):
        ingestions = []
        trace["subagent_ingestions"] = ingestions
    receipt_id = str(receipt["receipt_id"])
    entry = {
        "receipt_id": receipt_id,
        "work_order_id": receipt["work_order_id"],
        "stage_id": receipt["stage_id"],
        "agent_id": receipt["agent_id"],
        "ingested_at": _now(),
        "artifact_updates": artifact_updates,
        "human_review_complete": False,
    }
    trace["subagent_ingestions"] = [
        item
        for item in ingestions
        if not (
            isinstance(item, dict)
            and item.get("receipt_id") == receipt_id
            and item.get("stage_id") == receipt.get("stage_id")
            and item.get("work_order_id") == receipt.get("work_order_id")
        )
    ]
    trace["subagent_ingestions"].append(entry)
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")


def _touch_v_cycle_state(root: Path, state: dict) -> None:
    now = _now()
    previous = str(state.get("updated_at", ""))
    if previous and now <= previous:
        try:
            previous_dt = datetime.fromisoformat(previous.replace("Z", "+00:00"))
            now = (previous_dt + timedelta(seconds=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    state["updated_at"] = now
    path = root / ".modeller" / "runs" / str(state["run_id"]) / "state.json"
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _lane_evidence_block(receipt: dict, work_order: dict, *, root: Path, receipt_path: Path) -> str:
    commands = [_command_text(command) for command in _iter_commands(receipt.get("commands_run", []))]
    tests = [_command_text(test) for test in receipt.get("tests_run", [])]
    lines = [
        f"- Evidence-source: subagent lane receipt `{receipt['receipt_id']}`.",
        f"- Work order: `{work_order['work_order_id']}` for `{work_order.get('task', '')}`.",
        f"- Target path: `{work_order.get('target_path', '') or 'not specified'}`.",
        f"- Files read: {', '.join(receipt.get('files_read', [])) or 'none recorded'}.",
        f"- Files changed: {', '.join(receipt.get('files_changed', [])) or 'none recorded'}.",
        f"- Commands run: {'; '.join(commands) or 'none recorded'}.",
        f"- Tests run: {'; '.join(tests) or 'none recorded'}.",
        f"- Output digest: `{receipt['output_digest']}`.",
        f"- Receipt reference: `{_display_path(root, receipt_path)}`.",
    ]
    risks = receipt.get("risks", [])
    if risks:
        lines.append(f"- Risks: {', '.join(str(risk) for risk in risks)}.")
    return "\n".join(lines)


def _append_lane_evidence_to_markdown(text: str, evidence: str, *, receipt_id: str) -> str:
    if not text.strip():
        text = "# V-Cycle Artifact\n\n## Evidence\n\nTBD\n\n## Decisions Or Outputs\n\nTBD\n\n## AI Usage Disclosure\n\nTBD\n"
    text = _append_to_section(text, "Evidence", f"### Subagent Lane Evidence: {receipt_id}\n\n{evidence}")
    text = _append_to_section(
        text,
        "Decisions Or Outputs",
        "Subagent evidence ingested; human review remains required before stage advance.",
    )
    text = _append_to_section(text, "Trace Links", f"### Subagent Lane Trace: {receipt_id}\n\n{evidence}")
    text = _append_to_section(
        text,
        "AI Usage Disclosure",
        "AI subagents contributed evidence through a validated lane receipt; no human approval was generated by AI.",
    )
    return text


def _append_to_section(text: str, heading: str, addition: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return text
    body_start = text.find("\n", start)
    if body_start == -1:
        return text
    next_heading = text.find("\n## ", body_start + 1)
    if next_heading == -1:
        section_body = text[body_start + 1 :]
        suffix = ""
    else:
        section_body = text[body_start + 1 : next_heading]
        suffix = text[next_heading:]
    if addition in section_body:
        return text
    existing = section_body.strip()
    if not existing or existing == "TBD":
        new_body = addition.rstrip()
    else:
        new_body = existing + "\n\n" + addition.rstrip()
    prefix = text[: body_start + 1]
    return prefix + "\n" + new_body + "\n" + suffix


def _require(payload: dict, keys: list[str], errors: list[str], prefix: str) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{prefix}.{key} is required")


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalise_relative_path(path: str | None) -> str:
    value = str(path or "").strip().strip("`'\"")
    value = value.replace("\\", "/")
    value = re.sub(r"/+", "/", value)
    return value.strip("/")


def _is_safe_relative_path(path: str) -> bool:
    value = _normalise_relative_path(path)
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    return ".." not in value.split("/")


def _is_safe_token(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value)) and value not in {".", ".."} and ".." not in value


def _is_within_allowed_paths(path: str, allowed_paths: list[str]) -> bool:
    for allowed in allowed_paths:
        prefix = allowed.rstrip("/")
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _command_text(command: object) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def _iter_commands(commands: object) -> list[object]:
    if not isinstance(commands, list):
        return []
    if all(isinstance(item, str) for item in commands):
        return [commands]
    return commands


def _digest(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _lane_receipt_path(root: Path, run_id: str, stage_id: str, receipt_id: str) -> Path:
    return root / ".modeller" / "runs" / run_id / "subagents" / stage_id / f"{receipt_id}.json"


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
