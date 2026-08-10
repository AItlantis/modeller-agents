"""Blocking and warning checks over a loaded vault.

Check list is drawn EXACTLY from:
  - vault-alignment-plan.md "Validation Additions / vault_doctor"
  - vault-optimisation-plan.md Phase E

Blocking checks fail the ``check`` command (non-zero exit). Warning checks never
fail the run unless ``--warnings-as-errors`` is set. Some pack-layer warnings
require a knowledge-pack layer that does not exist yet; those are reported as
NOT-YET-APPLICABLE rather than emitted as findings.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

import yaml

from . import model
from .loader import Note, Vault

BLOCKING = "blocking"
WARNING = "warning"

# Heuristics / thresholds (warning-only).
LARGE_NOTE_BYTES = 50_000
STALE_REVIEW_DAYS = 365
SPARSE_LINK_MIN = 1  # authority-bearing notes with zero internal links → sparse


@dataclass(frozen=True)
class Finding:
    severity: str  # BLOCKING or WARNING
    check: str  # short machine id, e.g. "duplicate-note-id"
    message: str
    path: str | None = None

    def format(self) -> str:
        loc = f" [{self.path}]" if self.path else ""
        return f"{self.severity.upper():8} {self.check}: {self.message}{loc}"


def _present(value) -> bool:
    """A field 'present' means non-None and, for strings, non-empty after strip."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return True  # empty list/dict still counts as present (declared)
    return True


def _restricted_paths_and_ids(vault: Vault) -> tuple[set[str], set[str]]:
    """Rel paths and ids of notes explicitly marked restricted."""
    paths, ids = set(), set()
    for n in vault.notes:
        if n.sensitivity == "restricted":
            paths.add(n.rel_path)
            if n.note_id:
                ids.add(n.note_id)
    return paths, ids


# --------------------------------------------------------------------------- #
# BLOCKING CHECKS                                                             #
# --------------------------------------------------------------------------- #

def check_duplicate_ids(vault: Vault) -> list[Finding]:
    out = []
    for note_id, notes in sorted(vault.by_id.items()):
        if len(notes) > 1:
            paths = ", ".join(sorted(n.rel_path for n in notes))
            out.append(
                Finding(
                    BLOCKING,
                    "duplicate-note-id",
                    f"note id '{note_id}' is declared by {len(notes)} notes: {paths}",
                )
            )
    return out


def check_missing_ids(vault: Vault) -> list[Finding]:
    """Accepted/governance notes (status accepted|active) must carry a stable id."""
    out = []
    for n in vault.notes:
        if model.is_authority_bearing(n.profile, n.front_matter) and not n.note_id:
            out.append(
                Finding(
                    BLOCKING,
                    "missing-stable-id",
                    f"{n.profile} note with status "
                    f"'{n.status}' is missing a stable 'id'",
                    n.rel_path,
                )
            )
    return out


def check_vocabularies(vault: Vault) -> list[Finding]:
    out = []
    for n in vault.notes:
        if n.profile == model.PROFILE_UNCLASSIFIED:
            continue
        fm = n.front_matter
        st = fm.get("status")
        if _present(st) and st not in model.STATUS_VALUES:
            out.append(Finding(BLOCKING, "invalid-status", f"invalid status '{st}'", n.rel_path))
        al = fm.get("authority_level")
        if _present(al) and al not in model.AUTHORITY_LEVEL_VALUES:
            out.append(
                Finding(BLOCKING, "invalid-authority-level",
                        f"invalid authority_level '{al}'", n.rel_path)
            )
        sn = fm.get("sensitivity")
        if _present(sn) and sn not in model.SENSITIVITY_VALUES:
            # Distinguish an un-normalized transitional label for a clearer message.
            if sn in model.TRANSITIONAL_SENSITIVITY:
                out.append(
                    Finding(BLOCKING, "unnormalized-sensitivity",
                            f"transitional sensitivity label '{sn}' must be normalized to "
                            f"'{model.TRANSITIONAL_SENSITIVITY[sn]}'", n.rel_path)
                )
            else:
                out.append(
                    Finding(BLOCKING, "invalid-sensitivity",
                            f"invalid sensitivity '{sn}'", n.rel_path)
                )
        # type must belong to the note's profile vocabulary.
        ty = fm.get("type")
        allowed = model.PROFILE_TYPES.get(n.profile)
        if _present(ty) and allowed is not None and ty not in allowed:
            out.append(
                Finding(BLOCKING, "invalid-type",
                        f"type '{ty}' is not valid for the {n.profile} profile", n.rel_path)
            )
    return out


