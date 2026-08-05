# Typed Packs & The Knowledge Axis

Status: pilot architecture with D3-D5 condition enforcement implemented and one active knowledge pack. Date: 2026-07-12. Owner: modeller-agents.

This document captures the additive second routing axis. D1 and D2 from the decision register are already implemented in the current single-axis router. D3-D6 were ruled on 2026-07-12; D3/D4/D5 were accepted with conditions and those conditions now have medium-effort runtime enforcement in `src/modeller/knowledge_packs.py`, `src/modeller/route.py`, and `src/modeller/doctor.py`. The first active `kind = "knowledge"` pack is `reference-packs/domains/accessibility.toml`.

## Core Idea

Routing currently resolves WHERE the work happens:

```text
intent.target_repository -> bundles/<target>.bundle.json -> referencePacks[]
```

The proposed extension adds WHAT knowledge the work needs:

```text
intent.domains[] -> reference-packs/domains/_registry.toml -> knowledge packs
```

Skills stay generic methods. Packs carry repository facts or knowledge facts. Domain names stay in data files, not in `route.py` branches or envelope enums.

## Current State

The current router is single-axis and deterministic:

- `route_envelope` reads `intent.target_repository` and loads `bundles/{target_repository}.bundle.json`.
- `intent.requested_capability` is resolved through `CAPABILITY_SKILLS`.
- Unknown capabilities fail instead of silently falling back to `workflow`.
- The selected skill must be declared by the selected bundle.
- At least one selected valid reference pack must authorize the selected skill through `central_skills`.
- Bundles declare `routingKeyKind` as `repository` or `repository-class`.
- `RouteDecision` emits `target_repository`, `skill`, `bundle`, `routing_key_kind`, `reference_packs`, `consent_required`, `max_risk_level`, `warnings`, and `errors`.

Route decisions now include additive knowledge fields (`knowledge_domains`, `knowledge_packs`, and `knowledge_budget`) when `intent.domains[]` or bundle `defaultKnowledge[]` is present. Existing envelopes without domains remain single-axis routes.

The implemented enforcement is deliberately bounded:

- `intent.domains[]` and bundle `defaultKnowledge[]` form an ordered union with per-domain source provenance.
- `defaultKnowledge[]` is capped at 2 domains per bundle.
- total selected knowledge packs are capped at 3, with note-selection budget fields emitted for audit.
- skill `domain_affinity` accepts only `none`, `explicit`, or `routed`; wildcards are invalid.
- `routed` does not infer or expand domains; it only permits domains already selected by the route.
- knowledge-pack validation runs on route and doctor, using current vault exports when a domain pack exists.
- the active accessibility pack references vault note IDs only and carries `authority_context`; it contains no copied knowledge body.

## Proposed Additive Changes

| Artifact | Current | Proposed |
| --- | --- | --- |
| Reference pack | Untyped repo fact pack | Add `kind = "repo"` or `kind = "knowledge"` |
| Bundle | `routingKeyKind`, `skills[]`, `referencePacks[]` | Add `defaultKnowledge[]` |
| Skill frontmatter | `name`, `description`, `metadata.version`, `metadata.author` | Add `domain_affinity` |
| Context envelope intent | `user_text`, `requested_capability`, `target_repository`, `target_backend` | Add `domains[]` |
| Domain registry | None | Add `reference-packs/domains/_registry.toml` |
| Knowledge pack | None | Add `reference-packs/domains/<domain>.toml` |

## Routing Flow

```text
USER INTENT
  intent.target_repository
  intent.domains[]
        |
        v
route.py
  axis 1: target_repository -> bundle -> referencePacks[]
  axis 2: domains[] -> domains/_registry.toml -> knowledge pack paths
        |
        v
RouteDecision
  reference_packs[]
  knowledge_packs[]
        |
        v
SKILL
  loads reference_packs always
  loads knowledge_packs only when allowed by domain_affinity
```

When the envelope carries no `intent.domains`, the orchestration skill may infer candidate domains from task context and re-invoke routing with explicit domains. That inference must be auditable; it must not happen silently inside `route.py`.

## Axis A1 - Routing

Keep `intent.target_repository` as the WHERE axis. Add `intent.domains[]` as the WHAT axis. Domain entries are free strings resolved only through registry data. A typo or unknown domain must become an explicit routing decision, not a silent drop; this is still open in the review backlog.

Open decision: D3 decides whether request-level domains union with, or override, bundle `defaultKnowledge[]`.

## Axis A2 - Pack Typing

Add two pack kinds:

- `kind = "repo"` for current repository fact packs.
- `kind = "knowledge"` for domain knowledge packs under `reference-packs/domains/`.

Knowledge packs should point into `modelling-knowledge` with note references; they should not copy note bodies or take write authority over the vault.

Open decision: D5 decides whether knowledge packs are generated from the vault index or hand-authored.

## Axis A3 - Skill And Method

Skills remain methods. Packs carry knowledge. `domain_affinity` would declare which knowledge packs a skill may consume, or `["*"]` for broad skills.

Open decision: D4 decides whether wildcard affinity is acceptable for broad skills such as `workflow` and `review`.

## Axis A4 - Knowledge Vault Scope

This proposal does not decide what belongs in `modelling-knowledge`. It assumes durable cross-repo domain knowledge belongs in the vault only when the vault-scope ADR accepts it.

Open decision: D6 decides whether ux-adjacent notes need a separate `ux/` folder or should remain under `product/`.

## Axis A5 - Scale Invariants

The number of domains must not increase:

- `route.py` domain-specific branches;
- envelope schema enum values;
- skill count;
- default context size without an explicit request.

A new domain should be added by data changes: create a knowledge pack, register aliases, optionally add default knowledge to bundles, and optionally add skill affinity.

## Axis A6 - Pre-Existing Debt

D1 and D2 are implemented before this proposal moves forward:

- pipeline/backend capabilities are routable and unknown capabilities fail;
- bundle route keys are typed through `routingKeyKind`, distinguishing `repository` from `repository-class`.

Remaining risks for the second axis start at D3-D6.

## New Artifact Types

| Format | Location | Content |
| --- | --- | --- |
| Knowledge pack | `reference-packs/domains/<domain>.toml` | `kind = "knowledge"`, note pointers, concepts, scope |
| Domain registry | `reference-packs/domains/_registry.toml` | Maps ids and aliases to pack paths |
| `kind` field | Existing repo packs | `kind = "repo"` |
| `routingKeyKind` | Existing bundles | Implemented; `repository` or `repository-class` |
| `defaultKnowledge[]` | Existing bundles | Small additive default knowledge list |
| `domain_affinity` | `SKILL.md` frontmatter | Knowledge domains a skill may consume |
| `intent.domains[]` | Context envelope | Requested knowledge domains |

## Naming Note

"Domain pack" is avoided because `aimsun-psp` already uses `domains/` for pipeline-stage folders. The proposed artifact is called a knowledge pack.

## Related

- `docs/architecture/typed-packs-open-decisions.md`
- `docs/architecture/typed-packs-review-backlog.md`
