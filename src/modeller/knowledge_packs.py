from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .toml_compat import load_toml


VALID_PACK_STATUSES = {"draft", "active", "deprecated", "superseded"}
VALID_AFFINITY_MODES = {"none", "explicit", "routed"}
SENSITIVITY_RANK = {"public": 0, "internal": 1, "restricted": 2}
DEFAULT_KNOWLEDGE_CAP = 2
ROUTING_LIMITS = {
    "max_knowledge_packs": 3,
    "max_required_notes": 8,
    "max_optional_notes_loaded": 4,
    "max_full_notes": 2,
}
PROHIBITED_FIELDS = {
    "body",
    "content",
    "summary_as_authority",
    "copied_thresholds",
    "copied_rules",
    "copied_decision_text",
    "local_acceptance_status",
}


@dataclass
class VaultExports:
    index: dict
    domains: dict
    warnings: list[str] = field(default_factory=list)


@dataclass
class KnowledgePackCheck:
    path: Path
    pack_id: str = ""
    domain: str = ""
    status: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class KnowledgeResolution:
    domains: list[dict] = field(default_factory=list)
    packs: list[str] = field(default_factory=list)
    budget: dict = field(default_factory=lambda: {
        "packs_selected": 0,
        "notes_selected": 0,
        "notes_deferred": 0,
        "max_knowledge_packs": ROUTING_LIMITS["max_knowledge_packs"],
        "max_required_notes": ROUTING_LIMITS["max_required_notes"],
        "max_optional_notes_loaded": ROUTING_LIMITS["max_optional_notes_loaded"],
        "max_full_notes": ROUTING_LIMITS["max_full_notes"],
    })
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_vault_exports(root: Path) -> VaultExports:
    """Load current vault exports without requiring committed generated JSON files."""
    source_root = _installed_source_root(root) or root
    vault = source_root.parent / "modelling-knowledge"
    memory_src = source_root.parent / "modeller-memory" / "src"
    warnings: list[str] = []
    if not vault.exists():
        return VaultExports(index={}, domains={}, warnings=[f"modelling-knowledge vault not found: {vault}"])

    env = os.environ.copy()
    if memory_src.exists():
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(memory_src) + (os.pathsep + existing if existing else "")

    def _run(command: str) -> dict:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "modeller_memory.tools.vault_doctor.cli",
                command,
                "--vault-path",
                str(vault),
                "--json",
            ],
            cwd=str(root.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"{command} failed")
        return json.loads(proc.stdout)

    try:
        return VaultExports(index=_run("export-index"), domains=_run("export-domains"), warnings=warnings)
    except Exception as exc:
        return VaultExports(index={}, domains={}, warnings=[f"cannot load vault exports: {exc}"])


def _installed_source_root(root: Path) -> Path | None:
    manifest = root / ".modeller" / "install-manifest.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if payload.get("installer") != "modeller-agents":
        return None
    source_root = payload.get("source_root")
    if not isinstance(source_root, str) or not source_root.strip():
        return None
    path = Path(source_root)
    return path if path.exists() else None


def validate_domain_registry(root: Path, exports: VaultExports | None = None) -> list[str]:
    errors: list[str] = []
    path = root / "reference-packs" / "domains" / "_registry.toml"
    if not path.exists():
        errors.append("missing knowledge domain registry: reference-packs/domains/_registry.toml")
        return errors
    try:
        registry = load_toml(path)
    except Exception as exc:
        return [f"invalid knowledge domain registry TOML: {exc}"]
    if registry.get("schema_version") not in {1, "1"}:
        errors.append("reference-packs/domains/_registry.toml: schema_version must be 1")
    domains = registry.get("domains")
    if not isinstance(domains, dict) or not domains:
        errors.append("reference-packs/domains/_registry.toml: [domains.*] entries are required")
        return errors
    seen_aliases: dict[str, str] = {}
    vault_domains = {}
    if exports and exports.domains:
        vault_domains = {d.get("id"): d for d in exports.domains.get("domains", [])}
    for dom_id, spec in domains.items():
        if not isinstance(spec, dict):
            errors.append(f"reference-packs/domains/_registry.toml: domain {dom_id!r} must be a table")
            continue
        pack = spec.get("pack")
        if not isinstance(pack, str) or not pack:
            errors.append(f"domain {dom_id}: pack must be a non-empty string")
        elif not (root / pack).exists():
            errors.append(f"domain {dom_id}: pack does not exist: {pack}")
        aliases = spec.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            errors.append(f"domain {dom_id}: aliases must be a non-empty string array")
        else:
            for alias in aliases:
                key = str(alias).lower()
                if key in seen_aliases and seen_aliases[key] != dom_id:
                    errors.append(f"domain alias {alias!r} is used by both {seen_aliases[key]!r} and {dom_id!r}")
                seen_aliases[key] = dom_id
        if vault_domains:
            vault_domain = vault_domains.get(dom_id)
            if not vault_domain:
                errors.append(f"domain {dom_id}: absent from vault export")
            elif vault_domain.get("status") != "active" or vault_domain.get("routable") is not True:
                errors.append(f"domain {dom_id}: vault export is not active/routable")
    return errors


