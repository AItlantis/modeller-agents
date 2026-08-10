"""Controlled vocabularies, metadata profiles, and classification rules.

Sourced verbatim from the vault's own declared rules:
  - modelling-knowledge/standards/knowledge-metadata-standard.md
  - modelling-knowledge/docs/dev/vault-optimisation-plan.md (Phase E, profiles)
  - modelling-knowledge/docs/dev/vault-alignment-plan.md (Vault Eligibility, index contract)

vault_doctor enforces these; it does not author them. If the vault's standard
changes, this module is updated to track it — the vault remains the authority.
"""

from __future__ import annotations

# --- Controlled vocabularies (shared across all profiles) --------------------

STATUS_VALUES = frozenset(
    ["draft", "proposed", "accepted", "active", "superseded", "deprecated", "historical"]
)
AUTHORITY_LEVEL_VALUES = frozenset(
    ["authoritative", "supporting", "evidence", "historical"]
)
SENSITIVITY_VALUES = frozenset(["public", "internal", "restricted"])

# Transitional labels that the standard says must be normalized before pack
# eligibility. They are NOT valid final values; their presence is a finding.
TRANSITIONAL_SENSITIVITY = {
    "public-internal": "internal",
    "private-internal": "restricted",
}

# --- type vocabularies, profile-specific -------------------------------------

CONTEXT_TYPES = frozenset(["context"])
ACCEPTED_KNOWLEDGE_TYPES = frozenset(["tutorial", "how-to", "explanation", "reference"])
GOVERNANCE_TYPES = frozenset(["repository-map", "standard", "decision"])
PLANNING_EVIDENCE_TYPES = frozenset(
    ["baseline", "inventory", "audit", "process", "evidence"]
)
DISCOVERY_DRAFT_TYPES = frozenset(["discovery-draft"])

# --- Profile identifiers ------------------------------------------------------

PROFILE_CONTEXT = "context"
PROFILE_ACCEPTED = "accepted-knowledge"
PROFILE_GOVERNANCE = "governance"
PROFILE_PLANNING = "planning-evidence"
PROFILE_DISCOVERY = "discovery-draft"
PROFILE_UNCLASSIFIED = "unclassified"

PROFILE_TYPES = {
    PROFILE_CONTEXT: CONTEXT_TYPES,
    PROFILE_ACCEPTED: ACCEPTED_KNOWLEDGE_TYPES,
    PROFILE_GOVERNANCE: GOVERNANCE_TYPES,
    PROFILE_PLANNING: PLANNING_EVIDENCE_TYPES,
    PROFILE_DISCOVERY: DISCOVERY_DRAFT_TYPES,
}

# Required front-matter fields per profile (blocking when the note is
# accepted/governance). Presence is required; a field present with an empty
# value is treated as missing.
REQUIRED_FIELDS = {
    PROFILE_CONTEXT: ["title", "status", "type", "owner", "authority_level"],
    PROFILE_ACCEPTED: [
        "title",
        "status",
        "type",
        "owner",
        "id",
        "domain",
        "authority_level",
        "sensitivity",
        "last_reviewed",
    ],
    PROFILE_GOVERNANCE: [
        "title",
        "status",
        "type",
        "owner",
        "id",
        "authority_level",
        "sensitivity",
        "last_reviewed",
    ],
    PROFILE_PLANNING: ["title", "status", "type", "owner", "authority_level"],
    PROFILE_DISCOVERY: ["title", "status", "type", "owner", "sensitivity"],
}

# Profiles that require a stable, immutable id and are subject to the strictest
# blocking checks (missing id, missing required fields, etc.).
ID_REQUIRED_PROFILES = frozenset([PROFILE_ACCEPTED, PROFILE_GOVERNANCE])

# Accepted-authority fields a discovery draft must NEVER carry (Phase H.2).
FORBIDDEN_DRAFT_FIELDS = ("id", "authority_level", "domain")

# Personal Obsidian files that must not be tracked (vault-optimisation B.5).
FORBIDDEN_OBSIDIAN_FILES = frozenset(
    [
        ".obsidian/workspace.json",
        ".obsidian/workspace-mobile.json",
        ".obsidian/graph.json",
        ".obsidian/bookmarks.json",
    ]
)

# Directory prefixes (POSIX, vault-relative) whose notes are ineligible for pack
# routing by default (vault-alignment Vault Eligibility). Used to scope some
# warnings, not to exclude from parsing.
INELIGIBLE_PREFIXES = (
    "inbox/",
    "docs/dev/baselines/",
    "docs/dev/inventories/",
    "docs/audit/",
)


def classify_profile(rel_posix_path: str, front_matter: dict) -> str:
    """Classify a note into one of the metadata profiles.

    Classification is by directory location first (matching the standard's
    "Applies to" mapping), then falls back to the declared ``type``. Notes that
    match no profile are ``PROFILE_UNCLASSIFIED`` (not a blocking finding on
    their own, but they are skipped by profile-required-field checks).
    """
    p = rel_posix_path
    declared_type = front_matter.get("type")

    # Discovery drafts (inbox). A file in this folder is a *discovery draft* only
    # when it declares `type: discovery-draft`. README/process docs that merely
    # document the inbox contract are not drafts and fall through to normal rules.
    if p.startswith("inbox/discovery-drafts/") and declared_type == "discovery-draft":
        return PROFILE_DISCOVERY

    # Governance
    if (
        p.startswith("repository_maps/")
        or p.startswith("standards/")
        or p.startswith("decisions/")
    ):
        return PROFILE_GOVERNANCE

    # Accepted knowledge
    if p.startswith("domains/") or p.startswith("glossary/"):
        return PROFILE_ACCEPTED

    # Planning / evidence
    if (
        p.startswith("docs/dev/baselines/")
        or p.startswith("docs/dev/inventories/")
        or p.startswith("docs/audit/")
    ):
        return PROFILE_PLANNING

    # Context / entry-point files (top-level well-known names)
    basename = p.rsplit("/", 1)[-1]
    if "/" not in p and basename in {
        "README.md",
        "project-context.md",
        "handoff.md",
        "AGENTS.md",
    }:
        return PROFILE_CONTEXT

    # Fall back to declared type.
    declared = front_matter.get("type")
    if isinstance(declared, str):
        for profile, types in PROFILE_TYPES.items():
            if declared in types:
                return profile

    return PROFILE_UNCLASSIFIED


def is_authority_bearing(profile: str, front_matter: dict) -> bool:
    """True for accepted/governance notes whose status is accepted or active.

    These are the notes for which id, required fields, and vocabulary checks are
    blocking (per Phase E and the standard's stable-identity rules).
    """
    if profile not in ID_REQUIRED_PROFILES:
        return False
    status = front_matter.get("status")
    return status in ("accepted", "active")