def check_required_fields(vault: Vault) -> list[Finding]:
    """Accepted/governance notes must carry all required profile fields."""
    out = []
    for n in vault.notes:
        if not model.is_authority_bearing(n.profile, n.front_matter):
            continue
        required = model.REQUIRED_FIELDS.get(n.profile, [])
        for fld in required:
            if not _present(n.front_matter.get(fld)):
                out.append(
                    Finding(BLOCKING, "missing-required-field",
                            f"missing required field '{fld}' for {n.profile} profile",
                            n.rel_path)
                )
    return out


def check_front_matter_parse(vault: Vault) -> list[Finding]:
    out = []
    for n in vault.notes:
        if n.front_matter_error:
            out.append(
                Finding(BLOCKING, "front-matter-parse-error",
                        n.front_matter_error, n.rel_path)
            )
    return out


def check_broken_links(vault: Vault) -> list[Finding]:
    out = []
    for n in vault.notes:
        for target in n.wikilinks:
            if not vault.resolves(target, n):
                out.append(
                    Finding(BLOCKING, "broken-internal-link",
                            f"wikilink '[[{target}]]' does not resolve to a note",
                            n.rel_path)
                )
        for target in n.md_links:
            # Only internal markdown links (relative, ending .md) are integrity-checked.
            t = target.strip()
            low = t.lower()
            if low.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Ignore links to non-markdown assets.
            base = t.split("#", 1)[0].split("?", 1)[0]
            if not base.endswith(".md"):
                continue
            if not vault.resolves(target, n):
                out.append(
                    Finding(BLOCKING, "broken-internal-link",
                            f"markdown link '({target})' does not resolve to a note",
                            n.rel_path)
                )
    return out


_INDEX_ROW_RE = re.compile(
    r"\[\[decisions/(?P<slug>[^\]\|#]+)(?:\|[^\]]+)?\]\]\s*\|\s*(?P<status>[A-Za-z\-]+)"
)


def check_decision_index_parity(vault: Vault) -> list[Finding]:
    """decisions-index.md status column must match each decision's own status.

    The index lists rows of the form:
        | [[decisions/0004-...]] | accepted | ... |
    Each linked decision note has its own front-matter status. A mismatch is a
    blocking finding. 'coordination' is a valid index-only label for cross-repo
    records and is not compared against a note status.
    """
    out = []
    index = vault.by_rel_path.get("decisions/decisions-index.md")
    if index is None:
        return out
    # Map decision slug -> note status.
    by_slug = {}
    for n in vault.notes:
        if n.rel_path.startswith("decisions/") and n.rel_path.endswith(".md"):
            slug = n.rel_path[len("decisions/"):-3]
            by_slug[slug] = n.status
    for m in _INDEX_ROW_RE.finditer(index.body):
        slug = m.group("slug").strip()
        idx_status = m.group("status").strip().lower()
        if idx_status in ("coordination",):
            continue
        note_status = by_slug.get(slug)
        if note_status is None:
            out.append(
                Finding(BLOCKING, "decision-index-missing-note",
                        f"decisions-index references '{slug}' but no such decision note exists",
                        index.rel_path)
            )
        elif note_status != idx_status:
            out.append(
                Finding(BLOCKING, "decision-index-status-mismatch",
                        f"decisions-index lists '{slug}' as '{idx_status}' but the note's "
                        f"status is '{note_status}'", index.rel_path)
            )
    return out


