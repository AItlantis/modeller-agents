from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .runtime import runtime_path


DEFAULT_WORKFLOW = "modeller-agents-build"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
PROVENANCE_MARKERS = ("subagent", "agent ", "sonnet", "evidence-source:", "produced by")


@dataclass
class GateResult:
    run_id: str
    workflow_id: str
    step_id: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    checked_artifacts: list[str] = field(default_factory=list)

    def format(self) -> str:
        lines = [f"workflow gate: {'OK' if self.ok else 'FAIL'}"]
        lines.append(f"run_id: {self.run_id}")
        lines.append(f"workflow_id: {self.workflow_id}")
        lines.append(f"step_id: {self.step_id}")
        lines.append("checked_artifacts:")
        lines.extend(f"  - {artifact}" for artifact in self.checked_artifacts)
        if self.errors:
            lines.append("errors:")
            lines.extend(f"  - {error}" for error in self.errors)
        return "\n".join(lines)


def init_workflow(root: Path, run_id: str, workflow_id: str = DEFAULT_WORKFLOW) -> dict:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    run_root = _run_root(root, run_id)
    artifact_root = _artifact_root(root, workflow, run_id)
    artifact_root.mkdir(parents=True, exist_ok=True)

    state = {
        "schema_version": "0.1",
        "workflow_id": workflow["workflow_id"],
        "run_id": run_id,
        "current_step_index": 0,
        "status": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "artifact_root": str(artifact_root.relative_to(root)),
        "steps": [
            {
                "id": step["id"],
                "status": "pending",
                "required_artifacts": step["required_artifacts"],
            }
            for step in workflow["steps"]
        ],
    }
    state["steps"][0]["status"] = "in_progress"

    template = runtime_path(root, "method", "templates", "workflow-artifact.md").read_text(encoding="utf-8")
    for step in workflow["steps"]:
        for artifact in step["required_artifacts"]:
            path = artifact_path(root, workflow, run_id, artifact)
            if path.exists():
                continue
            path.write_text(
                template.format(
                    workflow_id=workflow["workflow_id"],
                    run_id=run_id,
                    artifact=artifact,
                    step=step["id"],
                    title=artifact.replace("-", " ").title(),
                ),
                encoding="utf-8",
            )
    run_root.mkdir(parents=True, exist_ok=True)
    _state_path(root, workflow, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def load_workflow(root: Path, workflow_id: str = DEFAULT_WORKFLOW) -> dict:
    path = runtime_path(root, "method", "workflows", f"{workflow_id}.workflow.json")
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(root: Path, run_id: str, workflow_id: str = DEFAULT_WORKFLOW) -> dict:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    return json.loads(_state_path(root, workflow, run_id).read_text(encoding="utf-8"))


def check_current_step(root: Path, run_id: str, workflow_id: str = DEFAULT_WORKFLOW) -> GateResult:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    step = workflow["steps"][state["current_step_index"]]
    errors: list[str] = []
    checked: list[str] = []
    for artifact in step["required_artifacts"]:
        checked.append(artifact)
        path = artifact_path(root, workflow, run_id, artifact)
        errors.extend(_validate_artifact(path, workflow, run_id, artifact, step))
    return GateResult(
        run_id=run_id,
        workflow_id=workflow["workflow_id"],
        step_id=step["id"],
        ok=not errors,
        errors=errors,
        checked_artifacts=checked,
    )


def advance_workflow(root: Path, run_id: str, workflow_id: str = DEFAULT_WORKFLOW) -> GateResult:
    _validate_run_id(run_id)
    gate = check_current_step(root, run_id, workflow_id)
    if not gate.ok:
        return gate
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    index = state["current_step_index"]
    state["steps"][index]["status"] = "complete"
    if index + 1 >= len(workflow["steps"]):
        state["status"] = "complete"
    else:
        state["current_step_index"] = index + 1
        state["steps"][index + 1]["status"] = "in_progress"
    state["updated_at"] = _now()
    _state_path(root, workflow, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return gate


def complete_artifact(
    root: Path,
    run_id: str,
    artifact: str,
    updated_by: str,
    evidence: str,
    output: str,
    purpose: str | None = None,
    verification: str | None = None,
    workflow_id: str = DEFAULT_WORKFLOW,
) -> Path:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    step = _artifact_step(workflow, artifact)
    current_step = workflow["steps"][state["current_step_index"]]
    if step["id"] != current_step["id"]:
        raise ValueError(
            f"artifact {artifact!r} belongs to step {step['id']!r}; "
            f"current step is {current_step['id']!r}"
        )
    if updated_by != step["owner"]:
        raise ValueError(f"artifact {artifact!r} must be completed by owner {step['owner']!r}")
    path = artifact_path(root, workflow, run_id, artifact)
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    values = _parse_frontmatter(frontmatter)
    values.update(
        {
            "workflow_id": workflow["workflow_id"],
            "run_id": run_id,
            "artifact": artifact,
            "step": step["id"],
            "status": "complete",
            "updated_by": updated_by,
            "updated_at": _now(),
        }
    )
    body = _replace_section(
        body,
        "Purpose",
        purpose or f"Record the completed {artifact} artifact for workflow step {step['id']}.",
    )
    body = _replace_section(body, "Evidence", evidence)
    body = _replace_section(body, "Decisions Or Outputs", output)
    body = _replace_section(
        body,
        "Verification",
        verification or "Verification: artifact owner, required terms, evidence, and workflow gate were checked.",
    )
    path.write_text(_render_frontmatter(values) + body, encoding="utf-8")
    state["updated_at"] = _now()
    _state_path(root, workflow, run_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return path


def format_status(root: Path, run_id: str, workflow_id: str = DEFAULT_WORKFLOW) -> str:
    _validate_run_id(run_id)
    workflow = load_workflow(root, workflow_id)
    state = load_state(root, run_id, workflow_id)
    current = workflow["steps"][state["current_step_index"]]
    lines = [f"workflow: {workflow['workflow_id']}", f"run_id: {run_id}", f"status: {state['status']}"]
    lines.append(f"current_step: {current['id']} - {current['title']}")
    lines.append("steps:")
    for step in state["steps"]:
        lines.append(f"  - {step['id']}: {step['status']}")
    return "\n".join(lines)


def artifact_path(root: Path, workflow: dict, run_id: str, artifact: str) -> Path:
    _validate_run_id(run_id)
    rel = workflow["artifact_root"].format(run_id=run_id)
    return root / rel / workflow["artifacts"][artifact]


def _run_root(root: Path, run_id: str) -> Path:
    _validate_run_id(run_id)
    return root / ".modeller/runs" / run_id


def _artifact_root(root: Path, workflow: dict, run_id: str) -> Path:
    _validate_run_id(run_id)
    return root / workflow["artifact_root"].format(run_id=run_id)


def _state_path(root: Path, workflow: dict, run_id: str) -> Path:
    _validate_run_id(run_id)
    return root / workflow["state_path"].format(run_id=run_id)


def _artifact_step(workflow: dict, artifact: str) -> dict:
    for step in workflow["steps"]:
        if artifact in step["required_artifacts"]:
            return step
    raise KeyError(f"artifact {artifact!r} is not required by workflow")


def _validate_artifact(path: Path, workflow: dict, run_id: str, artifact: str, step: dict) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{artifact}: missing artifact file {path}"]
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    values = _parse_frontmatter(frontmatter)
    expected = {
        "workflow_id": workflow["workflow_id"],
        "run_id": run_id,
        "artifact": artifact,
        "step": step["id"],
        "status": "complete",
    }
    for key, value in expected.items():
        if values.get(key) != value:
            errors.append(f"{artifact}: front matter {key} must be {value!r}")
    for key in ["updated_by", "updated_at"]:
        if not values.get(key):
            errors.append(f"{artifact}: front matter {key} is required")
    if values.get("updated_by") and values.get("updated_by") != step["owner"]:
        errors.append(f"{artifact}: front matter updated_by must be owner {step['owner']!r}")
    evidence = _section(body, "Evidence")
    output = _section(body, "Decisions Or Outputs")
    purpose = _section(body, "Purpose")
    verification = _section(body, "Verification")
    if _is_placeholder(purpose):
        errors.append(f"{artifact}: Purpose section must be completed")
    if _is_placeholder(evidence):
        errors.append(f"{artifact}: Evidence section must be completed")
    if _is_placeholder(output):
        errors.append(f"{artifact}: Decisions Or Outputs section must be completed")
    if _is_placeholder(verification):
        errors.append(f"{artifact}: Verification section must be completed")
    searchable = f"{evidence}\n{output}\n{verification}".lower()
    for term in _artifact_required_terms(workflow, artifact):
        if term.lower() not in searchable:
            errors.append(f"{artifact}: required evidence term {term!r} is missing")
    if _requires_agent_evidence(workflow, artifact, step):
        if not _has_provenance_marker(evidence):
            errors.append(
                f"artifact {artifact!r}: Evidence section must cite subagent/agent-produced "
                "evidence (found no provenance marker); subagent output must be incorporated, "
                "not asserted"
            )
    return errors


def _artifact_required_terms(workflow: dict, artifact: str) -> list[str]:
    rules = workflow.get("artifact_requirements", {})
    return list(rules.get(artifact, {}).get("required_terms", []))


def _requires_agent_evidence(workflow: dict, artifact: str, step: dict) -> bool:
    if step.get("requires_agent_evidence"):
        return True
    rules = workflow.get("artifact_requirements", {})
    return bool(rules.get(artifact, {}).get("requires_agent_evidence"))


def _has_provenance_marker(evidence: str) -> bool:
    lowered = evidence.lower()
    return any(marker in lowered for marker in PROVENANCE_MARKERS)


def _validate_run_id(run_id: str) -> None:
    if run_id in {".", ".."} or ".." in run_id or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            "run_id must be 1-64 characters of letters, numbers, dot, underscore, or dash, "
            "start with a letter or number, and not contain '..'"
        )


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[4:end], text[end + len("\n---\n") :]


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _render_frontmatter(values: dict[str, str]) -> str:
    keys = ["workflow_id", "run_id", "artifact", "step", "status", "updated_by", "updated_at"]
    lines = ["---"]
    lines.extend(f"{key}: {values.get(key, '')}" for key in keys)
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _section(body: str, heading: str) -> str:
    marker = f"## {heading}"
    start = body.find(marker)
    if start == -1:
        return ""
    start = body.find("\n", start)
    if start == -1:
        return ""
    next_heading = body.find("\n## ", start + 1)
    if next_heading == -1:
        return body[start:].strip()
    return body[start:next_heading].strip()


def _replace_section(body: str, heading: str, content: str) -> str:
    marker = f"## {heading}"
    start = body.find(marker)
    if start == -1:
        return body.rstrip() + f"\n\n{marker}\n\n{content.strip()}\n"
    content_start = body.find("\n", start)
    next_heading = body.find("\n## ", content_start + 1)
    replacement = f"{marker}\n\n{content.strip()}\n"
    if next_heading == -1:
        return body[:start] + replacement
    return body[:start] + replacement + body[next_heading + 1 :]


def _is_placeholder(text: str) -> bool:
    stripped = text.strip()
    return not stripped or stripped.upper() == "TBD" or stripped.endswith("\nTBD")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
