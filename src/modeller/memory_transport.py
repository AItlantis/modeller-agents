from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


OWNER = "modeller-agents/memory-agent"
SOURCE = "modeller-memory"
VALID_SENSITIVITY = {"public", "internal", "restricted"}
FORBIDDEN_DRAFT_FIELDS = {"id", "authority_level"}


@dataclass
class TransportResult:
    ok: bool
    output_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "output_path": str(self.output_path) if self.output_path else None,
            "errors": self.errors,
        }

    def format(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def transport_memory_candidate(candidate_path: Path, vault_inbox_dir: Path) -> TransportResult:
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return TransportResult(ok=False, errors=[f"failed to read MemoryCandidate JSON: {exc}"])

    errors = _validate_candidate(candidate)
    try:
        inbox_dir = _validate_inbox_dir(vault_inbox_dir)
    except ValueError as exc:
        errors.append(str(exc))
        inbox_dir = None
    if errors:
        return TransportResult(ok=False, errors=errors)

    assert inbox_dir is not None
    inbox_dir.mkdir(parents=True, exist_ok=True)
    output_path = inbox_dir / f"{_slug(candidate['candidate_id'])}.md"
    if output_path.exists():
        return TransportResult(ok=False, errors=[f"discovery draft already exists: {output_path}"])
    if not _is_relative_to(output_path.resolve(), inbox_dir.resolve()):
        return TransportResult(ok=False, errors=["resolved output path escapes inbox/discovery-drafts"])

    output_path.write_text(_render_discovery_draft(candidate), encoding="utf-8")
    return TransportResult(ok=True, output_path=output_path)


def _validate_candidate(candidate: Any) -> list[str]:
    if not isinstance(candidate, dict):
        return ["MemoryCandidate JSON must be an object"]
    errors: list[str] = []
    required = [
        "candidate_id",
        "claim",
        "provenance",
        "sensitivity",
        "target",
        "related_decisions",
        "origin_run",
    ]
    for key in required:
        if key not in candidate:
            errors.append(f"MemoryCandidate.{key} is required")
    for key in FORBIDDEN_DRAFT_FIELDS:
        if key in candidate:
            errors.append(f"MemoryCandidate.{key} is not allowed on discovery drafts")
    if candidate.get("target") != "vault-inbox":
        errors.append("MemoryCandidate.target must be 'vault-inbox' for vault inbox transport")
    if candidate.get("sensitivity") not in VALID_SENSITIVITY:
        errors.append("MemoryCandidate.sensitivity must be public, internal, or restricted")
    for key in ["candidate_id", "claim", "origin_run"]:
        if key in candidate and not str(candidate.get(key) or "").strip():
            errors.append(f"MemoryCandidate.{key} must be non-empty")
    for key in ["related_decisions", "authority_context_refs"]:
        if key in candidate and not isinstance(candidate.get(key), list):
            errors.append(f"MemoryCandidate.{key} must be a list when present")
    if "provenance" in candidate and not isinstance(candidate.get("provenance"), dict):
        errors.append("MemoryCandidate.provenance must be an object")
    return errors


def _validate_inbox_dir(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.name != "discovery-drafts" or resolved.parent.name != "inbox":
        raise ValueError("output directory must be the vault inbox/discovery-drafts directory")
    return resolved


def _render_discovery_draft(candidate: dict[str, Any]) -> str:
    title = _title(candidate)
    captured_from = _captured_from(candidate)
    frontmatter = {
        "title": title,
        "status": "draft",
        "type": "discovery-draft",
        "owner": OWNER,
        "source": SOURCE,
        "candidate_id": str(candidate["candidate_id"]),
        "origin_run": str(candidate["origin_run"]),
        "authority_context_refs": list(candidate.get("authority_context_refs", [])),
        "related_decisions": list(candidate.get("related_decisions", [])),
        "sensitivity": str(candidate["sensitivity"]),
        "captured_from": captured_from,
        "claim": str(candidate["claim"]),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.extend(_frontmatter_lines(key, value))
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Claim")
    lines.append("")
    lines.append(str(candidate["claim"]).strip())
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- `source: {SOURCE}` classified the candidate.")
    lines.append(f"- `owner: {OWNER}` transported the draft into the vault inbox.")
    lines.append(f"- `candidate_id: {candidate['candidate_id']}` and `origin_run: {candidate['origin_run']}` identify the source run.")
    lines.append("")
    lines.append("## Sensitivity")
    lines.append("")
    lines.append(f"`sensitivity: {candidate['sensitivity']}`")
    return "\n".join(lines) + "\n"


def _frontmatter_lines(key: str, value: Any) -> list[str]:
    if isinstance(value, list):
        if not value:
            return [f"{key}: []"]
        return [f"{key}:"] + [f"  - {json.dumps(str(item))}" for item in value]
    if isinstance(value, str) and "\n" in value:
        return [f"{key}: |-"] + [f"  {line}" for line in value.splitlines()]
    return [f"{key}: {json.dumps(str(value))}"]


def _title(candidate: dict[str, Any]) -> str:
    claim = " ".join(str(candidate["claim"]).split())
    return claim[:72].rstrip(" .,;:") or str(candidate["candidate_id"])


def _captured_from(candidate: dict[str, Any]) -> str:
    provenance = candidate.get("provenance", {})
    evidence_refs = provenance.get("evidence_refs", []) if isinstance(provenance, dict) else []
    parts = [f"origin_run={candidate['origin_run']}"]
    if isinstance(provenance, dict):
        if provenance.get("source_repository"):
            parts.append(f"source_repository={provenance['source_repository']}")
        if provenance.get("source_commit"):
            parts.append(f"source_commit={provenance['source_commit']}")
    if evidence_refs:
        parts.append("evidence_refs=" + ",".join(str(ref) for ref in evidence_refs))
    return "; ".join(parts)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value).strip()).strip("-._").lower()
    return slug[:96] or "memory-candidate"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