def validate_bundle_default_knowledge(bundle_name: str, bundle: dict) -> list[str]:
    value = bundle.get("defaultKnowledge", [])
    if value in (None, []):
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return [f"{bundle_name}: defaultKnowledge must be a string array when present"]
    if len(value) > DEFAULT_KNOWLEDGE_CAP:
        return [
            f"{bundle_name}: defaultKnowledge selects {len(value)} domains; "
            f"maximum is {DEFAULT_KNOWLEDGE_CAP}"
        ]
    if len(set(value)) != len(value):
        return [f"{bundle_name}: defaultKnowledge must not contain duplicates"]
    return []


def resolve_knowledge_selection(
    root: Path,
    *,
    requested_domains: object,
    default_domains: object,
    skill: str,
) -> KnowledgeResolution:
    resolution = KnowledgeResolution()
    request_items, request_errors = _domain_list("intent.domains", requested_domains)
    default_items, default_errors = _domain_list("bundle.defaultKnowledge", default_domains)
    resolution.errors.extend(request_errors)
    resolution.errors.extend(default_errors)
    if default_items and len(default_items) > DEFAULT_KNOWLEDGE_CAP:
        resolution.errors.append(
            f"bundle.defaultKnowledge selects {len(default_items)} domains; maximum is {DEFAULT_KNOWLEDGE_CAP}"
        )
    if resolution.errors:
        return resolution

    ordered: list[dict] = []
    seen: set[str] = set()
    for source, values in (("request", request_items), ("bundle-default", default_items)):
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append({"id": value, "source": source})
    if not ordered:
        return resolution
    if len(ordered) > ROUTING_LIMITS["max_knowledge_packs"]:
        resolution.errors.append(
            f"knowledge selection has {len(ordered)} domains; "
            f"maximum is {ROUTING_LIMITS['max_knowledge_packs']}"
        )
        return resolution

    affinity = load_skill_domain_affinity(root, skill)
    resolution.errors.extend(affinity["errors"])
    resolution.warnings.extend(affinity["warnings"])
    mode = affinity["mode"]
    allowed = set(affinity["domains"])
    if mode == "none":
        resolution.errors.append(f"skill {skill!r} does not allow knowledge domains")
        return resolution

    canonical, aliases, registry_errors = load_domain_pack_registry(root)
    resolution.errors.extend(registry_errors)
    if registry_errors:
        return resolution

    canonical_domains: list[dict] = []
    canonical_seen: set[str] = set()
    for item in ordered:
        raw_id = item["id"]
        canonical_id = _resolve_domain_id(raw_id, canonical, aliases)
        if canonical_id is None:
            resolution.errors.append(f"unknown knowledge domain {raw_id!r}")
            continue
        if mode == "explicit" and canonical_id not in allowed:
            resolution.errors.append(f"skill {skill!r} does not explicitly allow knowledge domain {canonical_id!r}")
            continue
        if canonical_id in canonical_seen:
            continue
        canonical_seen.add(canonical_id)
        selected = {"id": canonical_id, "source": item["source"]}
        if canonical_id != raw_id:
            selected["requested_as"] = raw_id
        canonical_domains.append(selected)
    if resolution.errors:
        return resolution

    exports = load_vault_exports(root)
    for item in canonical_domains:
        pack_path = canonical[item["id"]]
        check = validate_knowledge_pack(root, pack_path, exports=exports)
        resolution.errors.extend(check.errors)
        resolution.warnings.extend(check.warnings)
        if check.ok:
            resolution.domains.append(item)
            resolution.packs.append(pack_path)
            notes = check.data.get("notes", []) if isinstance(check.data.get("notes"), list) else []
            required = [note for note in notes if isinstance(note, dict) and note.get("required") is True]
            optional = [note for note in notes if isinstance(note, dict) and note.get("required") is False]
            resolution.budget["notes_selected"] += len(required) + min(
                len(optional), ROUTING_LIMITS["max_optional_notes_loaded"]
            )
            resolution.budget["notes_deferred"] += max(0, len(optional) - ROUTING_LIMITS["max_optional_notes_loaded"])
            if len(required) > ROUTING_LIMITS["max_required_notes"]:
                resolution.errors.append(
                    f"{pack_path}: required notes {len(required)} exceeds "
                    f"{ROUTING_LIMITS['max_required_notes']}"
                )
    resolution.budget["packs_selected"] = len(resolution.packs)
    if resolution.budget["notes_selected"] > ROUTING_LIMITS["max_required_notes"] + ROUTING_LIMITS["max_optional_notes_loaded"]:
        resolution.errors.append(
            "knowledge selection exceeds note budget: "
            f"{resolution.budget['notes_selected']} selected"
        )
    return resolution


