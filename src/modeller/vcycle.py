from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime import runtime_path, runtime_relative_path
from .workflow import RUN_ID_PATTERN


VALID_MODES = {"full", "stage", "paired-review"}
HUMAN_DECISIONS = {"approved", "approved-with-reservations", "changes-requested", "rejected"}
APPROVING_DECISIONS = {"approved", "approved-with-reservations"}
SHA256_RE = re.compile(r"^sha256:[a-fA-F0-9]{64}$")
STANDARD_ARTIFACTS = {
    "brief": "BRIEF.md",
    "recon": "RECON.md",
    "workflow-plan": "workflow-plan.md",
    "machine-evidence": "machine-evidence.md",
    "handoff": "handoff.md",
}


@dataclass
class VCycleCheck:
    run_id: str
    ok: bool
    stage_id: str | None = None
    artifact_digest: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "run_id": self.run_id,
            "stage_id": self.stage_id,
            "artifact_digest": self.artifact_digest,
            "checked_artifacts": self.checked_artifacts,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def format(self) -> str:
        lines = [f"v-cycle gate: {'OK' if self.ok else 'FAIL'}"]
        lines.append(f"run_id: {self.run_id}")
        if self.stage_id:
            lines.append(f"stage_id: {self.stage_id}")
        if self.artifact_digest:
            lines.append(f"artifact_digest: {self.artifact_digest}")
        lines.append("checked_artifacts:")
        lines.extend(f"  - {artifact}" for artifact in self.checked_artifacts)
        if self.warnings:
            lines.append("warnings:")
            lines.extend(f"  - {warning}" for warning in self.warnings)
        if self.errors:
            lines.append("errors:")
            lines.extend(f"  - {error}" for error in self.errors)
        return "\n".join(lines)


def load_v_cycle_family(root: Path) -> dict:
    return _load_yaml(runtime_path(root, "method", "workflows", "v-cycle.family.yaml"))


def load_v_cycle_stages(root: Path) -> list[dict]:
    payload = _load_yaml(runtime_path(root, "method", "workflows", "v-cycle.stages.yaml"))
    stages = payload.get("stages", [])
    if not isinstance(stages, list):
        raise ValueError("v-cycle.stages.yaml must contain a stages list")
    return sorted([stage for stage in stages if isinstance(stage, dict)], key=lambda s: int(s.get("order", 0)))


def load_v_cycle_policy(root: Path) -> dict:
    return _load_yaml(runtime_path(root, "method", "policies", "v-cycle-vigilance.yaml"))


def list_v_cycle_workflows(root: Path) -> list[dict]:
    family = load_v_cycle_family(root)
    stages = load_v_cycle_stages(root)
    return [
        {
            "workflow_id": "v-cycle",
            "workflow_family": "v-cycle",
            "name": str(family.get("name", "Project V-Cycle")),
            "status": str(family.get("status", "")),
            "skill": str(family.get("skill", "v-cycle")),
            "invocation_modes": list(family.get("invocation_modes", [])),
            "stage_count": len(stages),
            "stages": [_stage_summary(stage) for stage in stages],
        }
    ]


def recommend_v_cycle_stage(root: Path, prompt: str) -> dict:
    stages = load_v_cycle_stages(root)
    lowered = prompt.lower()
    keyword_map = {
        "opportunity-analysis": ["opportunity", "business case", "value", "roi", "benefit"],
        "needs-analysis": ["need", "stakeholder", "workshop", "baseline"],
        "functional-specification": ["functional", "requirement", "specification", "spec"],
        "general-design": ["architecture", "general design", "option", "interface"],
        "detailed-design": ["detailed design", "technical design", "unit test plan"],
        "implementation": ["implement", "code", "refactor", "build"],
        "unit-testing": ["unit test", "pytest", "coverage"],
        "integration-testing": ["integration", "degraded", "scenario"],
        "system-validation": ["system validation", "regression", "validation"],
        "acceptance-qualification": ["acceptance", "sign-off", "reservation"],
        "deployment": ["deploy", "rollback", "cutover", "release"],
        "operations-rex": ["operations", "rex", "incident", "retrospective"],
        "project-governance": ["governance", "planning", "status", "risk", "decision log"],
    }
    scores: dict[str, int] = {}
    for stage in stages:
        stage_id = str(stage.get("id", ""))
        score = 0
        for term in keyword_map.get(stage_id, []):
            if term in lowered:
                score += 1
        if stage_id in lowered:
            score += 3
        scores[stage_id] = score
    selected_id = max(scores, key=lambda key: (scores[key], -_stage_order(stages, key)))
    if scores[selected_id] == 0:
        selected_id = "project-governance"
    selected = _stage_by_id(stages, selected_id)
    return {
        "workflow_family": "v-cycle",
        "invocation_mode": "stage",
        "requested_stage": selected_id,
        "confidence": "keyword" if scores[selected_id] else "fallback",
        "stage": _stage_summary(selected),
    }


