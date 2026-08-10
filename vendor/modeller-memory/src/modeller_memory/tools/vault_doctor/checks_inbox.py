"""Inbox discovery-draft checks (schema section 5).

Validates files under ``inbox/discovery-drafts/**`` that declare
``type: discovery-draft`` against the inbound draft contract defined in
``modelling-knowledge/standards/discovery-draft-schema.md`` (which extends
Profile 5 of ``knowledge-metadata-standard.md``).

Scope:
  - Only notes classified as ``PROFILE_DISCOVERY`` are considered. The inbox
    ``README.md`` and any non-draft process docs (``type != discovery-draft``)
    are NOT drafts and are skipped (see ``model.classify_profile``).
  - A draft carrying a ``promoted_to:`` pointer is still a well-formed draft and
    is validated normally — promotion is not an error here.

Blocking checks (schema section 5, items 1-5):
  1. required discovery-draft fields present (the full section 2 required set);
  2. controlled-vocabulary values valid (status == draft, type ==
     discovery-draft, sensitivity in public|internal|restricted);
  3. sensitivity set;
  4. no accepted-note authority inflation (no authority_level / accepted id /
     other accepted-profile authority field; status must not be accepted/active);
  5. inbound sensitivity fence (H.3): a draft referencing restricted evidence
     must carry explicit ``sensitivity: restricted`` (mirrors the outbound
     ``check_sensitivity_fencing`` in checks.py).

Warning check (schema section 5, item 6):
  6. stale draft past a review-age threshold (based on a captured date if one is
     present; skipped gracefully when no date field exists).

These checks import shared helpers/finding types from ``checks`` to keep one
blocking/warning severity model.
"""

from __future__ import annotations

import datetime as _dt

from . import model
from .loader import Note, Vault

# Import shared primitives from the sibling checks module. checks_inbox is
# imported by checks (which registers these into its BLOCKING/WARNING lists), so
# only the leaf primitives are pulled in here to avoid a circular top-level use.
from .checks import (
    BLOCKING,
    WARNING,
    Finding,
    _coerce_date,
    _present,
    _resolve_to_note,
    _restricted_paths_and_ids,
)

# Full required field set for a discovery draft (schema section 2 / section 5.1).
# List-typed fields may be empty (`[]`) but must be present; `_present` treats an
# empty list/dict as present-but-declared.
DISCOVERY_DRAFT_REQUIRED_FIELDS = (
    "title",
    "status",
    "type",
    "owner",
    "source",
    "candidate_id",
    "origin_run",
    "authority_context_refs",
    "related_decisions",
    "sensitivity",
    "captured_from",
    "claim",
)

# Statuses that would make a draft masquerade as accepted knowledge (schema §3).
ACCEPTED_STATUSES = frozenset(["accepted", "active"])

# Front-matter keys that may carry a captured/drop timestamp for staleness.
_CAPTURED_DATE_KEYS = ("captured_at", "captured_from", "last_reviewed", "date")

# A draft older than this many days is flagged (warning only). An old but
# well-formed draft still passes.
STALE_DRAFT_DAYS = 90


def _drafts(vault: Vault) -> list[Note]:
    """Discovery drafts only (type: discovery-draft under inbox/discovery-drafts/).

    README.md and non-draft files are excluded because classify_profile only
    assigns PROFILE_DISCOVERY when the folder AND the declared type match.
    """
    return [n for n in vault.notes if n.profile == model.PROFILE_DISCOVERY]


# --------------------------------------------------------------------------- #
# BLOCKING                                                                     #
# --------------------------------------------------------------------------- #

def check_inbox_required_fields(vault: Vault) -> list[Finding]:
    """Every discovery-draft carries all section 2 required fields."""
    out: list[Finding] = []
    for n in _drafts(vault):
        for fld in DISCOVERY_DRAFT_REQUIRED_FIELDS:
            if not _present(n.front_matter.get(fld)):
                out.append(
                    Finding(BLOCKING, "draft-missing-required-field",
                            f"discovery draft is missing required field '{fld}'",
                            n.rel_path)
                )
    return out


def check_inbox_vocabularies(vault: Vault) -> list[Finding]:
    """status == draft, type == discovery-draft, sensitivity in the vocabulary."""
    out: list[Finding] = []
    for n in _drafts(vault):
        fm = n.front_matter

        st = fm.get("status")
        if _present(st) and st != "draft":
            out.append(
                Finding(BLOCKING, "draft-invalid-status",
                        f"discovery draft status must be 'draft', got '{st}'",
                        n.rel_path)
            )

        ty = fm.get("type")
        if _present(ty) and ty != "discovery-draft":
            out.append(
                Finding(BLOCKING, "draft-invalid-type",
                        f"discovery draft type must be 'discovery-draft', got '{ty}'",
                        n.rel_path)
            )

        sn = fm.get("sensitivity")
        if _present(sn) and sn not in model.SENSITIVITY_VALUES:
            if sn in model.TRANSITIONAL_SENSITIVITY:
                out.append(
                    Finding(BLOCKING, "draft-unnormalized-sensitivity",
                            f"transitional sensitivity label '{sn}' must be normalized to "
                            f"'{model.TRANSITIONAL_SENSITIVITY[sn]}'", n.rel_path)
                )
            else:
                out.append(
                    Finding(BLOCKING, "draft-invalid-sensitivity",
                            f"invalid sensitivity '{sn}'", n.rel_path)
                )
    return out