def validate_knowledge_pack(root: Path, rel_path: str, exports: VaultExports | None = None) -> KnowledgePackCheck:
    path = root / rel_path
    check = KnowledgePackCheck(path=path)
    try:
        data = load_toml(path)
    except FileNotFoundError:
        check.errors.append(f"knowledge pack missing: {rel_path}")
        return check
    except Exception as exc:
        check.errors.append(f"knowledge pack invalid TOML {rel_path}: {exc}")
        return check
    check.data = data
    check.pack_id = str(data.get("id", ""))
    check.domain = str(data.get("domain", ""))
    check.status = str(data.get("status", ""))

    for field_name in [
        "schema_version",
        "id",
        "kind",
        "domain",
        "status",
        "source_vault",
        "source_index_digest",
        "source_domains_digest",
        "authority_context",
        "required_scopes",
        "max_sensitivity",
        "notes",
    ]:
        if field_name not in data:
            check.errors.append(f"{rel_path}: missing {field_name}")
    if data.get("schema_version") not in {1, "1"}:
        check.errors.append(f"{rel_path}: schema_version must be 1")
    if data.get("kind") != "knowledge":
        check.errors.append(f"{rel_path}: kind must be 'knowledge'")
    if check.status and check.status not in VALID_PACK_STATUSES:
        check.errors.append(f"{rel_path}: status must be one of {sorted(VALID_PACK_STATUSES)}")
    if check.status == "draft":
        check.warnings.append(f"{rel_path}: knowledge pack is draft")
    expected_id = Path(rel_path).stem
    if check.pack_id and check.pack_id != expected_id:
        check.errors.append(f"{rel_path}: id {check.pack_id!r} must match filename stem {expected_id!r}")
    if data.get("source_vault") != "modelling-knowledge":
        check.errors.append(f"{rel_path}: source_vault must be 'modelling-knowledge'")
    authority_context = data.get("authority_context", {})
    if not isinstance(authority_context, dict):
        check.errors.append(f"{rel_path}: authority_context must be a table")
        authority_context = {}
    for field_name in [
        "vault",
        "domain_registry",
        "scope_decision",
        "knowledge_seam_decision",
        "coordination_decision",
        "checked_at",
    ]:
        if not isinstance(authority_context.get(field_name), str) or not authority_context.get(field_name):
            check.errors.append(f"{rel_path}: authority_context.{field_name} must be a non-empty string")
    if authority_context.get("vault") and authority_context.get("vault") != "modelling-knowledge":
        check.errors.append(f"{rel_path}: authority_context.vault must be 'modelling-knowledge'")
    if data.get("max_sensitivity") not in SENSITIVITY_RANK:
        check.errors.append(f"{rel_path}: max_sensitivity must be public, internal, or restricted")
    scopes = data.get("required_scopes")
    if not isinstance(scopes, list) or not scopes or not all(isinstance(s, str) and s for s in scopes):
        check.errors.append(f"{rel_path}: required_scopes must be a non-empty string array")

    for field_name in PROHIBITED_FIELDS:
        if field_name in data:
            check.errors.append(f"{rel_path}: prohibited copied-knowledge field {field_name}")

    notes = data.get("notes")
    if not isinstance(notes, list) or not notes:
        check.errors.append(f"{rel_path}: notes must be a non-empty array of tables")
        notes = []
    required_count = 0
    for index, note in enumerate(notes):
        if not isinstance(note, dict):
            check.errors.append(f"{rel_path}: notes[{index}] must be a table")
            continue
        extra = set(note).difference({"id", "required", "purpose"})
        if extra:
            check.errors.append(f"{rel_path}: notes[{index}] has unsupported fields: {', '.join(sorted(extra))}")
        if not isinstance(note.get("id"), str) or not note.get("id"):
            check.errors.append(f"{rel_path}: notes[{index}].id must be a non-empty string")
        if not isinstance(note.get("required"), bool):
            check.errors.append(f"{rel_path}: notes[{index}].required must be boolean")
        elif note.get("required"):
            required_count += 1
        if not isinstance(note.get("purpose"), str) or not note.get("purpose"):
            check.errors.append(f"{rel_path}: notes[{index}].purpose must be a non-empty string")
    if check.status == "active" and required_count == 0:
        check.errors.append(f"{rel_path}: active knowledge pack must have at least one required note")

    if exports is None:
        exports = load_vault_exports(root)
    check.warnings.extend(exports.warnings)
    if check.status == "active" and (not exports.index or not exports.domains):
        check.errors.append(f"{rel_path}: active knowledge pack requires current vault exports")
        return check
    if exports.index:
        if data.get("source_index_digest") != exports.index.get("index_digest"):
            check.errors.append(f"{rel_path}: source_index_digest does not match current vault export")
        notes_by_id = {n.get("id"): n for n in exports.index.get("notes", [])}
        domains_by_id = {d.get("id"): d for d in exports.domains.get("domains", [])} if exports.domains else {}
        domain_spec = domains_by_id.get(check.domain)
        if check.status == "active":
            if not domain_spec:
                check.errors.append(f"{rel_path}: domain {check.domain!r} absent from current vault domain export")
            elif domain_spec.get("status") != "active" or domain_spec.get("routable") is not True:
                check.errors.append(f"{rel_path}: domain {check.domain!r} is not active/routable in vault export")
        allowed_types = set(domain_spec.get("allowed_note_types", [])) if domain_spec else set()
        max_sens = data.get("max_sensitivity")
        for note in notes:
            if not isinstance(note, dict) or not isinstance(note.get("id"), str):
                continue
            vault_note = notes_by_id.get(note["id"])
            if not vault_note:
                check.errors.append(f"{rel_path}: note id {note['id']!r} absent from current vault index")
                continue
            if vault_note.get("domain") != check.domain:
                check.errors.append(f"{rel_path}: note {note['id']!r} domain is {vault_note.get('domain')!r}")
            if vault_note.get("status") != "accepted":
                check.errors.append(f"{rel_path}: note {note['id']!r} is not accepted")
            if vault_note.get("status") in {"superseded", "deprecated", "historical"} or vault_note.get("superseded_by"):
                replacement = vault_note.get("superseded_by") or "replacement not declared"
                check.errors.append(f"{rel_path}: note {note['id']!r} is superseded by {replacement!r}")
            if vault_note.get("exposable") is not True:
                check.errors.append(f"{rel_path}: note {note['id']!r} is not exposable")
            exposure_scopes = vault_note.get("exposure_scopes", [])
            if isinstance(scopes, list) and isinstance(exposure_scopes, list):
                missing_scopes = sorted(set(scopes).difference(set(exposure_scopes)))
                if missing_scopes:
                    check.errors.append(
                        f"{rel_path}: note {note['id']!r} lacks required exposure scopes: "
                        f"{', '.join(missing_scopes)}"
                    )
            if vault_note.get("sensitivity") == "restricted":
                check.errors.append(f"{rel_path}: note {note['id']!r} is restricted")
            if allowed_types and vault_note.get("type") not in allowed_types:
                check.errors.append(f"{rel_path}: note {note['id']!r} type {vault_note.get('type')!r} is not allowed")
            if max_sens in SENSITIVITY_RANK and vault_note.get("sensitivity") in SENSITIVITY_RANK:
                if SENSITIVITY_RANK[vault_note["sensitivity"]] > SENSITIVITY_RANK[max_sens]:
                    check.errors.append(f"{rel_path}: note {note['id']!r} exceeds max_sensitivity {max_sens!r}")
    if exports.domains and data.get("source_domains_digest") != exports.domains.get("index_digest"):
        check.errors.append(f"{rel_path}: source_domains_digest does not match current vault domain export")
    return check


