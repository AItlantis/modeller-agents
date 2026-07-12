# Typed Packs & Knowledge Axis - Open Decisions

Status: implementation-condition register. Date: 2026-07-12. Owner: modeller-agents.

This register tracks decisions for the typed-packs knowledge-axis proposal. D1 and D2 were pre-existing single-axis routing debts and are now implemented. D3-D6 were ruled by the independent 2026-07-12 board; D3/D4/D5 carried implementation conditions, and D6 was accepted. See that document for axis definitions and `typed-packs-review-backlog.md` for antagonist findings that should be promoted into this register.

## D1 - Fix `CAPABILITY_SKILLS` First

- **Axis:** A6 (pre-existing debt)
- **Question:** Should the five pipeline skills missing from `CAPABILITY_SKILLS` in `src/modeller/route.py` (`pipeline-smoke`, `pipeline-review`, `pipeline-fix`, `backend-scaffold`, `backend-align`) be added now, as a standalone fix, separately from any domain-axis work?
- **Fable recommendation:** Yes. Do it first, decoupled from the knowledge-axis proposal, since it is an existing routing gap independent of any new axis.
- **Status:** ACCEPTED and implemented
- **Notes:** Implemented in `src/modeller/route.py`: the five pipeline/backend skills are now routable by `requested_capability`, and unknown capabilities fail instead of silently falling back to `workflow`. Coverage lives in `tests/test_reference_packs.py`.

## D2 - Resolve the `pipeline-backend` Bundle Key

- **Axis:** A6 (pre-existing debt)
- **Question:** Is `pipeline-backend` meant to be a real repository identity that `route_envelope` resolves `target_repository` against, or a repository-class/category label?
- **Fable recommendation:** Rename the bundle key to a real repository identity, or explicitly define what the routing key is allowed to mean. Either resolution is acceptable, but silent ambiguity is not.
- **Status:** ACCEPTED and implemented
- **Notes:** Bundles now carry `routingKeyKind`, with allowed values `repository` and `repository-class`. `pipeline-backend.bundle.json` declares `repository-class`; repository-owned bundles declare `repository`. `doctor` and `route` reject missing or invalid values, and route output carries `routing_key_kind` for audit.

## D3 - `intent.domains[]` Cardinality And Combination Semantics

- **Axis:** A1 (routing)
- **Question:** When a bundle declares `defaultKnowledge[]` and a request also carries `intent.domains[]`, do the two combine (union) or does the request override the bundle default?
- **Fable recommendation:** Union, no override. A request's `domains[]` should add to, never replace, a bundle's default knowledge packs.
- **Status:** ACCEPT-WITH-CONDITION (independent antagonist board, 2026-07-12)
- **Ruling:** Adopt **ordered union with explicit provenance** (the vault-side form from `modelling-knowledge/docs/dev/vault-alignment-plan.md`, stronger than the bare union): `effective domains = explicit request domains + bundle defaults not already present`, each tagged `source: request | bundle-default | inferred`.
- **Conditions (must hold before union semantics ship — gate at VA7/VA8):** (1) the context-budget contract (`max_knowledge_packs`, `max_required_notes`, …) is implemented and enforced, not merely described (addresses VA-08/VA-10 hidden-context-expansion); (2) route decisions expose per-domain `source` so audit can distinguish asked-for from silently-added; (3) bundle defaults are size-capped by an enforced validator (A5 "≤2 default knowledge packs").
- **Notes:** Direction settled (union, not override); not an unconditional closure. Mirrors `modelling-knowledge` decision 0010 and the alignment plan's VA8 gate.
- **Implementation status (2026-07-12): CONDITION SATISFIED in `modeller-agents` at medium effort.** `src/modeller/knowledge_packs.py` defines and enforces the context-budget contract (`max_knowledge_packs = 3`, `max_required_notes = 8`, `max_optional_notes_loaded = 4`, `max_full_notes = 2`), `route_envelope` emits `knowledge_domains[]` with `source: request | bundle-default`, and `doctor`/route validation reject `defaultKnowledge[]` over the enforced cap of 2.

## D4 - Wildcard `["*"]` Domain Affinity On Broad Skills

- **Axis:** A3 (skill/method)
- **Question:** Is `domain_affinity = ["*"]` acceptable on broad skills like `workflow` or `review`, or must every domain a skill can consume be listed individually for auditability?
- **Fable recommendation:** Open question. There is a real tension between skill-authoring convenience and auditability.
- **Status:** ACCEPT-WITH-CONDITION (independent antagonist board, 2026-07-12)
- **Ruling:** Prohibit `*` / `all` / `any`. Use the three-mode taxonomy `domain_affinity: none | explicit | routed` (vault-side recommendation), where `routed` = the skill consumes only packs already selected and authorized by routing.
- **Conditions (before any skill may declare `mode: routed`):** a bounded, documented selection policy must exist — max packs per request, precedence when multiple domains apply, and an explicit rule that `routed` never expands beyond what an explicit request or a capped default already authorized. Without it, `routed` silently reintroduces wildcard-equivalent breadth (VA-08/VA-11); until the policy exists, treat `routed` as equivalent to `explicit` (i.e. not implemented).
- **Notes:** Direction settled (no wildcard); `routed` is the correct shape but is gated on the selection-policy condition. Mirrors decision 0010.
- **Implementation status (2026-07-12): CONDITION SATISFIED in `modeller-agents` at medium effort.** Skill `domain_affinity` validation accepts only `none`, `explicit`, or `routed`, rejects `*`/`all`/`any`, and selected knowledge remains bounded by the same route selection budget. `explicit` allows only listed domains; `routed` performs no expansion and consumes only domains already selected by explicit request or capped bundle defaults.

