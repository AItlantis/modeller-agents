"""Deterministic vault-index and domain-index export.

Shapes follow the Vault Index Contract (vault-alignment-plan.md) and
docs/dev/vault-index-schema.md. Exports are DETERMINISTIC: notes are sorted by
id, keys are sorted, and volatile fields (generated_at) are omitted by default
so an unchanged vault produces byte-identical output across runs.
"""

from __future__ import annotations

import hashlib
import json

import yaml

from . import model
from .loader import Vault

SCHEMA_VERSION = 1

# Exposure scopes by sensitivity (per the standard / index contract).
_EXPOSURE_SCOPES = {
    "public": ["internal-agent", "product", "external"],
    "internal": ["internal-agent"],
    "restricted": [],
}


def _exposability(fm: dict) -> tuple[bool, list[str]]:
    """Compute (exposable, exposure_scopes) from a note's declared sensitivity.

    restricted -> (False, []). An explicit ``exposable: false`` on the note wins.
    Un-normalized transitional labels are non-exposable.
    """
    sens = fm.get("sensitivity")
    if fm.get("exposable") is False:
        return False, []
    if sens == "restricted":
        return False, []
    if sens in _EXPOSURE_SCOPES:
        scopes = list(_EXPOSURE_SCOPES[sens])
        return (len(scopes) > 0), scopes
    # Unknown / transitional / missing -> non-exposable.
    return False, []


def _refresh_state(fm: dict) -> str:
    # Minimal: we do not compute staleness policy here; report "current" when a
    # last_reviewed exists, else "unknown".
    return "current" if fm.get("last_reviewed") else "unknown"


def _note_entry(note) -> dict:
    fm = note.front_matter
    exposable, scopes = _exposability(fm)
    aliases = fm.get("aliases") or []
    if not isinstance(aliases, list):
        aliases = []
    prev = fm.get("previous_paths") or []
    if not isinstance(prev, list):
        prev = []
    return {
        "id": note.note_id,
        "canonical_path": note.rel_path,
        "title": fm.get("title") if isinstance(fm.get("title"), str) else note.rel_path,
        "status": fm.get("status"),
        "type": fm.get("type"),
        "authority_level": fm.get("authority_level"),
        "sensitivity": fm.get("sensitivity"),
        "domain": fm.get("domain"),
        "owner": fm.get("owner"),
        "aliases": aliases,
        "previous_paths": prev,
        "last_reviewed": _iso(fm.get("last_reviewed")),
        "refresh_state": _refresh_state(fm),
        "superseded_by": fm.get("superseded_by") or None,
        "exposable": exposable,
        "exposure_scopes": scopes,
    }


def _iso(value):
    import datetime as _dt

    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip() or None
    return None


def _index_notes(vault: Vault) -> list[dict]:
    """Accepted + governance notes carrying an id, sorted by id."""
    entries = []
    for n in vault.notes:
        if n.profile not in model.ID_REQUIRED_PROFILES:
            continue
        if not n.note_id:
            continue  # a blocking check already flags this; export only complete anchors
        entries.append(_note_entry(n))
    entries.sort(key=lambda e: (e["id"] or "", e["canonical_path"]))
    return entries


def _domain_entries(vault: Vault) -> list[dict]:
    reg = vault.root / "registry" / "knowledge-domains.yml"
    if not reg.is_file():
        return []
    try:
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    out = []
    for dom_id, spec in (data.get("domains") or {}).items():
        spec = spec or {}
        aliases = spec.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        out.append(
            {
                "id": dom_id,
                "aliases": sorted(aliases),
                "status": spec.get("status"),
            }
        )
    out.sort(key=lambda e: e["id"])
    return out


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(obj) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def build_index(vault: Vault, generated_at: str | None = None) -> dict:
    """Build the vault-index object. ``generated_at`` is omitted unless supplied."""
    notes = _index_notes(vault)
    domains = _domain_entries(vault)
    core = {
        "schema_version": SCHEMA_VERSION,
        "domains": domains,
        "notes": notes,
    }
    index_digest = _digest(core)
    result = {
        "schema_version": SCHEMA_VERSION,
        "index_digest": index_digest,
        "domains": domains,
        "notes": notes,
    }
    if generated_at is not None:
        result["generated_at"] = generated_at
    return result


def _notes_digest_by_domain(vault: Vault) -> dict[str, str]:
    """Per-domain digest over that domain's index-note entries.

    A domain's ``notes_digest`` changes only when a note *in that domain* changes,
    so a knowledge pack pinned to it is not invalidated by unrelated vault edits
    (e.g. an unrelated decision status change moving the whole-index digest).
    """
    by_domain: dict[str, list[dict]] = {}
    for entry in _index_notes(vault):
        dom = entry.get("domain")
        if not dom:
            continue
        by_domain.setdefault(dom, []).append(entry)
    result: dict[str, str] = {}
    for dom, entries in by_domain.items():
        entries.sort(key=lambda e: (e["id"] or "", e["canonical_path"]))
        result[dom] = _digest({"schema_version": SCHEMA_VERSION, "domain": dom, "notes": entries})
    return result


def build_domains(vault: Vault, generated_at: str | None = None) -> dict:
    reg = vault.root / "registry" / "knowledge-domains.yml"
    notes_digests = _notes_digest_by_domain(vault)
    domains: list[dict] = []
    if reg.is_file():
        try:
            data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        for dom_id, spec in (data.get("domains") or {}).items():
            spec = spec or {}
            aliases = spec.get("aliases") or []
            if not isinstance(aliases, list):
                aliases = []
            domains.append(
                {
                    "id": dom_id,
                    "title": spec.get("title"),
                    "status": spec.get("status"),
                    "routable": bool(spec.get("routable", False)),
                    "sensitivity_ceiling": spec.get("sensitivity_ceiling"),
                    "aliases": sorted(aliases),
                    "index_note": spec.get("index_note"),
                    "allowed_note_types": spec.get("allowed_note_types") or [],
                    # digest over this domain's accepted notes; empty domains get a
                    # stable digest of an empty note list.
                    "notes_digest": notes_digests.get(
                        dom_id, _digest({"schema_version": SCHEMA_VERSION, "domain": dom_id, "notes": []})
                    ),
                }
            )
    domains.sort(key=lambda e: e["id"])
    core = {"schema_version": SCHEMA_VERSION, "domains": domains}
    result = {
        "schema_version": SCHEMA_VERSION,
        "index_digest": _digest(core),
        "domains": domains,
    }
    if generated_at is not None:
        result["generated_at"] = generated_at
    return result


def dumps(obj: dict) -> str:
    """Pretty, deterministic JSON string (sorted keys, trailing newline)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