def load_domain_pack_registry(root: Path) -> tuple[dict[str, str], dict[str, str], list[str]]:
    path = root / "reference-packs" / "domains" / "_registry.toml"
    try:
        registry = load_toml(path)
    except FileNotFoundError:
        return {}, {}, ["knowledge domain registry missing"]
    except Exception as exc:
        return {}, {}, [f"knowledge domain registry invalid TOML: {exc}"]
    domains = registry.get("domains", {})
    canonical: dict[str, str] = {}
    aliases: dict[str, str] = {}
    errors: list[str] = []
    if not isinstance(domains, dict):
        return {}, {}, ["knowledge domain registry has no [domains.*] table"]
    for dom_id, spec in domains.items():
        if not isinstance(spec, dict):
            continue
        pack = spec.get("pack")
        if isinstance(pack, str):
            canonical[dom_id] = pack
        for alias in spec.get("aliases", []) if isinstance(spec.get("aliases"), list) else []:
            aliases[str(alias).lower()] = dom_id
    return canonical, aliases, errors


def load_skill_domain_affinity(root: Path, skill: str) -> dict:
    path = root / ".claude" / "plugins" / "modeller" / "skills" / skill / "SKILL.md"
    result = {"mode": "none", "domains": [], "errors": [], "warnings": []}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result["errors"].append(f"missing skill file for domain affinity: {path}")
        return result
    frontmatter = _frontmatter(text)
    if "domain_affinity:" not in frontmatter:
        return result
    mode = _frontmatter_nested_value(frontmatter, "domain_affinity", "mode")
    domains = _frontmatter_nested_list(frontmatter, "domain_affinity", "domains")
    if mode not in VALID_AFFINITY_MODES:
        result["errors"].append(f"skill {skill!r} domain_affinity.mode must be one of {sorted(VALID_AFFINITY_MODES)}")
        return result
    if any(item.lower() in {"*", "all", "any"} for item in domains):
        result["errors"].append(f"skill {skill!r} domain_affinity must not use wildcard domains")
    if mode == "explicit" and not domains:
        result["errors"].append(f"skill {skill!r} domain_affinity explicit mode requires domains")
    if mode == "none" and domains:
        result["errors"].append(f"skill {skill!r} domain_affinity none mode must not list domains")
    if mode == "routed" and domains:
        result["warnings"].append(f"skill {skill!r} domain_affinity routed mode ignores listed domains")
    result["mode"] = mode
    result["domains"] = domains
    return result