def check_registry_map_parity(vault: Vault) -> list[Finding]:
    """Every repository in registry/repositories.yml has a repository_maps/<name>.md
    and vice versa."""
    out = []
    reg = vault.root / "registry" / "repositories.yml"
    if not reg.is_file():
        return out
    try:
        data = yaml.safe_load(reg.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [Finding(BLOCKING, "registry-parse-error",
                        f"cannot parse registry/repositories.yml: {exc}",
                        "registry/repositories.yml")]
    repos = set((data or {}).get("repositories", {}).keys())
    # Maps present (exclude index.md).
    maps = set()
    for n in vault.notes:
        if n.rel_path.startswith("repository_maps/") and n.rel_path.endswith(".md"):
            base = n.rel_path[len("repository_maps/"):-3]
            if base in ("index", "_index"):
                continue
            maps.add(base)
    for repo in sorted(repos - maps):
        out.append(
            Finding(BLOCKING, "registry-map-parity",
                    f"registry declares repository '{repo}' but repository_maps/{repo}.md is missing",
                    "registry/repositories.yml")
        )
    for m in sorted(maps - repos):
        out.append(
            Finding(BLOCKING, "registry-map-parity",
                    f"repository_maps/{m}.md exists but registry declares no repository '{m}'",
                    f"repository_maps/{m}.md")
        )
    return out


def check_forbidden_obsidian_tracked(vault: Vault) -> list[Finding]:
    out = []
    if not vault.tracked_files:
        return out  # git not available / not a repo — skip silently
    tracked = set(vault.tracked_files)
    for forbidden in sorted(model.FORBIDDEN_OBSIDIAN_FILES):
        if forbidden in tracked:
            out.append(
                Finding(BLOCKING, "forbidden-obsidian-tracked",
                        f"personal Obsidian file '{forbidden}' is git-tracked; it must be "
                        f"untracked (git rm --cached) and gitignored", forbidden)
            )
    return out


def check_sensitivity_fencing(vault: Vault) -> list[Finding]:
    """public notes must not link to / embed / derive-from restricted content
    without a passing redaction review."""
    out = []
    restricted_paths, restricted_ids = _restricted_paths_and_ids(vault)
    # Build a lookup of link target -> resolved restricted note (best effort).
    for n in vault.notes:
        if n.sensitivity != "public":
            continue
        fm = n.front_matter

        # 1) public + derived_from_restricted without passing redaction_review.
        if fm.get("derived_from_restricted") is True:
            rr = fm.get("redaction_review") or {}
            rr_status = rr.get("status") if isinstance(rr, dict) else None
            if rr_status != "passed":
                out.append(
                    Finding(BLOCKING, "public-derived-from-restricted",
                            "public note has derived_from_restricted: true without "
                            "redaction_review.status: passed", n.rel_path)
                )

        # 2) public note directly linking to a restricted note.
        for target in n.wikilinks + [
            t for t in n.md_links
            if not t.lower().startswith(("http://", "https://", "mailto:", "#"))
        ]:
            resolved = _resolve_to_note(vault, target, n)
            if resolved is not None and resolved.sensitivity == "restricted":
                out.append(
                    Finding(BLOCKING, "public-links-restricted",
                            f"public note links directly to restricted note "
                            f"'{resolved.rel_path}'", n.rel_path)
                )

        # 3) public note embedding a restricted source path (source_path /
        #    source_repositories referencing a restricted note path).
        for key in ("source_path",):
            val = fm.get(key)
            if isinstance(val, str) and val.strip():
                norm = val.strip().replace("\\", "/")
                if norm in restricted_paths:
                    out.append(
                        Finding(BLOCKING, "public-embeds-restricted-path",
                                f"public note's {key} points at restricted note '{norm}'",
                                n.rel_path)
                    )
    return out


def _load_domain_registry(vault: Vault):
    reg = vault.root / "registry" / "knowledge-domains.yml"
    if not reg.is_file():
        return {}, None
    try:
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return None, str(exc)
    domains = data.get("domains") or {}
    if not isinstance(domains, dict):
        return None, "top-level 'domains' is not a mapping"
    return domains, None


def _active_domain_specs(vault: Vault) -> tuple[dict, list[Finding]]:
    domains, err = _load_domain_registry(vault)
    if err is not None:
        return {}, [
            Finding(
                BLOCKING,
                "knowledge-domain-registry-parse",
                f"cannot parse registry/knowledge-domains.yml: {err}",
                "registry/knowledge-domains.yml",
            )
        ]
    active = {}
    for dom_id, spec in domains.items():
        spec = spec or {}
        if spec.get("status") == "active" or spec.get("routable") is True:
            active[dom_id] = spec
    return active, []


def _eligible_for_domain(note: Note, dom_id: str, spec: dict) -> bool:
    fm = note.front_matter
    if note.profile != model.PROFILE_ACCEPTED:
        return False
    if fm.get("domain") != dom_id:
        return False
    if fm.get("status") != "accepted":
        return False
    if fm.get("authority_level") not in ("authoritative", "supporting"):
        return False
    if not note.note_id:
        return False
    if fm.get("superseded_by"):
        return False
    if fm.get("sensitivity") == "restricted":
        return False
    allowed_types = spec.get("allowed_note_types") or []
    if allowed_types and fm.get("type") not in allowed_types:
        return False
    ceiling = spec.get("sensitivity_ceiling")
    sens = fm.get("sensitivity")
    if ceiling == "public" and sens != "public":
        return False
    if ceiling == "internal" and sens not in ("public", "internal"):
        return False
    return True


def check_knowledge_domain_registry(vault: Vault) -> list[Finding]:
    """Validate active/routable domain registry entries.

    Draft domains may be incomplete. Active or routable domains must satisfy the
    VA2 gate: stable registry id, aliases, sensitivity ceiling, index note, at
    least one eligible accepted note, and a matching stable index-note id.
    """
    active, parse_findings = _active_domain_specs(vault)
    out = list(parse_findings)
    if parse_findings:
        return out

    valid_sensitivity = {"public", "internal", "restricted"}
    for dom_id, spec in sorted(active.items()):
        if not isinstance(dom_id, str) or not dom_id.strip():
            out.append(
                Finding(
                    BLOCKING,
                    "invalid-domain-id",
                    "active domain has an empty or non-string id",
                    "registry/knowledge-domains.yml",
                )
            )
            continue
        if spec.get("status") != "active":
            out.append(
                Finding(
                    BLOCKING,
                    "active-domain-status",
                    f"domain '{dom_id}' is routable but status is not 'active'",
                    "registry/knowledge-domains.yml",
                )
            )
        if spec.get("routable") is not True:
            out.append(
                Finding(
                    BLOCKING,
                    "active-domain-routable",
                    f"domain '{dom_id}' is active but routable is not true",
                    "registry/knowledge-domains.yml",
                )
            )
        aliases = spec.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            out.append(
                Finding(
                    BLOCKING,
                    "active-domain-missing-aliases",
                    f"active domain '{dom_id}' has no aliases",
                    "registry/knowledge-domains.yml",
                )
            )
        ceiling = spec.get("sensitivity_ceiling")
        if ceiling not in valid_sensitivity:
            out.append(
                Finding(
                    BLOCKING,
                    "active-domain-sensitivity-ceiling",
                    f"active domain '{dom_id}' has invalid sensitivity_ceiling '{ceiling}'",
                    "registry/knowledge-domains.yml",
                )
            )
        index_id = spec.get("index_note")
        index_matches = vault.by_id.get(index_id) if isinstance(index_id, str) else None
        if not index_matches:
            out.append(
                Finding(
                    BLOCKING,
                    "active-domain-index-note",
                    f"active domain '{dom_id}' index_note '{index_id}' does not resolve to a note id",
                    "registry/knowledge-domains.yml",
                )
            )
        else:
            index_note = index_matches[0]
            if index_note.front_matter.get("domain") != dom_id:
                out.append(
                    Finding(
                        BLOCKING,
                        "active-domain-index-domain",
                        f"active domain '{dom_id}' index_note '{index_id}' has domain "
                        f"'{index_note.front_matter.get('domain')}'",
                        index_note.rel_path,
                    )
                )
            if index_note.status != "accepted":
                out.append(
                    Finding(
                        BLOCKING,
                        "active-domain-index-status",
                        f"active domain '{dom_id}' index_note '{index_id}' is not accepted",
                        index_note.rel_path,
                    )
                )
        eligible = [n for n in vault.notes if _eligible_for_domain(n, dom_id, spec)]
        non_index = [n for n in eligible if n.note_id != index_id]
        if not non_index:
            out.append(
                Finding(
                    BLOCKING,
                    "active-domain-no-eligible-notes",
                    f"active domain '{dom_id}' has no eligible accepted non-index notes",
                    "registry/knowledge-domains.yml",
                )
            )
    return out


def check_note_domains_in_registry(vault: Vault) -> list[Finding]:
    """Accepted domain notes must use a domain declared in knowledge-domains.yml."""
    domains, err = _load_domain_registry(vault)
    if err is not None:
        return []  # parse error is reported by check_knowledge_domain_registry
    out = []
    domain_ids = set(domains.keys())
    for n in vault.notes:
        if n.profile != model.PROFILE_ACCEPTED:
            continue
        if n.status != "accepted":
            continue
        dom = n.front_matter.get("domain")
        if dom not in domain_ids:
            out.append(
                Finding(
                    BLOCKING,
                    "note-domain-absent-from-registry",
                    f"accepted note declares domain '{dom}' absent from registry/knowledge-domains.yml",
                    n.rel_path,
                )
            )
    return out


def check_domain_alias_collisions(vault: Vault) -> list[Finding]:
    """Aliases must resolve to a single canonical domain."""
    domains, err = _load_domain_registry(vault)
    if err is not None:
        return []
    seen: dict[str, str] = {}
    out = []
    for dom_id, spec in sorted(domains.items()):
        spec = spec or {}
        aliases = spec.get("aliases") or []
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            key = alias.strip().lower()
            if not key:
                continue
            if key in seen and seen[key] != dom_id:
                out.append(
                    Finding(
                        BLOCKING,
                        "duplicate-domain-alias",
                        f"alias '{alias}' is used by both '{seen[key]}' and '{dom_id}'",
                        "registry/knowledge-domains.yml",
                    )
                )
            else:
                seen[key] = dom_id
    return out


def _resolve_to_note(vault: Vault, link_target: str, from_note: Note):
    """Best-effort resolution of a link target to a concrete Note (or None)."""
    t = link_target.strip().split("#", 1)[0].split("?", 1)[0].strip().replace("\\", "/")
    if not t:
        return None
    for cand in (t, t + ".md", t[:-3] if t.endswith(".md") else None):
        if cand and cand in vault.by_rel_path:
            return vault.by_rel_path[cand]
    base = t.rsplit("/", 1)[-1]
    base_noext = base[:-3] if base.endswith(".md") else base
    matches = vault.by_basename_noext.get(base_noext)
    if matches and len(matches) == 1:
        return matches[0]
    return None


BLOCKING_CHECKS = [
    check_front_matter_parse,
    check_duplicate_ids,
    check_missing_ids,
    check_vocabularies,
    check_required_fields,
    check_broken_links,
    check_decision_index_parity,
    check_registry_map_parity,
    check_forbidden_obsidian_tracked,
    check_sensitivity_fencing,
    check_knowledge_domain_registry,
    check_note_domains_in_registry,
    check_domain_alias_collisions,
]
# Inbox discovery-draft blocking checks (schema section 5) are appended below,
# after this module is fully defined, from checks_inbox (which imports shared
# primitives from here). See the bottom of this module.


# --------------------------------------------------------------------------- #
# WARNING CHECKS                                                             #
# --------------------------------------------------------------------------- #

def _internal_link_count(vault: Vault, n: Note) -> int:
    count = 0
    for target in n.wikilinks:
        if vault.resolves(target, n):
            count += 1
    for target in n.md_links:
        low = target.lower()
        if low.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target.split("#", 1)[0].endswith(".md") and vault.resolves(target, n):
            count += 1
    return count


def warn_orphan_notes(vault: Vault) -> list[Finding]:
    """Authority-bearing notes not referenced by any other note (no inbound link)."""
    referenced: set[str] = set()
    for n in vault.notes:
        for target in n.wikilinks + n.md_links:
            r = _resolve_to_note(vault, target, n)
            if r is not None:
                referenced.add(r.rel_path)
    out = []
    for n in vault.notes:
        if not model.is_authority_bearing(n.profile, n.front_matter):
            continue
        if n.rel_path not in referenced:
            out.append(
                Finding(WARNING, "orphan-note",
                        "authority-bearing note has no inbound internal links", n.rel_path)
            )
    return out


def warn_large_notes(vault: Vault) -> list[Finding]:
    return [
        Finding(WARNING, "large-note",
                f"note is {n.size_bytes} bytes (> {LARGE_NOTE_BYTES})", n.rel_path)
        for n in vault.notes
        if n.size_bytes > LARGE_NOTE_BYTES
    ]


def warn_stale_last_reviewed(vault: Vault) -> list[Finding]:
    out = []
    today = _dt.date.today()
    for n in vault.notes:
        lr = n.front_matter.get("last_reviewed")
        d = _coerce_date(lr)
        if d is None:
            continue
        age = (today - d).days
        if age > STALE_REVIEW_DAYS:
            out.append(
                Finding(WARNING, "stale-last-reviewed",
                        f"last_reviewed is {age} days old (> {STALE_REVIEW_DAYS})", n.rel_path)
            )
    return out


def warn_duplicate_filenames(vault: Vault) -> list[Finding]:
    out = []
    for base_noext, notes in sorted(vault.by_basename_noext.items()):
        if len(notes) > 1:
            paths = ", ".join(sorted(n.rel_path for n in notes))
            out.append(
                Finding(WARNING, "duplicate-filename",
                        f"filename '{base_noext}.md' appears {len(notes)} times: {paths}")
            )
    return out


def warn_sparse_links(vault: Vault) -> list[Finding]:
    out = []
    for n in vault.notes:
        if not model.is_authority_bearing(n.profile, n.front_matter):
            continue
        if _internal_link_count(vault, n) < SPARSE_LINK_MIN:
            out.append(
                Finding(WARNING, "sparse-links",
                        "authority-bearing note has no outbound internal links", n.rel_path)
            )
    return out


def warn_missing_aliases(vault: Vault) -> list[Finding]:
    """Governance notes without an aliases field (search discoverability)."""
    out = []
    for n in vault.notes:
        if n.profile != model.PROFILE_GOVERNANCE:
            continue
        if not model.is_authority_bearing(n.profile, n.front_matter):
            continue
        if "aliases" not in n.front_matter:
            out.append(
                Finding(WARNING, "missing-aliases",
                        "governance note has no 'aliases' field", n.rel_path)
            )
    return out


WARNING_CHECKS = [
    warn_orphan_notes,
    warn_large_notes,
    warn_stale_last_reviewed,
    warn_duplicate_filenames,
    warn_sparse_links,
    warn_missing_aliases,
]

# Warnings from the plans that require a knowledge-pack layer that does not exist
# in this vault yet. Reported as not-yet-applicable rather than emitted.
NOT_YET_APPLICABLE = [
    "accepted note not referenced by any pack (needs the pack layer)",
    "active pack pointer to draft/superseded/restricted note (needs the pack layer)",
    "pack referencing too many notes (needs the pack layer)",
]


def _coerce_date(value):
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%Y-%m-%d",):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return None


def run_all(vault: Vault) -> tuple[list[Finding], list[Finding]]:
    """Return (blocking_findings, warning_findings)."""
    blocking: list[Finding] = []
    for chk in BLOCKING_CHECKS:
        blocking.extend(chk(vault))
    warnings: list[Finding] = []
    for chk in WARNING_CHECKS:
        warnings.extend(chk(vault))
    return blocking, warnings


# --------------------------------------------------------------------------- #
# Register inbox discovery-draft checks (schema section 5).                    #
#                                                                              #
# checks_inbox imports shared primitives (Finding, _present, _resolve_to_note, #
# _restricted_paths_and_ids, _coerce_date) from THIS module, so it is imported #
# here at the bottom — after those primitives are defined — and its check      #
# lists are appended to the blocking/warning registries. This keeps the inbox  #
# checks in the same severity model and makes `check` run them by default.     #
# --------------------------------------------------------------------------- #
from . import checks_inbox as _checks_inbox  # noqa: E402  (deferred by design)

BLOCKING_CHECKS.extend(_checks_inbox.INBOX_BLOCKING_CHECKS)
WARNING_CHECKS.extend(_checks_inbox.INBOX_WARNING_CHECKS)
