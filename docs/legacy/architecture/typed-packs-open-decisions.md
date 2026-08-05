# Typed Packs And Knowledge Axis Decision Register

Status: implementation-condition register. Date: 2026-07-14. Owner: `modeller-agents`.

This register tracks the typed-packs knowledge-axis decisions referenced by the README. It records
what is implemented in `modeller-agents` and what remains blocked by `modelling-knowledge`
governance gates. It does not reactivate vault domain routability by itself.

## Current State

- D1 and D2 are implemented in the router and capability map.
- D3, D4, and D5 were accepted with implementation conditions by the 2026-07-12 independent board.
- D6 was accepted by the same board.
- The `modeller-agents` implementation conditions are satisfied for routing, validation, and budgeted
  selection.
- Vault domains remain disabled: `modelling-knowledge` keeps `product`, `accessibility`, and
  `transport` at `status: draft` / `routable: false`.
- Domain reactivation still requires vault-side governance closure: N-2 general acceptance, DR-1
  attribution, and decision `0010` general-scope acceptance, followed by regenerated exports and
  route verification.

## D1 - Capability Map Completeness

Question: should pipeline/backend skills be added to the route capability map separately from the
knowledge-axis work?

Status: accepted and implemented.

Implementation:

- `src/modeller/capabilities.py` owns canonical capability-to-skill mapping.
- `route` and `plan` use that map rather than silently falling back to `workflow`.
- Unknown capabilities fail deterministically.
- Pipeline/backend capabilities such as `pipeline-smoke`, `pipeline-review`, `pipeline-fix`,
  `backend-scaffold`, and `backend-align` are routable.

## D2 - Bundle Routing Key Kind

Question: should a bundle key be a repository identity or a reusable class/category label?

Status: accepted and implemented.

Implementation:

- Bundles declare `routingKeyKind`.
- Valid values are `repository` and `repository-class`.
- `doctor` and `route` reject missing or invalid values.
- Route output carries `routing_key_kind` for audit.

## D3 - Domain Combination Semantics

Question: when a request supplies `intent.domains[]` and a bundle supplies `defaultKnowledge[]`, do
they combine or does the request override the default?

Status: accepted with condition; condition satisfied in `modeller-agents`.

Ruling:

- Use ordered union.
- Preserve provenance for every selected domain: `request` or `bundle-default`.
- Do not silently expand beyond explicit request or capped bundle defaults.

Implementation:

- `src/modeller/knowledge_packs.py` enforces the context budget:
  `max_knowledge_packs = 3`, `max_required_notes = 8`,
  `max_optional_notes_loaded = 4`, `max_full_notes = 2`.
- Bundle `defaultKnowledge[]` is capped at 2.
- Route output exposes `knowledge_domains[]` with source provenance.

## D4 - Domain Affinity Modes

Question: can broad skills use wildcard domain affinity?

Status: accepted with condition; condition satisfied in `modeller-agents`.

Ruling:

- Wildcards are prohibited: no `*`, `all`, or `any`.
- Skills use `domain_affinity.mode`: `none`, `explicit`, or `routed`.
- `routed` consumes only domains already selected by the router; it does not infer or expand.

Implementation:

- Skill front matter validation rejects wildcard-like domain affinity.
- Route selection remains bounded by the same knowledge budget.
- `explicit` permits only listed domains; `routed` permits only already-routed domains.

## D5 - Knowledge Pack Currency And Authority

Question: should knowledge packs be generated, hand-authored, or hybrid?

Status: accepted with condition; condition satisfied in `modeller-agents`, with vault routability
still disabled.

Ruling:

- Use a hybrid model: vault export candidate -> human-reviewed pack -> recurring automated parity
  validation.
- Packs carry note IDs, purpose, digest pins, and authority context; they do not copy note bodies.

Implementation:

- `doctor` and route-time validation load current `vault_doctor export-index` and `export-domains`
  outputs when domain packs exist.
- Validation compares `source_domain_notes_digest` and `source_domains_digest`.
- Validation rejects absent notes, superseded/deprecated/historical note references, and active packs
  without current exports.
- The pilot pack `reference-packs/domains/accessibility.toml` remains inert while the vault exports
  non-routable domains.

## D6 - Product Versus UX Split

Question: should a new `ux/` folder be introduced now?

Status: accepted.

Ruling:

- No `ux/` split now.
- UX-adjacent knowledge remains under `domains/product/` unless accepted future evidence satisfies
  the domain-scope conditions in `modelling-knowledge` decision `0005`.

## Enforcement State

- N-1 shared eligibility conformance is structurally satisfied for the VA5 pilot, but live routing is
  intentionally disabled by the vault's non-routable domain export.
- N-2 authority-context completeness/currency is implemented for pack loading and memory-runtime
  classification inputs, but not yet accepted at general governance scope by `modelling-knowledge`.
- N-3 import isolation is enforced in `modeller-memory` by `tests/test_import_guards.py`.

## Cross-Repo Pointers

- Vault historical alignment plan:
  `modelling-knowledge/docs/plan/historical/vault-alignment-plan.md`
- Cross-repo coordination record:
  `modelling-knowledge/decisions/0010-typed-packs-cross-repo-coordination.md`
- Current machine-readable status:
  `modelling-knowledge/docs/dev/ecosystem-status.json`