def check_inbox_sensitivity_set(vault: Vault) -> list[Finding]:
    """sensitivity must be present (schema §4.1)."""
    out: list[Finding] = []
    for n in _drafts(vault):
        if not _present(n.front_matter.get("sensitivity")):
            out.append(
                Finding(BLOCKING, "draft-missing-sensitivity",
                        "discovery draft must set 'sensitivity'", n.rel_path)
            )
    return out


def check_inbox_no_authority_inflation(vault: Vault) -> list[Finding]:
    """A draft must never masquerade as accepted (schema §3).

    Rejects: any accepted-authority field (authority_level, accepted id,
    domain), and a status of accepted/active.
    """
    out: list[Finding] = []
    for n in _drafts(vault):
        fm = n.front_matter
        for fld in model.FORBIDDEN_DRAFT_FIELDS:
            if _present(fm.get(fld)):
                out.append(
                    Finding(BLOCKING, "draft-authority-inflation",
                            f"discovery draft carries forbidden accepted-authority field "
                            f"'{fld}' — a draft must never masquerade as accepted",
                            n.rel_path)
                )
        st = fm.get("status")
        if _present(st) and st in ACCEPTED_STATUSES:
            out.append(
                Finding(BLOCKING, "draft-authority-inflation",
                        f"discovery draft has accepted-lifecycle status '{st}' — a draft "
                        f"must never masquerade as accepted", n.rel_path)
            )
    return out


def check_inbox_sensitivity_fence(vault: Vault) -> list[Finding]:
    """Inbound sensitivity fence (schema §4 / H.3).

    A draft that references restricted evidence must carry explicit
    ``sensitivity: restricted``. Mirrors the outbound ``check_sensitivity_fencing``
    on the inbound side. A restricted reference without a restricted
    classification is an unclassified restricted leak.
    """
    out: list[Finding] = []
    restricted_paths, restricted_ids = _restricted_paths_and_ids(vault)

    for n in _drafts(vault):
        fm = n.front_matter
        sens = fm.get("sensitivity")
        if sens == "restricted":
            continue  # properly fenced — nothing to leak-check

        leaks: list[str] = []

        # 1) self-declared derivation from restricted evidence.
        if fm.get("derived_from_restricted") is True:
            leaks.append("derived_from_restricted: true")

        # 2) an embedded source_path that points at a restricted note.
        val = fm.get("source_path")
        if isinstance(val, str) and val.strip():
            norm = val.strip().replace("\\", "/")
            if norm in restricted_paths:
                leaks.append(f"source_path points at restricted note '{norm}'")

        # 3) an authority_context_ref / link that resolves to a restricted note.
        refs: list[str] = []
        acr = fm.get("authority_context_refs")
        if isinstance(acr, list):
            refs.extend(str(x) for x in acr if isinstance(x, (str,)))
        elif isinstance(acr, str):
            refs.append(acr)
        for target in n.wikilinks + [
            t for t in n.md_links
            if not t.lower().startswith(("http://", "https://", "mailto:", "#"))
        ] + refs:
            resolved = _resolve_to_note(vault, str(target), n)
            if resolved is not None and resolved.sensitivity == "restricted":
                leaks.append(f"references restricted note '{resolved.rel_path}'")
            elif str(target).strip() in restricted_ids:
                leaks.append(f"references restricted id '{str(target).strip()}'")

        for leak in leaks:
            out.append(
                Finding(BLOCKING, "draft-restricted-leak",
                        f"discovery draft {leak} but is not classified "
                        f"'sensitivity: restricted' (unclassified restricted leak)",
                        n.rel_path)
            )
    return out


# --------------------------------------------------------------------------- #
# WARNING                                                                      #
# --------------------------------------------------------------------------- #

def warn_inbox_stale_drafts(vault: Vault) -> list[Finding]:
    """Flag drafts older than STALE_DRAFT_DAYS for board attention.

    Age is measured from the first parseable date among a small set of
    provenance keys. If no date field is present/parseable, the draft is skipped
    gracefully (no finding).
    """
    out: list[Finding] = []
    today = _dt.date.today()
    for n in _drafts(vault):
        d = None
        for key in _CAPTURED_DATE_KEYS:
            d = _coerce_date(n.front_matter.get(key))
            if d is not None:
                break
        if d is None:
            continue
        age = (today - d).days
        if age > STALE_DRAFT_DAYS:
            out.append(
                Finding(WARNING, "stale-discovery-draft",
                        f"discovery draft is {age} days old (> {STALE_DRAFT_DAYS}); "
                        f"flag for board review", n.rel_path)
            )
    return out


INBOX_BLOCKING_CHECKS = [
    check_inbox_required_fields,
    check_inbox_vocabularies,
    check_inbox_sensitivity_set,
    check_inbox_no_authority_inflation,
    check_inbox_sensitivity_fence,
]

INBOX_WARNING_CHECKS = [
    warn_inbox_stale_drafts,
]