def init_v_cycle_run(
    root: Path,
    run_id: str,
    *,
    invocation_mode: str = "stage",
    requested_stage: str | None = None,
) -> dict:
    _validate_run_id(run_id)
    if invocation_mode not in VALID_MODES:
        raise ValueError(f"invocation_mode must be one of {sorted(VALID_MODES)}")
    stages = load_v_cycle_stages(root)
    selected = _select_stages(stages, invocation_mode, requested_stage)
    run_root = _run_root(root, run_id)
    artifact_root = _artifact_root(root, run_id)
    artifact_root.mkdir(parents=True, exist_ok=True)
    for name, filename in STANDARD_ARTIFACTS.items():
        _write_if_missing(
            artifact_root / filename,
            _standard_artifact_template(name=name, run_id=run_id, selected=selected, mode=invocation_mode),
        )
    _write_if_missing(artifact_root / "v-trace.json", _trace_template(run_id, selected))

    stage_states = []
    for index, stage in enumerate(selected):
        stage_dir = artifact_root / "stages" / str(stage["id"])
        stage_dir.mkdir(parents=True, exist_ok=True)
        for artifact in stage.get("artifacts", []):
            _write_if_missing(stage_dir / f"{artifact}.md", _stage_artifact_template(run_id, stage, artifact))
        _write_if_missing(stage_dir / "human-review-receipt.json", _receipt_template(run_id, stage))
        stage_states.append(
            {
                "id": str(stage["id"]),
                "status": "draft" if index == 0 else "pending",
                "branch": str(stage.get("branch", "")),
                "vigilance_level": str(stage.get("vigilance_level", "")),
                "human_owner_roles": list(stage.get("human_owner_roles", [])),
                "artifacts": list(stage.get("artifacts", [])),
                "dependencies": list(stage.get("dependencies", [])),
                "paired_stage": stage.get("paired_stage"),
                "review": {"status": "missing", "receipt_path": "", "artifact_digest": ""},
                "prerequisites": _prerequisite_audit(stage, selected, invocation_mode),
            }
        )
    state = {
        "schema_version": "0.1",
        "workflow_family": "v-cycle",
        "run_id": run_id,
        "invocation_mode": invocation_mode,
        "requested_stage": requested_stage or None,
        "selected_stages": [str(stage["id"]) for stage in selected],
        "current_stage_index": 0,
        "status": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "artifact_root": runtime_relative_path(root, artifact_root),
        "stages": stage_states,
    }
    run_root.mkdir(parents=True, exist_ok=True)
    _state_path(root, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def is_v_cycle_run(root: Path, run_id: str) -> bool:
    try:
        state = load_v_cycle_state(root, run_id)
    except Exception:
        return False
    return state.get("workflow_family") == "v-cycle"


def load_v_cycle_state(root: Path, run_id: str) -> dict:
    _validate_run_id(run_id)
    return json.loads(_state_path(root, run_id).read_text(encoding="utf-8"))


def format_v_cycle_status(root: Path, run_id: str) -> str:
    state = load_v_cycle_state(root, run_id)
    current = _current_stage_state(state)
    lines = ["workflow_family: v-cycle", f"run_id: {run_id}", f"status: {state['status']}"]
    lines.append(f"invocation_mode: {state['invocation_mode']}")
    lines.append(f"current_stage: {current['id']} ({current['status']})")
    lines.append("stages:")
    for stage in state["stages"]:
        review = stage.get("review", {})
        lines.append(f"  - {stage['id']}: {stage['status']} review={review.get('status', 'missing')}")
    return "\n".join(lines)


def check_v_cycle_current_stage(root: Path, run_id: str) -> VCycleCheck:
    state = load_v_cycle_state(root, run_id)
    stage = _current_stage_state(state)
    return check_v_cycle_stage(root, run_id, str(stage["id"]))


def check_v_cycle_stage(root: Path, run_id: str, stage_id: str) -> VCycleCheck:
    state = load_v_cycle_state(root, run_id)
    stage = _state_stage(state, stage_id)
    artifact_paths = _stage_material_artifact_paths(root, state, stage)
    checked = [runtime_relative_path(root, path) for path in artifact_paths]
    errors: list[str] = []
    warnings: list[str] = []
    for path in artifact_paths:
        if not path.exists():
            errors.append(f"missing artifact {runtime_relative_path(root, path)}")
        elif path.suffix.lower() == ".md" and _contains_placeholder(path.read_text(encoding="utf-8")):
            errors.append(f"artifact still contains TBD placeholder: {runtime_relative_path(root, path)}")
    trace_path = _artifact_root(root, run_id) / "v-trace.json"
    errors.extend(_validate_trace(trace_path, state, stage_id))
    errors.extend(_validate_required_subagent_receipts(root, state, stage))
    for prereq in stage.get("prerequisites", []):
        if prereq.get("status") == "missing":
            warnings.append(
                f"missing prerequisite {prereq.get('stage_id')} is recorded; do not invent its baseline"
            )
    digest = stage_artifact_digest(root, state, stage)
    review = stage.get("review", {})
    if review.get("status") in {"approved", "approved-with-reservations", "changes-requested", "rejected"}:
        if review.get("artifact_digest") != digest:
            errors.append("human review receipt is invalidated by current artifact digest")
    else:
        errors.append("human review receipt is required before stage advance")
    return VCycleCheck(
        run_id=run_id,
        stage_id=stage_id,
        ok=not errors,
        errors=errors,
        warnings=warnings,
        checked_artifacts=checked,
        artifact_digest=digest,
    )


def advance_v_cycle(root: Path, run_id: str) -> VCycleCheck:
    state = load_v_cycle_state(root, run_id)
    stage = _current_stage_state(state)
    check = check_v_cycle_stage(root, run_id, str(stage["id"]))
    closed_stage_errors = _validate_closed_stage_reviews(root, state, current_stage_id=str(stage["id"]))
    if closed_stage_errors:
        check.errors.extend(closed_stage_errors)
        check.ok = False
    if not check.ok:
        stage["status"] = "awaiting-human-review"
        state["updated_at"] = _now()
        _state_path(root, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return check
    review_status = stage.get("review", {}).get("status")
    if review_status not in APPROVING_DECISIONS:
        check.errors.append(f"human review decision {review_status!r} does not approve stage advance")
        check.ok = False
        return check
    stage["status"] = "closed"
    index = int(state["current_stage_index"])
    if index + 1 >= len(state["stages"]):
        state["status"] = "complete"
    else:
        state["current_stage_index"] = index + 1
        state["stages"][index + 1]["status"] = "draft"
    state["updated_at"] = _now()
    _state_path(root, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return check


def review_v_cycle_stage(root: Path, run_id: str, receipt_path: Path) -> dict:
    state = load_v_cycle_state(root, run_id)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [f"receipt is not valid JSON: {exc}"], "artifact_digest": ""}
    if not isinstance(receipt, dict):
        return {"ok": False, "errors": ["receipt must be a JSON object"], "artifact_digest": ""}
    errors = _validate_receipt_shape(receipt)
    stage_id = str(receipt.get("stage_id", ""))
    if receipt.get("run_id") != run_id:
        errors.append(f"receipt run_id must be {run_id!r}")
    try:
        stage = _state_stage(state, stage_id)
    except KeyError:
        errors.append(f"receipt stage_id {stage_id!r} is not part of this run")
        stage = None
    digest = ""
    if stage is not None:
        digest = stage_artifact_digest(root, state, stage)
        if receipt.get("artifact_digest") != digest:
            errors.append("receipt artifact_digest does not match current stage artifact digest")
        roles = set(stage.get("human_owner_roles", []))
        reviewer = receipt.get("reviewer", {}) if isinstance(receipt.get("reviewer"), dict) else {}
        if roles and reviewer.get("role") not in roles:
            errors.append(
                f"reviewer.role must be one of the stage human owner roles: {', '.join(sorted(roles))}"
            )
        reviewer_id = str(reviewer.get("id", ""))
        if reviewer_id and reviewer_id in _stage_subagent_actor_ids(root, state, stage):
            errors.append("reviewer.id must not match a subagent or work-order agent for this stage")
    if errors:
        return {"ok": False, "errors": errors, "artifact_digest": digest}
    assert stage is not None
    dst = _artifact_root(root, run_id) / "stages" / stage_id / "human-review-receipt.json"
    dst.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    stage["review"] = {
        "status": receipt["decision"],
        "receipt_path": runtime_relative_path(root, dst),
        "artifact_digest": receipt["artifact_digest"],
        "reviewed_at": receipt["reviewed_at"],
        "reviewer": receipt["reviewer"],
    }
    stage["status"] = "approved" if receipt["decision"] in APPROVING_DECISIONS else "rework"
    state["updated_at"] = _now()
    _state_path(root, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "stage_id": stage_id, "artifact_digest": digest, "receipt": runtime_relative_path(root, dst)}


def build_human_review_receipt(
    root: Path,
    run_id: str,
    *,
    stage_id: str | None,
    reviewer_id: str,
    reviewer_role: str,
    decision: str,
    review_type: str = "approval",
    reservations: list[str] | None = None,
    accepted_risks: list[str] | None = None,
) -> dict:
    state = load_v_cycle_state(root, run_id)
    stage = _state_stage(state, stage_id) if stage_id else _current_stage_state(state)
    digest = stage_artifact_digest(root, state, stage)
    artifact_refs = [runtime_relative_path(root, path) for path in _stage_review_artifact_paths(root, state, stage)]
    return {
        "review_id": f"review-{run_id}-{stage['id']}-{_review_digest(run_id, str(stage['id']), reviewer_id, digest)}",
        "run_id": run_id,
        "stage_id": stage["id"],
        "artifact_refs": artifact_refs,
        "artifact_digest": digest,
        "review_type": review_type,
        "reviewer": {"id": reviewer_id, "role": reviewer_role, "actor_type": "human"},
        "decision": decision,
        "reservations": list(reservations or []),
        "accepted_risks": list(accepted_risks or []),
        "reviewed_at": _now(),
    }


def write_human_review_receipt(root: Path, run_id: str, receipt: dict, *, label: str = "human-review") -> Path:
    _validate_run_id(run_id)
    receipt_id = str(receipt.get("review_id", label))
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", receipt_id).strip(".-") or label
    path = _run_root(root, run_id) / "human-reviews" / f"{safe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return path


def apply_human_review_provider(
    root: Path,
    run_id: str,
    *,
    provider: str,
    receipt_path: Path | None = None,
    fixture_metadata_path: Path | None = None,
    reviewer_id: str | None = None,
    reviewer_role: str | None = None,
    decision: str = "approved",
    review_type: str = "approval",
    allow_test_fixture: bool = False,
    stage_id: str | None = None,
) -> dict:
    if provider == "receipt-file":
        if receipt_path is None:
            return {"ok": False, "errors": ["--receipt is required for receipt-file provider"]}
        return review_v_cycle_stage(root, run_id, receipt_path)
    if provider != "test-fixture":
        return {"ok": False, "errors": [f"unknown human review provider {provider!r}"]}
    state = load_v_cycle_state(root, run_id)
    if not allow_test_fixture:
        return {"ok": False, "errors": ["test-fixture provider requires --allow-test-fixture"]}
    stage = _state_stage(state, stage_id) if stage_id else _current_stage_state(state)
    fixture_errors = validate_test_fixture_review_allowed(
        root,
        run_id,
        str(stage["id"]),
        allow_flag=allow_test_fixture,
        fixture_metadata_path=fixture_metadata_path,
    )
    if fixture_errors:
        return {"ok": False, "errors": fixture_errors}
    if not reviewer_id or not reviewer_role:
        return {"ok": False, "errors": ["--reviewer-id and --reviewer-role are required for test-fixture provider"]}
    receipt = build_human_review_receipt(
        root,
        run_id,
        stage_id=stage_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        decision=decision,
        review_type=review_type,
    )
    path = write_human_review_receipt(root, run_id, receipt, label="test-fixture-review")
    payload = review_v_cycle_stage(root, run_id, path)
    payload["provider"] = "test-fixture"
    payload["receipt_file"] = runtime_relative_path(root, path)
    return payload


def validate_test_fixture_review_allowed(
    root: Path,
    run_id: str,
    stage_id: str,
    *,
    allow_flag: bool,
    fixture_metadata_path: Path | None,
) -> list[str]:
    errors: list[str] = []
    if not allow_flag:
        errors.append("test-fixture provider requires --allow-test-fixture")
    if fixture_metadata_path is None:
        errors.append("--fixture-metadata is required for test-fixture provider")
        return errors
    metadata_path = fixture_metadata_path
    if not metadata_path.is_absolute():
        metadata_path = root / metadata_path
    metadata_path = metadata_path.resolve()
    run_root = (_run_root(root, run_id)).resolve()
    try:
        metadata_path.relative_to(run_root)
    except ValueError:
        errors.append("fixture metadata must be under .modeller/runs/<run-id>/")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        errors.append(f"fixture metadata not found: {fixture_metadata_path}")
        return errors
    except json.JSONDecodeError as exc:
        errors.append(f"fixture metadata is not valid JSON: {exc}")
        return errors
    expected = {
        "run_id": run_id,
        "stage_id": stage_id,
        "provider": "test-fixture",
        "fixture_run": True,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            errors.append(f"fixture metadata {key} must be {value!r}")
    return errors


def record_v_cycle_subagent_receipt(
    root: Path,
    run_id: str,
    *,
    stage_id: str,
    receipt_id: str,
    work_order_id: str,
    receipt_path: Path,
    work_order_path: Path,
    agent_id: str,
    exit_status: str,
    output_digest: str,
) -> None:
    state = load_v_cycle_state(root, run_id)
    _state_stage(state, stage_id)
    trace_path = _artifact_root(root, run_id) / "v-trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    entries = trace.setdefault("subagent_receipts", [])
    if not isinstance(entries, list):
        entries = []
        trace["subagent_receipts"] = entries
    entry = {
        "receipt_id": receipt_id,
        "work_order_id": work_order_id,
        "stage_id": stage_id,
        "agent_id": agent_id,
        "exit_status": exit_status,
        "output_digest": output_digest,
        "receipt_ref": runtime_relative_path(root, receipt_path),
        "receipt_sha256": _sha256_file(receipt_path),
        "work_order_ref": runtime_relative_path(root, work_order_path),
        "work_order_sha256": _sha256_file(work_order_path),
    }
    trace["subagent_receipts"] = [
        item
        for item in entries
        if not (
            isinstance(item, dict)
            and item.get("receipt_id") == receipt_id
            and item.get("stage_id") == stage_id
            and item.get("work_order_id") == work_order_id
        )
    ]
    trace["subagent_receipts"].append(entry)
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")


def trace_check_v_cycle(root: Path, run_id: str) -> VCycleCheck:
    state = load_v_cycle_state(root, run_id)
    errors = _validate_trace(_artifact_root(root, run_id) / "v-trace.json", state, None)
    checked = [runtime_relative_path(root, _artifact_root(root, run_id) / "v-trace.json")]
    return VCycleCheck(run_id=run_id, stage_id=None, ok=not errors, errors=errors, checked_artifacts=checked)


def stage_artifact_digest(root: Path, state: dict, stage: dict) -> str:
    digest = hashlib.sha256()
    for path in _stage_review_artifact_paths(root, state, stage):
        digest.update(runtime_relative_path(root, path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.exists() else b"<missing>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("PyYAML is required to load V-cycle workflow assets") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def _select_stages(stages: list[dict], mode: str, requested_stage: str | None) -> list[dict]:
    if mode == "full":
        return list(stages)
    if not requested_stage:
        raise ValueError("--stage is required for v-cycle stage and paired-review modes")
    requested = _stage_by_id(stages, requested_stage)
    if mode == "stage":
        return [requested]
    paired_id = requested.get("paired_stage")
    if not paired_id:
        return [requested]
    return [requested, _stage_by_id(stages, str(paired_id))]


def _stage_by_id(stages: list[dict], stage_id: str) -> dict:
    for stage in stages:
        if stage.get("id") == stage_id:
            return stage
    raise ValueError(f"unknown V-cycle stage {stage_id!r}")


def _stage_order(stages: list[dict], stage_id: str) -> int:
    for stage in stages:
        if stage.get("id") == stage_id:
            return int(stage.get("order", 0))
    return 999


def _stage_summary(stage: dict) -> dict:
    return {
        "id": str(stage.get("id", "")),
        "branch": str(stage.get("branch", "")),
        "order": int(stage.get("order", 0)),
        "vigilance_level": str(stage.get("vigilance_level", "")),
        "human_owner_roles": list(stage.get("human_owner_roles", [])),
        "artifacts": list(stage.get("artifacts", [])),
        "dependencies": list(stage.get("dependencies", [])),
        "paired_stage": stage.get("paired_stage"),
    }


def _prerequisite_audit(stage: dict, selected: list[dict], mode: str) -> list[dict]:
    selected_ids = {str(item.get("id", "")) for item in selected}
    audit = []
    for dep in stage.get("dependencies", []):
        status = "available" if mode == "full" and dep in selected_ids else "missing"
        audit.append({"stage_id": dep, "status": status})
    return audit


def _standard_artifact_template(name: str, run_id: str, selected: list[dict], mode: str) -> str:
    stages = ", ".join(str(stage["id"]) for stage in selected)
    return (
        f"# {name.replace('-', ' ').title()}\n\n"
        f"run_id: {run_id}\n"
        f"workflow_family: v-cycle\n"
        f"invocation_mode: {mode}\n"
        f"selected_stages: {stages}\n\n"
        "## Evidence\n\nTBD\n\n"
        "## Decisions Or Outputs\n\nTBD\n\n"
        "## AI Usage Disclosure\n\nTBD\n"
    )


def _stage_artifact_template(run_id: str, stage: dict, artifact: str) -> str:
    return (
        f"# {artifact.replace('-', ' ').title()}\n\n"
        f"run_id: {run_id}\n"
        f"stage_id: {stage['id']}\n"
        f"vigilance_level: {stage.get('vigilance_level')}\n"
        f"human_owner_roles: {', '.join(stage.get('human_owner_roles', []))}\n\n"
        "## Evidence\n\nTBD\n\n"
        "## Decisions Or Outputs\n\nTBD\n\n"
        "## Trace Links\n\nTBD\n\n"
        "## AI Usage Disclosure\n\nTBD\n"
    )


def _trace_template(run_id: str, selected: list[dict]) -> str:
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "workflow_family": "v-cycle",
        "selected_stages": [stage["id"] for stage in selected],
        "nodes": [],
        "links": [],
        "subagent_receipts": [],
        "gaps": [
            {
                "stage_id": stage["id"],
                "gap_type": "prerequisite-audit",
                "status": "pending",
                "description": "Prerequisites must be classified before human review.",
            }
            for stage in selected
            if stage.get("dependencies")
        ],
        "ai_usage": {"used": True, "human_review_complete": False},
    }
    return json.dumps(payload, indent=2) + "\n"


def _receipt_template(run_id: str, stage: dict) -> str:
    payload = {
        "status": "missing-human-review",
        "run_id": run_id,
        "stage_id": stage["id"],
        "message": "Replace this file through `modeller workflow review --receipt <receipt.json>`.",
    }
    return json.dumps(payload, indent=2) + "\n"


def _validate_trace(path: Path, state: dict, stage_id: str | None) -> list[str]:
    if not path.exists():
        return [f"missing trace artifact {runtime_relative_path(path.parent.parent.parent, path)}"]
    try:
        trace = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"v-trace.json is not valid JSON: {exc}"]
    errors = []
    if trace.get("run_id") != state.get("run_id"):
        errors.append("v-trace.json run_id must match workflow state")
    if not isinstance(trace.get("nodes"), list):
        errors.append("v-trace.json must include a nodes array")
    if not isinstance(trace.get("links"), list):
        errors.append("v-trace.json must include a links array")
    selected = set(state.get("selected_stages", []))
    if not set(trace.get("selected_stages", [])).issubset(selected):
        errors.append("v-trace.json selected_stages contains stages outside this run")
    if stage_id and stage_id not in trace.get("selected_stages", []):
        errors.append(f"v-trace.json must include current stage {stage_id!r}")
    if "ai_usage" not in trace:
        errors.append("v-trace.json must disclose AI usage")
    if "subagent_receipts" in trace and not isinstance(trace.get("subagent_receipts"), list):
        errors.append("v-trace.json subagent_receipts must be a list")
    if "subagent_ingestions" in trace and not isinstance(trace.get("subagent_ingestions"), list):
        errors.append("v-trace.json subagent_ingestions must be a list")
    return errors


def _validate_receipt_shape(receipt: dict[str, Any]) -> list[str]:
    errors = []
    required = [
        "review_id",
        "run_id",
        "stage_id",
        "artifact_refs",
        "artifact_digest",
        "review_type",
        "reviewer",
        "decision",
        "reviewed_at",
    ]
    for key in required:
        if key not in receipt:
            errors.append(f"receipt missing required field {key}")
    if not isinstance(receipt.get("artifact_refs"), list) or not receipt.get("artifact_refs"):
        errors.append("receipt artifact_refs must be a non-empty list")
    if not isinstance(receipt.get("artifact_digest"), str) or not SHA256_RE.fullmatch(receipt.get("artifact_digest", "")):
        errors.append("receipt artifact_digest must be a sha256 digest")
    reviewer = receipt.get("reviewer")
    if not isinstance(reviewer, dict) or reviewer.get("actor_type") != "human":
        errors.append("receipt reviewer.actor_type must be human")
    elif not isinstance(reviewer.get("id"), str) or not reviewer.get("id").strip():
        errors.append("receipt reviewer.id is required")
    elif not isinstance(reviewer.get("role"), str) or not reviewer.get("role").strip():
        errors.append("receipt reviewer.role is required")
    if receipt.get("decision") not in HUMAN_DECISIONS:
        errors.append(f"receipt decision must be one of {sorted(HUMAN_DECISIONS)}")
    if receipt.get("review_type") not in {"expert-review", "approval", "sign-off", "action-approval"}:
        errors.append("receipt review_type is invalid")
    return errors


def _review_digest(run_id: str, stage_id: str, reviewer_id: str, digest: str) -> str:
    body = f"{run_id}\0{stage_id}\0{reviewer_id}\0{digest}".encode("utf-8")
    return hashlib.sha256(body).hexdigest()[:12]


def _current_stage_state(state: dict) -> dict:
    return state["stages"][int(state["current_stage_index"])]


def _state_stage(state: dict, stage_id: str) -> dict:
    for stage in state["stages"]:
        if stage.get("id") == stage_id:
            return stage
    raise KeyError(stage_id)


def _stage_material_artifact_paths(root: Path, state: dict, stage: dict) -> list[Path]:
    artifact_root = root / state["artifact_root"]
    paths = _stage_review_artifact_paths(root, state, stage)
    paths.append(artifact_root / "v-trace.json")
    return sorted(paths, key=lambda path: path.as_posix())


def _stage_review_artifact_paths(root: Path, state: dict, stage: dict) -> list[Path]:
    artifact_root = root / state["artifact_root"]
    paths = [artifact_root / filename for filename in STANDARD_ARTIFACTS.values()]
    stage_dir = artifact_root / "stages" / str(stage["id"])
    paths.extend(stage_dir / f"{artifact}.md" for artifact in stage.get("artifacts", []))
    return sorted(paths, key=lambda path: path.as_posix())


def _validate_required_subagent_receipts(root: Path, state: dict, stage: dict) -> list[str]:
    run_id = str(state["run_id"])
    stage_id = str(stage["id"])
    work_orders = _stage_work_orders(root, run_id, stage_id)
    if not work_orders:
        return []
    trace_path = _artifact_root(root, run_id) / "v-trace.json"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ["subagent lane receipt gate cannot be checked because v-trace.json is invalid"]
    receipts = trace.get("subagent_receipts", [])
    if not isinstance(receipts, list):
        return ["v-trace.json subagent_receipts must be a list"]
    complete_receipts = {
        str(item.get("work_order_id"))
        for item in receipts
        if isinstance(item, dict)
        and item.get("stage_id") == stage_id
        and item.get("exit_status") == "complete"
        and not _validate_subagent_receipt_trace_entry(root, run_id, stage_id, item)
    }
    errors = []
    for work_order in work_orders:
        work_order_id = str(work_order.get("work_order_id", ""))
        if work_order_id not in complete_receipts:
            errors.append(f"missing complete subagent lane receipt for work order {work_order_id!r}")
    return errors


def _validate_subagent_receipt_trace_entry(root: Path, run_id: str, stage_id: str, item: dict) -> list[str]:
    errors = []
    receipt_ref = item.get("receipt_ref")
    work_order_ref = item.get("work_order_ref")
    if not isinstance(receipt_ref, str) or not receipt_ref:
        errors.append("subagent receipt trace entry missing receipt_ref")
    if not isinstance(work_order_ref, str) or not work_order_ref:
        errors.append("subagent receipt trace entry missing work_order_ref")
    if errors:
        return errors
    receipt_path = (root / receipt_ref).resolve()
    work_order_path = (root / work_order_ref).resolve()
    expected_root = (_run_root(root, run_id) / "subagents" / stage_id).resolve()
    for label, path in [("receipt_ref", receipt_path), ("work_order_ref", work_order_path)]:
        try:
            path.relative_to(expected_root)
        except ValueError:
            errors.append(f"subagent {label} must be under .modeller/runs/<run-id>/subagents/<stage-id>")
        if not path.exists():
            errors.append(f"subagent {label} does not exist: {runtime_relative_path(root, path)}")
    if errors:
        return errors
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        work_order = json.loads(work_order_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return [f"persisted subagent receipt/work-order is not valid JSON: {exc}"]
    expected = {
        "receipt_id": receipt.get("receipt_id"),
        "work_order_id": receipt.get("work_order_id"),
        "agent_id": receipt.get("agent_id"),
        "exit_status": receipt.get("exit_status"),
        "output_digest": receipt.get("output_digest"),
        "stage_id": receipt.get("stage_id"),
        "receipt_ref": runtime_relative_path(root, receipt_path),
        "work_order_ref": runtime_relative_path(root, work_order_path),
        "receipt_sha256": _sha256_file(receipt_path),
        "work_order_sha256": _sha256_file(work_order_path),
    }
    for key, value in expected.items():
        if item.get(key) != value:
            errors.append(f"subagent receipt trace entry {key} does not match persisted lane receipt")
    if work_order.get("work_order_id") != receipt.get("work_order_id"):
        errors.append("persisted work order id does not match receipt work_order_id")
    if work_order.get("stage_id") != stage_id or receipt.get("stage_id") != stage_id:
        errors.append("persisted subagent receipt/work-order stage_id does not match current stage")
    return errors


def _validate_closed_stage_reviews(root: Path, state: dict, *, current_stage_id: str) -> list[str]:
    errors = []
    for stage in state.get("stages", []):
        if not isinstance(stage, dict) or stage.get("id") == current_stage_id or stage.get("status") != "closed":
            continue
        gate = check_v_cycle_stage(root, str(state["run_id"]), str(stage["id"]))
        if not gate.ok:
            errors.append(f"closed stage {stage.get('id')!r} review is no longer valid: {gate.errors}")
    return errors


def _stage_subagent_actor_ids(root: Path, state: dict, stage: dict) -> set[str]:
    run_id = str(state["run_id"])
    stage_id = str(stage["id"])
    actor_ids = {str(order.get("agent_id")) for order in _stage_work_orders(root, run_id, stage_id) if order.get("agent_id")}
    trace_path = _artifact_root(root, run_id) / "v-trace.json"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return actor_ids
    for item in trace.get("subagent_receipts", []):
        if isinstance(item, dict) and item.get("stage_id") == stage_id and item.get("agent_id"):
            actor_ids.add(str(item["agent_id"]))
    return actor_ids


def _stage_work_orders(root: Path, run_id: str, stage_id: str) -> list[dict]:
    work_order_root = _run_root(root, run_id) / "work-orders"
    if not work_order_root.exists():
        return []
    orders = []
    for path in sorted(work_order_root.glob("*.json"), key=lambda item: item.as_posix()):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            orders.append({"work_order_id": path.stem, "stage_id": stage_id})
            continue
        if payload.get("stage_id") == stage_id:
            orders.append(payload)
    return orders


def _contains_placeholder(text: str) -> bool:
    return "TBD" in text


def _write_if_missing(path: Path, text: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _validate_run_id(run_id: str) -> None:
    if run_id in {".", ".."} or ".." in run_id or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            "run_id must be 1-64 characters of letters, numbers, dot, underscore, or dash, "
            "start with a letter or number, and not contain '..'"
        )


def _run_root(root: Path, run_id: str) -> Path:
    return root / ".modeller" / "runs" / run_id


def _artifact_root(root: Path, run_id: str) -> Path:
    return _run_root(root, run_id) / "artifacts"


def _state_path(root: Path, run_id: str) -> Path:
    return _run_root(root, run_id) / "state.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