## D5 - Knowledge Pack Generation: Generated Vs Hand-Authored

- **Axis:** A2 (pack typing)
- **Question:** Should knowledge packs under `reference-packs/domains/<domain>.toml` be generated from `modelling-knowledge`'s `_index.md` summaries, or hand-authored as TOML directly?
- **Fable recommendation:** Generate from `_index.md` summaries, so the pack's `[[notes]]` pointers stay synchronized with the source-of-truth index.
- **Status:** ACCEPT-WITH-CONDITION (independent antagonist board, 2026-07-12)
- **Ruling:** Adopt the **hybrid** model (vault-side, stronger than Fable's plain generation): vault-generated candidate (from the structured `vault-index.json`, not prose `_index.md`) → human-reviewed active pack (author picks required/optional notes, purpose, ordering) → mandatory automated parity validation against the current vault index (`source_vault_commit`, `source_index_digest`).
- **Conditions (before any pack is marked `active`):** (1) parity validation must be recurring/triggered (on vault-commit change, on pack load, or scheduled) — not point-in-time only (VA-04); (2) `vault-index.json` / `vault_doctor export-index` must exist as a deterministic, versioned artifact first (VA3) — the ruling is correct but non-executable until then; (3) pack lifecycle must be linked to note supersession so a superseded note invalidates dependent packs (VA-14).
- **Notes:** Direction settled (hybrid over plain-generate); implementation is gated on the vault index export existing. Mirrors decision 0010.
- **Implementation status (2026-07-12): CONDITION SATISFIED in `modeller-agents` at medium effort.** `doctor` and route-time validation both load current `vault_doctor export-index` / `export-domains` outputs when domain packs exist, compare `source_index_digest` / `source_domains_digest`, reject active packs without current exports, reject note IDs absent from the vault index, and invalidate superseded/deprecated/historical note references. The first active pilot is `reference-packs/domains/accessibility.toml`, containing note IDs and routing purposes only.

## D6 - `product` Vs `ux` Subfolder Split

- **Axis:** A4 (knowledge-vault scope)
- **Question:** Should a new `ux/` subfolder be introduced under the relevant knowledge area now, or should ux-adjacent notes continue to live under `product/` until they demonstrably do not fit there?
- **Fable recommendation:** No `ux/` split yet. Keep ux-adjacent notes under `product/` until accepted notes stop fitting there.
- **Status:** ACCEPTED (independent antagonist board, 2026-07-12)
- **Ruling:** No `ux/` split now; ux-adjacent notes stay under `domains/product/`. Re-evaluate only against decision 0005's five concrete conditions (a real cross-product UX-method cluster of accepted notes that genuinely does not fit `product/`, applies to more than one product, forms a coherent cluster, has an accepted vault-scope decision, and an explicit product-vs-UX-method boundary).
- **Notes:** Clean accept — the conservative/reversible choice, backed by accepted decision 0005 (the domain's owning authority). No condition on D6 itself; 0005's own status is being confirmed under the same board pass. Mirrors decision 0010.

## Blocking Order

D1 and D2 are resolved in the current single-axis router. **D3–D6 were ruled on by an independent antagonist board on 2026-07-12** (D3/D4/D5 ACCEPT-WITH-CONDITION, D6 ACCEPTED); the direction of each is now settled, so none remain OPEN. Their **conditions** (D3 context-budget enforcement + per-domain provenance; D4 bounded selection policy before `routed`; D5 recurring parity + the vault index export existing + supersession-linked invalidation) are the gates that must be met before the domain axis is *implemented* — they block implementation, not the ruling. These conditions map to Phase VA7/VA8 of `modelling-knowledge/docs/dev/vault-alignment-plan.md` and to the cross-repo tracker `modelling-knowledge/decisions/0010-typed-packs-cross-repo-coordination.md`.

This ruling removes the forcing-function the vault flagged (its domains were rolled back to non-routable pending exactly this acceptance); re-activating vault domain routability is now legitimate once these conditions and the vault-side board confirmation are in place.

2026-07-12 implementation update: those gates are now satisfied for the VA5 accessibility pilot. Vault routability can be active for the already scoped domains while `modelling-knowledge` remains the authority for note IDs, metadata, sensitivity, and eligibility.

## Enforcement Needs N-1/N-2/N-3

Status as of 2026-07-12:

- **N-1 shared eligibility conformance test:** MET for VA5. `tests/test_reference_packs.py::test_live_accessibility_pack_conforms_to_vault_export` validates the active pilot against the live vault export, and `test_live_route_selects_accessibility_pack_with_provenance` proves the route consumes it with explicit provenance.
- **N-2 `authority_context` completeness/currency validator:** MET for VA5 pack consumption. Active knowledge packs must carry an `authority_context` table naming the vault, registry, scope decision, knowledge-seam decision, coordination decision, and check date; digest parity supplies current-export currency.
- **N-3 CI import-guard for `vault_doctor`:** MET in `modeller-memory` via `tests/test_import_guards.py`, which fails if runtime modules outside `tools/vault_doctor/` import vault-doctor internals.