def validate_skill_domain_affinities(root: Path) -> list[str]:
    errors: list[str] = []
    skill_root = root / ".claude" / "plugins" / "modeller" / "skills"
    if not skill_root.exists():
        return errors
    for skill_dir in sorted(path for path in skill_root.iterdir() if path.is_dir()):
        affinity = load_skill_domain_affinity(root, skill_dir.name)
        errors.extend(affinity["errors"])
    return errors


def _domain_list(label: str, value: object) -> tuple[list[str], list[str]]:
    if value in (None, []):
        return [], []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return [], [f"{label} must be a string array when present"]
    return list(value), []


def _resolve_domain_id(raw_id: str, canonical: dict[str, str], aliases: dict[str, str]) -> str | None:
    if raw_id in canonical:
        return raw_id
    return aliases.get(raw_id.lower())


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    if end == -1:
        return ""
    return text[4:end]


def _frontmatter_nested_value(frontmatter: str, parent: str, key: str) -> str:
    lines = frontmatter.splitlines()
    in_parent = False
    for line in lines:
        if line.startswith(f"{parent}:"):
            in_parent = True
            continue
        if in_parent:
            if line and not line.startswith(" "):
                return ""
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                return stripped.split(":", 1)[1].strip().strip('"')
    return ""


def _frontmatter_nested_list(frontmatter: str, parent: str, key: str) -> list[str]:
    lines = frontmatter.splitlines()
    in_parent = False
    in_list = False
    values: list[str] = []
    for line in lines:
        if line.startswith(f"{parent}:"):
            in_parent = True
            continue
        if not in_parent:
            continue
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            tail = stripped.split(":", 1)[1].strip()
            if tail.startswith("[") and tail.endswith("]"):
                inner = tail[1:-1].strip()
                if inner:
                    values.extend(part.strip().strip('"') for part in inner.split(",") if part.strip())
                return values
            in_list = True
            continue
        if in_list:
            if stripped.startswith("- "):
                values.append(stripped[2:].strip().strip('"'))
            elif stripped:
                break
    return values
