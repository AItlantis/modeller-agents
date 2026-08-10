# Modeller Memory, Candidate-Classification Seam: Product Requirements Document

**Nature:** initial product specification, translating the classification seam's business-need and design brief into testable, live obligations for this repository
**Status:** Draft, to be validated by the maintainers of modeller-memory, modeller-agents, and modelling-knowledge
**Version:** 0.1, 25 July 2026
**Upstream documents:** docs/vision/Business-need-design-brief.md
**Consistency matrix:** None exists for this doc set

---

## 1. Purpose and scope

This document translates the Modeller Memory Business Need and Design Brief into testable requirements for the classification seam that is built and tested today, and for the smaller companion-recall scaffold alongside it. It forms a basis for design, architecture, delivery breakdown, and the suggested pilot named in the brief (one bounded task, one candidate, one round trip through human review).

It does not replace:

- the business-need / design brief, which explains the why and the journeys;
- the detailed architecture decisions, including the ADRs governing the vault boundary and skill ownership;
- the interface specifications, including `docs/contracts/` and `schemas/`;
- the API contracts exposed to modeller-agents and modelling-knowledge;
- the technical test plans under `tests/`;
- the ecosystem architecture record, `modelling-ecosystem/.docs/architecture.md`, which is authoritative on this repository's current status.

This document obligates only what the brief scoped as MVP: the classification seam and the companion-recall scaffold. It does not obligate repository intelligence, the modeller-agents transport step, or standing companion recall. Those remain named, tracked dependencies this repository's own requirements point to, not scope this document invents or assumes closed.

---

## 2. Traceability to upstream documents

| Upstream document | Relevant sections | What this PRD obligates |
|---|---|---|
| `Business-need-design-brief.md` | §1, §2, §3, §4 | Turns the product promise, the four named risks, the product boundaries, and the user/responsibility matrix into BR, INT, and HITL requirements |
| `Business-need-design-brief.md` | §5.1, §5.2, §5.4, §6, §9 | Turns the two built journeys (classification, companion-recall) and the maintainer journey into FR, DATA, and SEC requirements |
| `Business-need-design-brief.md` | §5.3, §7, §8, §10 | Records the transport step and inbox-review journey as a named, not-yet-reachable dependency; requirements referencing it carry Target maturity |
| `Business-need-design-brief.md` | §11, §13, §14 | Sources the cross-cutting MVP capability list and the success-measure framing behind OBS and NFR requirements |
| `Business-need-design-brief.md` | §12, §17 | Sources the parking-lot exclusions (§18 below) and the blocking open decisions (§19 below) |

Every requirement below carries a **Source** field pointing back to one of these sections.

---

## 3. Normative language

This document uses RFC 2119-style keywords. Each requirement statement uses **exactly one** keyword class to express its obligation:

- **MUST**: obligation required for acceptance of the scope concerned.
- **MUST NOT**: explicitly forbidden behavior.
- **SHOULD**: important requirement; deviation allowed only by documented decision.
- **MAY**: optional or progressive capability.

### Priority

| Priority | Interpretation |
|---|---|
| **P0** | Required for the built classification journey (brief §5.1) or for the vault-boundary guarantee |
| **P1** | Important for a complete MVP or for the suggested pilot (brief §8) |
| **P2** | Improvement that can be deferred |

### Status-ladder discipline

This document uses the ecosystem's full status-ladder word set only: Current, Operational, Emerging, Target, Proposed, Deferred, Legacy. A requirement against a capability that is not Operational names the blocking dependency in its own Statement or Rationale, not in a footnote.

- **CURRENT**: the requirement targets a capability that exists in the codebase today, tested, but not yet proven in a live modeller-agents workflow.
- **OPERATIONAL**: the requirement targets a capability already proven in real use; not used anywhere in this document, since no live workflow exercise has yet occurred (brief §17 OPN-002).
- **EMERGING**: the requirement targets a capability under active but incomplete construction; the requirement text names the gap that keeps it from being Current.
- **TARGET**: the requirement targets a capability planned but not yet started, most often because it depends on a not-yet-built modeller-agents transport step; the requirement text says so explicitly.
- **PROPOSED**: the requirement targets a capability that is only a candidate direction, not yet committed (e.g. repository intelligence); treated with the same caution as an open decision (§19).

No requirement in this document claims Operational status. The classification seam and the import-guard boundary are Current, tested but not yet proven live; the companion-recall scaffold is Current, non-persistent by design; everything depending on the modeller-agents transport step is Target; repository intelligence is Proposed.

---

## 4. Definitions and actors

| Term | Definition |
|---|---|
| Observation | The structured input an orchestrator submits to `classify()`; not itself typed knowledge until classified. |
| Authority context | The accepted-knowledge references, source commit, and applicable decisions an observation is judged against; supplied by the orchestrator, never read independently by modeller-memory. |
| `MemoryCandidate` | The typed output of `classify()`, carrying a target, classification, confidence, provenance, and sensitivity. |
| Candidate event ledger | The append-only, digest-chained record of every classification transition; evidence, not a store of accepted fact. |
| `MemoryScope` | The explicit session, project, tenant, repository, or run boundary a companion-recall write or read must specify; there is no unscoped default. |
| Target | The routing recommendation on a `MemoryCandidate` (`vault-inbox`, `companion`, `discard`, or `flag`), never itself a write. |

| Actor | Description |
|---|---|
| Orchestrator | An in-flight agent inside modeller-agents, acting on behalf of a transport modeller; submits observations and authority context, holds the returned candidate. |
| Inbox reviewer / antagonist board | modelling-knowledge's human decision-makers; interact with modeller-memory's output only, once modeller-agents' transport step delivers it, never with modeller-memory directly. |
| modeller-memory maintainer | Extends `classify()`, the policy checks, and the event ledger; keeps the vault boundary and skill-ownership boundary intact. |
| modeller-agents / modelling-knowledge maintainer | Consumes this repository's contracts; owns the transport step and the inbox contract respectively. |

---

## 5. Requirement entry format

Every requirement in every family below follows this skeleton:

### {{ID}} - {{Title}}

**Statement:** {{System}} {{MUST | MUST NOT | SHOULD | MAY}} {{testable obligation}}.
**Rationale:** {{why this exists; link back to a risk or a cost of the status quo}}
**Source:** {{Business Need §N; or "Open question OQ-00N" if not yet decided}}
**Priority:** {{P0 | P1 | P2}}
**Dependencies:** {{other requirement IDs, or "None"}}
**Maturity:** {{Current | Operational | Emerging | Target | Proposed}} {{if not Operational, name the blocking dependency}}

**Acceptance criteria:**
- {{observable, testable condition 1}}
- {{observable, testable condition 2}}
- {{observable, testable condition 3}}

**Validation method:** {{how this will be tested}}
**Related risks:** {{risk IDs, if a risk register exists upstream}}
**Related architecture:** {{architecture component IDs, if applicable}}
**Related plan items:** {{delivery batch IDs, if applicable}}
**Status:** Draft, to be validated

---

## 6. Business requirements (BR)

Product-level obligations that follow directly from the business need: what modeller-memory must be organised around, what it must never do to modelling-knowledge's or the human reviewer's authority, and what continuity it must preserve as a connecting layer rather than a second source of truth.

### BR-001 - Non-authoritative connecting layer

**Statement:** modeller-memory MUST propose a classification and MUST NOT decide, approve, or silently promote a candidate to accepted knowledge.
**Rationale:** the core product promise is a typed candidate a human reviews, never a silent second version of accepted knowledge; this is the fundamental problem the brief names.
**Source:** Business-need-design-brief.md §1, §2.2 (risk 1), §3.
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current. `classify()` returns a typed proposal and stops; no code path in the repository writes an acceptance decision.

**Acceptance criteria:**
- No function in `src/modeller_memory/` sets a candidate's status to accepted or rejected.
- Every `MemoryCandidate` returned by `classify()` is documented and typed as a proposal, never as a decision.
- A maintainer review of `src/modeller_memory/candidate/` and `src/modeller_memory/policy/` finds no vault-write or acceptance-decision code path.

**Validation method:** Static source review plus `tests/candidate/test_classify.py`.
**Related risks:** Silent promotion (brief §2.2, risk 1).
**Related architecture:** `src/modeller_memory/candidate/classify.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### BR-002 - Vault boundary confinement

**Statement:** no module under `src/modeller_memory/` other than `src/modeller_memory/tools/vault_doctor/` MUST read or write the modelling-knowledge vault in any way.
**Rationale:** keeping the write path from observation to vault visibly separate from modelling-knowledge's own governed inbox is the mechanism that prevents silent promotion; `vault_doctor` is an orthogonal, explicitly separate, read-only tool.
**Source:** Business-need-design-brief.md §2.2 (risk 1), §3, §9.3; ADR-0005.
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current, machine-enforced today.

**Acceptance criteria:**
- `tests/test_import_guards.py` fails the build if any module outside `src/modeller_memory/tools/vault_doctor/` imports `vault_doctor`.
- `vault_doctor` reads vault files read-only via an explicit `--vault-path` CLI argument; it performs no write, move, or delete.
- No runtime path in `src/modeller_memory/candidate/`, `src/modeller_memory/policy/`, or `src/modeller_memory/companion/` references a vault path.

**Validation method:** `tests/test_import_guards.py`; static grep for vault-path references outside `tools/vault_doctor/`.
**Related risks:** Silent promotion (brief §2.2, risk 1).
**Related architecture:** `src/modeller_memory/tools/vault_doctor/`; ADR-0005.
**Related plan items:** None.
**Status:** Draft, to be validated

### BR-003 - Classification traceability as a first-class property

**Statement:** modeller-memory MUST keep every `MemoryCandidate` linked to the observation and authority context that produced it, and to the ledger event that recorded its classification transition.
**Rationale:** the brief's evidence requirement: a candidate must remain re-readable, and its dependence on a complete or stale authority context must remain identifiable after the fact.
**Source:** Business-need-design-brief.md §7, §10.
**Priority:** P0.
**Dependencies:** BR-001.
**Maturity:** Current.

**Acceptance criteria:**
- Every `MemoryCandidate` carries a reference to its source observation and authority context via `authority_context_refs` and `provenance`.
- Every classification transition produces exactly one ledger event.
- A maintainer or orchestrator can re-read a candidate and its ledger event after the fact using only artifacts produced by `classify()`.

**Validation method:** `tests/candidate/test_classify.py`, `tests/candidate/test_ledger.py`.
**Related risks:** None beyond BR-001's silent-promotion risk.
**Related architecture:** `src/modeller_memory/candidate/model.py`, `src/modeller_memory/candidate/ledger.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 7. Functional requirements (FR)

User-facing (orchestrator-facing) capabilities mapped to the two built journeys in the brief: the classification call (§5.1) and the companion-recall scaffold (§5.2).

### FR-001 - Structured observation and authority-context submission

**Statement:** modeller-memory MUST accept a structured observation together with an orchestrator-supplied authority context as the sole input to `classify()`.
**Rationale:** direct re-key of the brief's built journey, steps 1 through 3; `classify()` uses only what is explicitly supplied, never reading the vault or the host repository's structure independently.
**Source:** Business-need-design-brief.md §5.1 (steps 1-3), §9.1.
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current.

**Acceptance criteria:**
- `classify()` accepts exactly one `MemoryCandidate` and one `AuthorityContext` per call.
- No call path allows `classify()` to read the vault or repository structure to supplement a missing input.
- A call with a well-formed observation and authority context returns without error.

**Validation method:** `tests/candidate/test_classify.py`.
**Related risks:** None additional.
**Related architecture:** `src/modeller_memory/candidate/classify.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-002 - Typed `MemoryCandidate` output

**Statement:** `classify()` MUST return a typed `MemoryCandidate` carrying a target, classification, confidence, provenance, and sensitivity marking.
**Rationale:** direct re-key of the brief's product promise: a working observation becomes a typed, evidenced candidate a human can review.
**Source:** Business-need-design-brief.md §1, §5.1 (step 6), §7.
**Priority:** P0.
**Dependencies:** FR-001.
**Maturity:** Current.

**Acceptance criteria:**
- Every successful `classify()` call returns a `MemoryCandidate` with `target`, `classification`, `confidence`, `provenance`, and `sensitivity` populated.
- The schema is versioned under `schemas/memory-candidate.schema.json` so a downstream consumer can rely on it without reading this repository's internals.
- A hand-checked sample of candidates shows correct target routing for both an ordinary and a stale-context case, matching the MVP success bar stated in the brief.

**Validation method:** `tests/candidate/test_classify.py`; a hand-checked sample per the brief's stated success bar, to be run against the suggested pilot (brief §8).
**Related risks:** None additional.
**Related architecture:** `src/modeller_memory/candidate/model.py`; `schemas/memory-candidate.schema.json`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-003 - Scoped companion-recall write and read-back

**Statement:** modeller-memory MUST let an orchestrator write a generated piece of context into the companion provider and read it back within the same explicit `MemoryScope`.
**Rationale:** direct re-key of the brief's companion-recall journey; supports session- or project-local write-and-read-back without claiming standing recall.
**Source:** Business-need-design-brief.md §5.2, §7.
**Priority:** P1.
**Dependencies:** None.
**Maturity:** Current, explicitly non-persistent; nothing written survives beyond the process (brief §5.2, step 4).

**Acceptance criteria:**
- A `CompanionRecord` written via `InMemoryMemoryProvider.put()` with an explicit `MemoryScope` can be read back via `get()` using a scope that contains it.
- Nothing written through the companion provider persists beyond the process.
- The interface does not represent a companion-recall write as durable to the orchestrator.

**Validation method:** `tests/companion/test_provider.py`.
**Related risks:** Scope leakage (brief §2.2, risk 4), addressed by FR-004.
**Related architecture:** `src/modeller_memory/companion/provider.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-004 - No unscoped companion-recall retrieval

**Statement:** the companion provider MUST NOT return a result for a blank or unscoped `MemoryScope`.
**Rationale:** direct re-key of the brief's scope-leakage risk: a companion store built or operated carelessly could surface one project's or one client's context inside another's session.
**Source:** Business-need-design-brief.md §2.2 (risk 4), §3, §5.2 (step 3).
**Priority:** P0.
**Dependencies:** FR-003.
**Maturity:** Current.

**Acceptance criteria:**
- A `search()` or `get()` call with a `MemoryScope` whose `is_explicit` is false returns nothing, never a default or fallback result.
- No code path in `src/modeller_memory/companion/` infers a scope when one is not explicitly supplied.

**Validation method:** `tests/companion/test_provider.py`.
**Related risks:** Scope leakage (brief §2.2, risk 4).
**Related architecture:** `src/modeller_memory/companion/provider.py`; ADR-0003.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 8. Integration requirements (INT)

How modeller-memory's classification seam integrates with the orchestrator inside modeller-agents, how the not-yet-built transport step will eventually connect it to modelling-knowledge's inbox, and how conflict-relevant context flows in without modeller-memory reading the vault itself.

### INT-001 - `classify()` as the sole runtime touchpoint

**Statement:** modeller-memory MUST expose `classify(candidate, authority_context)` as its only callable classification entry point for an orchestrator integration.
**Rationale:** the brief states plainly there is no workflow to build inside modeller-memory itself; sequencing and retry logic belong to the orchestrator, not this repository.
**Source:** Business-need-design-brief.md §6.2, §6.3.
**Priority:** P0.
**Dependencies:** FR-001, FR-002.
**Maturity:** Current; the only proven runtime touchpoint between modeller-memory and modeller-agents today.

**Acceptance criteria:**
- `classify()` is the only public entry point an external orchestrator calls to obtain a `MemoryCandidate`.
- `classify_with_ledger()` is documented as an optional helper for callers that also want ledger evidence, not a second classification path with different semantics.
- No sequencing, retry, or workflow-orchestration logic exists inside `src/modeller_memory/`.

**Validation method:** API surface review against `docs/contracts/candidate-contract.md`.
**Related risks:** None additional.
**Related architecture:** `src/modeller_memory/candidate/classify.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### INT-002 - Candidate transport into modelling-knowledge's inbox

**Statement:** once modeller-agents builds its transport step, that step MUST perform the actual inbox write for a candidate recommending `target: vault-inbox`; modeller-memory itself MUST NOT perform this write.
**Rationale:** ADR-0004's propose/transport/govern split; modeller-memory returns a typed candidate and stops, the write belongs solely to a modeller-agents-owned agent not yet built.
**Source:** Business-need-design-brief.md §3, §5.3, §6.7; ADR-0004.
**Priority:** P0.
**Dependencies:** FR-002.
**Maturity:** Target; blocked on modeller-agents building the transport step (brief §17 OPN-001), which per the integration plan does not yet exist in modeller-agents.

**Acceptance criteria:**
- No module in this repository writes to modelling-knowledge's inbox.
- Once built, the modeller-agents transport step's inbox write carries the candidate's full authority context and provenance.
- The gap between a classified candidate and a delivered inbox draft is visibly marked wherever this journey is documented, not silently assumed closed.

**Validation method:** Not testable from this repository alone until the transport step exists; validated jointly with modeller-agents once built.
**Related risks:** Ownership collision (brief §2.2, risk 3), if the transport step's boundary with `classify()` is not kept clear.
**Related architecture:** ADR-0004; modeller-agents' (not-yet-built) transport agent.
**Related plan items:** Blocked on OPN-001.
**Status:** Draft, to be validated

### INT-003 - No memory-owned executable skill

**Statement:** modeller-memory MUST NOT author or ship an executable skill (e.g. `memory-recon`, `memory-maintain`); it MAY provide non-executable `*.reference.md` examples only.
**Rationale:** direct re-key of the brief's ownership-collision risk and ADR-0002: skill ownership belongs solely to modeller-agents.
**Source:** Business-need-design-brief.md §2.2 (risk 3), §3, §9.3; ADR-0002.
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current.

**Acceptance criteria:**
- No executable skill file exists in this repository's skill-facing directories.
- Any `*.reference.md` present is explicitly non-executable and documented as an example only.

**Validation method:** Repository structure review against ADR-0002.
**Related risks:** Ownership collision (brief §2.2, risk 3).
**Related architecture:** ADR-0002.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 9. Data requirements (DATA)

Identity and provenance for the classification seam's core objects: the observation, the authority context, the candidate, and the ledger event.

### DATA-001 - `MemoryCandidate` as a typed, versioned schema

**Statement:** modeller-memory MUST define `MemoryCandidate` as a typed, versioned schema that a downstream consumer can rely on without reading this repository's internals.
**Rationale:** direct re-key of the brief's cross-cutting MVP capability list: a typed, versioned schema is required so modeller-agents and, eventually, modelling-knowledge can build against a stable contract.
**Source:** Business-need-design-brief.md §7, §11.
**Priority:** P0.
**Dependencies:** FR-002.
**Maturity:** Current.

**Acceptance criteria:**
- `MemoryCandidate`'s schema is published under `schemas/memory-candidate.schema.json` and described in `docs/contracts/candidate-contract.md`, each with an explicit version.
- A schema change is reflected in the version identifier.
- Target, classification, confidence, provenance, and sensitivity fields are all present and typed.

**Validation method:** Schema validation test; contract review.
**Related risks:** None additional.
**Related architecture:** `src/modeller_memory/candidate/model.py`; `schemas/memory-candidate.schema.json`; `docs/contracts/candidate-contract.md`.
**Related plan items:** None.
**Status:** Draft, to be validated

### DATA-002 - Append-only, digest-chained candidate event ledger

**Statement:** the candidate event ledger MUST record every classification transition as an append-only, digest-chained event, performing no vault or file I/O of its own.
**Rationale:** direct re-key of the brief's core evidence mechanism: what was classified, when, and against what authority context stays evidenced without becoming a second store of accepted fact.
**Source:** Business-need-design-brief.md §3, §6.4, §7, §11.
**Priority:** P0.
**Dependencies:** BR-003.
**Maturity:** Current.

**Acceptance criteria:**
- Every classification transition produces exactly one `CandidateLedgerEvent`.
- `CandidateEventLedger.append()` rejects an event whose `previous_digest` does not match the ledger's current `latest_digest`, so no event can be modified or removed once appended.
- Each event's digest chains to the prior event via `compute_event_digest()`, so tampering is detectable by `validate_event_chain()`.
- The ledger itself performs no read or write against the modelling-knowledge vault or any external file store; persistence, where wanted, is the caller's own responsibility via `event_to_json_line()`.

**Validation method:** `tests/candidate/test_ledger.py`.
**Related risks:** Silent promotion (brief §2.2, risk 1), if the ledger were ever mistaken for an accepted-fact store.
**Related architecture:** `src/modeller_memory/candidate/ledger.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### DATA-003 - Authority context as orchestrator-supplied, never independently sourced

**Statement:** modeller-memory MUST treat the authority context (accepted-knowledge references, source commit, applicable decisions) as supplied entirely by the orchestrator, and MUST NOT read modelling-knowledge or the host repository independently to construct or supplement it.
**Rationale:** direct re-key of the brief's context boundary: `classify()` uses only what is explicitly supplied; repository intelligence that could supplement this is unbuilt.
**Source:** Business-need-design-brief.md §6.1, §9.1.
**Priority:** P0.
**Dependencies:** FR-001.
**Maturity:** Current.

**Acceptance criteria:**
- No code path in `src/modeller_memory/` queries modelling-knowledge or a host repository to fill in a missing `AuthorityContext` field.
- The `AuthorityContext` passed into a `classify()` call is fully attributable to what the orchestrator supplied in that call.

**Validation method:** Static source review; `tests/candidate/test_classify.py`.
**Related risks:** Stale-context conflict resolution (brief §2.2, risk 2), addressed jointly with SEC-001.
**Related architecture:** `src/modeller_memory/policy/authority.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 10. Security requirements (SEC)

Access scope and boundary enforcement for the classification seam and the vault-doctor tool, scoped to the MVP's programmatic, no-UI surface.

### SEC-001 - Authority-context validation before conflict resolution

**Statement:** `classify()` MUST run the authority-context validator (completeness, vault pinning to modelling-knowledge, receipt checks, digest currency) before resolving any classification decision.
**Rationale:** direct re-key of the brief's stale-context conflict risk; the N-2 validator exists precisely so a conflict decision is never made against context nothing has confirmed is current.
**Source:** Business-need-design-brief.md §2.2 (risk 2), §3, §5.1 (step 4).
**Priority:** P0.
**Dependencies:** DATA-003.
**Maturity:** Current, but the validator's completeness/currency guarantee is designed and unit-tested, not yet proven against a live orchestrator-supplied context in a real modeller-agents workflow, per the integration plan's cross-repo status table.

**Acceptance criteria:**
- `validate_authority_context()` runs before `classify_target()` executes, on every `classify()` call.
- Completeness, vault pinning, receipt, and digest-currency checks are all exercised on every call.
- No `classify()` call resolves a conflict decision against an authority context that has not passed this validator.

**Validation method:** `tests/policy/test_authority.py`; a live-workflow proof is deferred to the suggested pilot (brief §8, OPN-002).
**Related risks:** Stale-context conflict resolution (brief §2.2, risk 2).
**Related architecture:** `src/modeller_memory/policy/authority.py`.
**Related plan items:** Blocked on OPN-002 for live-workflow proof.
**Status:** Draft, to be validated

### SEC-002 - Forced flag on incomplete or stale context

**Statement:** `classify()` MUST force `target: flag` whenever the authority-context validator finds the supplied context incomplete or stale, and MUST NOT silently proceed to `vault-inbox` or a silent discard.
**Rationale:** direct re-key of the brief's central containment mechanism for risk 2; this is the one machine-enforced answer to a stale or incomplete authority context.
**Source:** Business-need-design-brief.md §2.3, §5.1 (step 5), §9.4, §11.
**Priority:** P0.
**Dependencies:** SEC-001.
**Maturity:** Current.

**Acceptance criteria:**
- A `classify()` call against a deliberately incomplete authority context returns `target: flag` with `classification: "authority-context-invalid"`.
- A `classify()` call against a deliberately stale authority context (failed digest-currency check) returns `target: flag` for the same reason.
- No test or production code path allows a `classify()` call with a failed validator check to return any target other than `flag`.

**Validation method:** `tests/policy/test_authority.py`, `tests/candidate/test_classify.py`, exercising deliberately incomplete and stale contexts.
**Related risks:** Stale-context conflict resolution (brief §2.2, risk 2).
**Related architecture:** `src/modeller_memory/policy/authority.py`, `src/modeller_memory/candidate/classify.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### SEC-003 - `vault_doctor` read-only, explicit-path access

**Statement:** `tools/vault_doctor/` MUST access the modelling-knowledge vault read-only, and MUST require an explicit `--vault-path` argument rather than inferring a vault location.
**Rationale:** the one sanctioned exception to the vault boundary (BR-002) must itself stay narrow: no implicit path, no write capability.
**Source:** Business-need-design-brief.md §3, §9.3; ADR-0005.
**Priority:** P0.
**Dependencies:** BR-002.
**Maturity:** Current.

**Acceptance criteria:**
- `vault_doctor`'s CLI requires `--vault-path` and fails without it, rather than defaulting to a discovered path.
- No function under `tools/vault_doctor/` calls a write, move, or delete operation against the supplied vault path.

**Validation method:** `tests/vault_doctor/test_checks.py`, `tests/vault_doctor/test_inbox.py`, `tests/vault_doctor/test_export.py`.
**Related risks:** Silent promotion (brief §2.2, risk 1), if vault_doctor's read boundary were to erode.
**Related architecture:** `src/modeller_memory/tools/vault_doctor/`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 11. Non-functional requirements (NFR)

Performance, resilience, and environment expectations for the classification seam. Where a budget is not yet known, this document says so explicitly rather than inventing a number.

### NFR-001 - No performance budget defined ahead of a live workflow

**Statement:** modeller-memory SHOULD NOT be held to a `classify()` latency or throughput budget until performance and reliability expectations are captured from a live modeller-agents workflow.
**Rationale:** the brief names this explicitly as expected input still owed from technology: performance and reliability expectations for `classify()` under a live modeller-agents workflow, once one is run.
**Source:** Business-need-design-brief.md §16.
**Priority:** P2.
**Dependencies:** None.
**Maturity:** Target; blocked on the suggested pilot (brief §8) or an equivalent live exercise producing real timing data.

**Acceptance criteria:**
- No committed latency or throughput number is published for `classify()` ahead of a live-workflow measurement.
- Once a live measurement exists, this requirement is superseded by a concrete budget requirement.

**Validation method:** Not applicable until a live workflow is run.
**Related risks:** None additional.
**Related architecture:** None.
**Related plan items:** Blocked on the suggested pilot (brief §8).
**Status:** Draft, to be validated

### NFR-002 - Import-guard boundary as a build-blocking test

**Statement:** the import-guard test MUST fail the build whenever a module outside `src/modeller_memory/tools/vault_doctor/` imports `vault_doctor`.
**Rationale:** this is the one boundary independently verifiable by a passing test today, and the mechanism that operationalises BR-002.
**Source:** Business-need-design-brief.md §3, §5.4 (step 2); ADR-0005.
**Priority:** P0.
**Dependencies:** BR-002.
**Maturity:** Current.

**Acceptance criteria:**
- `tests/test_import_guards.py` runs as part of CI and fails the build on a violation.
- A deliberately introduced violating import is caught by the test in a maintainer's local run.

**Validation method:** `tests/test_import_guards.py`.
**Related risks:** Silent promotion (brief §2.2, risk 1).
**Related architecture:** `tests/test_import_guards.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### NFR-003 - Companion-recall non-persistence by construction

**Statement:** the companion-recall provider SHOULD hold no state beyond the lifetime of the process it runs in.
**Rationale:** direct re-key of the brief's explicit design constraint: standing companion recall is deferred behind evaluation gates that have not been run, so the current scaffold must not accidentally become durable.
**Source:** Business-need-design-brief.md §5.2 (step 4), §12.
**Priority:** P1.
**Dependencies:** FR-003.
**Maturity:** Current, deliberately in-memory only; `InMemoryMemoryProvider` holds its `_records` dict as a plain instance attribute with no serialisation path.

**Acceptance criteria:**
- No companion-recall write is persisted to disk, a database, or any store surviving process restart.
- A restart of the process clears all previously written companion context.

**Validation method:** `tests/companion/test_provider.py`.
**Related risks:** Scope leakage (brief §2.2, risk 4), if persistence were added without the evaluation gates in brief §12 first passing.
**Related architecture:** `src/modeller_memory/companion/provider.py`.
**Related plan items:** Blocked on OPN-004 (companion-recall evaluation thresholds) before any persistence work begins.
**Status:** Draft, to be validated

---

## 12. Observability requirements (OBS)

What must be observable after the fact so a maintainer, and eventually an inbox reviewer, can inspect a classification transition.

### OBS-001 - Ledger event queryability by candidate

**Statement:** a maintainer or orchestrator MUST be able to retrieve the ledger event corresponding to a given `MemoryCandidate` after the fact.
**Rationale:** direct re-key of the brief's evidence requirement: re-reading a candidate and its ledger event after the fact must be possible, not just theoretically recorded.
**Source:** Business-need-design-brief.md §7, §10.
**Priority:** P0.
**Dependencies:** DATA-002.
**Maturity:** Current.

**Acceptance criteria:**
- Given a `MemoryCandidate`'s `candidate_id`, its corresponding `CandidateLedgerEvent` can be retrieved from the ledger without ambiguity.
- The retrieved event identifies the observation, authority context, classification outcome, and confidence associated with the transition, via `authority_context_refs`, `evidence_refs`, `classification`, and `target`.

**Validation method:** `tests/candidate/test_ledger.py`.
**Related risks:** None additional.
**Related architecture:** `src/modeller_memory/candidate/ledger.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### OBS-002 - Distinguishing forced-flag outcomes from ordinary classification

**Statement:** the ledger event and the returned `MemoryCandidate` MUST make it identifiable whether a classification depended on a complete and current authority context, or was forced to `flag` because it did not.
**Rationale:** direct re-key of the brief's evidence requirement: this distinction must be legible after the fact, not inferred.
**Source:** Business-need-design-brief.md §10, §14.
**Priority:** P0.
**Dependencies:** SEC-002, OBS-001.
**Maturity:** Current.

**Acceptance criteria:**
- A `MemoryCandidate` with `target: flag` and `classification: "authority-context-invalid"` is distinguishable, in its own data, from one flagged for another reason.
- The corresponding ledger event's `reason_codes` records which validator check failed.

**Validation method:** `tests/candidate/test_classify.py`, `tests/policy/test_authority.py`.
**Related risks:** Stale-context conflict resolution (brief §2.2, risk 2).
**Related architecture:** `src/modeller_memory/policy/authority.py`, `src/modeller_memory/candidate/ledger.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 13. Human-in-the-loop requirements (HITL)

Where a human must confirm, decide, or review, and where modeller-memory's own part in the cycle stops.

### HITL-001 - Human acceptance authority reserved to modelling-knowledge

**Statement:** modeller-memory MUST NOT approve, reject, or otherwise decide the fate of a candidate; that decision belongs solely to modelling-knowledge's inbox reviewers and antagonist boards.
**Rationale:** direct re-key of the brief's most fundamental boundary: nothing modeller-memory produces becomes accepted knowledge on its own authority.
**Source:** Business-need-design-brief.md §3, §9.3, §18.
**Priority:** P0.
**Dependencies:** BR-001.
**Maturity:** Current for modeller-memory's own restraint; Target for the reviewer actually being able to exercise this authority end to end, since the transport step delivering a candidate to the inbox is not yet built (brief §5.3).

**Acceptance criteria:**
- No code path in this repository sets or infers an acceptance or rejection decision.
- Documentation of `classify()`'s output describes the `target` field as a recommendation, never a decision.

**Validation method:** Static source review; `tests/candidate/test_classify.py`.
**Related risks:** Silent promotion (brief §2.2, risk 1).
**Related architecture:** `src/modeller_memory/candidate/classify.py`.
**Related plan items:** Blocked on OPN-001 (modeller-agents transport step) for the reviewer's own end of this guarantee.
**Status:** Draft, to be validated

### HITL-002 - Orchestrator visibility into supplied authority context

**Statement:** the orchestrator MUST be able to see and correct the authority context it supplies to `classify()` before an important classification call.
**Rationale:** direct re-key of the brief's context-trust boundary: `classify()` trusts the supplied context and does not independently verify it against the vault, so the orchestrator is the last checkpoint before that trust is extended.
**Source:** Business-need-design-brief.md §9.1.
**Priority:** P1.
**Dependencies:** DATA-003.
**Maturity:** Current for the contract shape (the `AuthorityContext` is a plain, orchestrator-visible dataclass, not opaque); Target for any confirmation UI, since modeller-memory has no interface of its own and any consumer surface belongs to modeller-agents.

**Acceptance criteria:**
- The `AuthorityContext` object passed to `classify()` is fully inspectable by the orchestrator before the call.
- No field of the authority context is generated or altered by modeller-memory before validation runs.

**Validation method:** API contract review; `tests/candidate/test_classify.py`.
**Related risks:** Stale-context conflict resolution (brief §2.2, risk 2).
**Related architecture:** `src/modeller_memory/policy/authority.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### HITL-003 - Inbox reviewer traceability once transport exists

**Statement:** once modeller-agents' transport step is built, an inbox reviewer MUST be able to trace a delivered candidate back to the observation, authority context, and ledger event that produced it.
**Rationale:** direct re-key of the brief's inbox-reviewer journey and evidence requirement; this is the shape the MVP is designed to complete, not something already working.
**Source:** Business-need-design-brief.md §5.3, §10.
**Priority:** P1.
**Dependencies:** OBS-001, INT-002.
**Maturity:** Target; blocked on modeller-agents building the transport step (brief §17 OPN-001). modeller-memory's own contribution, a traceable candidate and ledger event, is Current; the end-to-end reviewer journey is not reachable today.

**Acceptance criteria:**
- A candidate carrying `target: vault-inbox`, once delivered by the transport step, retains its full authority context and provenance intact.
- An inbox reviewer can locate the originating ledger event from the delivered candidate alone.

**Validation method:** Not testable from this repository alone until the transport step exists.
**Related risks:** None additional beyond OPN-001's blocking status.
**Related architecture:** `src/modeller_memory/candidate/ledger.py`; modeller-agents' (not-yet-built) transport agent.
**Related plan items:** Blocked on OPN-001.
**Status:** Draft, to be validated

---

## 14. Verification requirements (TEST)

Cross-cutting test campaigns proving the classification seam holds together as a whole, including the boundary tests that are this repository's most load-bearing guarantees.

### TEST-001 - Import-guard and vault-boundary regression coverage

**Statement:** the test suite MUST verify, on every change, that no runtime module outside `tools/vault_doctor/` imports `vault_doctor`, and that no runtime module reads or writes the modelling-knowledge vault.
**Rationale:** direct verification of BR-002 and SEC-003, the repository's single most consequential boundary guarantee.
**Source:** Business-need-design-brief.md §3, §5.4 (step 2).
**Priority:** P0.
**Dependencies:** BR-002, SEC-003.
**Maturity:** Current.

**Acceptance criteria:**
- `tests/test_import_guards.py` passes on a clean checkout and fails when a violating import is deliberately introduced.
- The vault_doctor test suite (`tests/vault_doctor/`) confirms read-only, explicit-path behaviour.

**Validation method:** `pytest tests/test_import_guards.py tests/vault_doctor/`.
**Related risks:** Silent promotion (brief §2.2, risk 1).
**Related architecture:** `tests/test_import_guards.py`, `tests/vault_doctor/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### TEST-002 - Classification and policy regression coverage

**Statement:** the test suite MUST verify that `classify()` returns a well-formed `MemoryCandidate` on a complete, current authority context, and forces `target: flag` on an incomplete or stale one.
**Rationale:** direct verification of FR-002, SEC-001, and SEC-002, the classification seam's core behavioural contract.
**Source:** Business-need-design-brief.md §5.1, §11, §13.
**Priority:** P0.
**Dependencies:** FR-002, SEC-001, SEC-002.
**Maturity:** Current.

**Acceptance criteria:**
- `tests/candidate/test_classify.py` and `tests/policy/test_authority.py` both pass on a clean checkout.
- The suite includes at least one deliberately incomplete and one deliberately stale authority-context case, both asserting `target: flag`.
- The suite includes at least one ordinary, complete-context case, asserting a non-`flag` target with correct routing.

**Validation method:** `pytest tests/candidate/ tests/policy/`.
**Related risks:** Stale-context conflict resolution (brief §2.2, risk 2).
**Related architecture:** `src/modeller_memory/candidate/`, `src/modeller_memory/policy/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### TEST-003 - Companion-scope regression coverage

**Statement:** the test suite MUST verify that the companion provider returns nothing for a blank or unscoped `MemoryScope`, and correctly round-trips a write and read-back within an explicit scope.
**Rationale:** direct verification of FR-003 and FR-004, the companion-recall scaffold's core behavioural contract and the scope-leakage risk it exists to close.
**Source:** Business-need-design-brief.md §2.2 (risk 4), §5.2.
**Priority:** P1.
**Dependencies:** FR-003, FR-004.
**Maturity:** Current.

**Acceptance criteria:**
- `tests/companion/test_provider.py` passes on a clean checkout.
- The suite includes at least one blank/unscoped retrieval case, asserting an empty result.
- The suite includes at least one explicit-scope write-then-read case, asserting the same content is returned.

**Validation method:** `pytest tests/companion/`.
**Related risks:** Scope leakage (brief §2.2, risk 4).
**Related architecture:** `src/modeller_memory/companion/provider.py`.
**Related plan items:** None.
**Status:** Draft, to be validated

### TEST-004 - Pilot round-trip verification, once reachable

**Statement:** once modeller-agents' transport step exists, a test or manual verification exercise SHOULD confirm one full round trip: one observation, one `classify()` call, one ledger event, one transported candidate, one human review decision.
**Rationale:** direct re-key of the brief's suggested pilot and the MVP success bar it states.
**Source:** Business-need-design-brief.md §1, §8, §17 (OPN-002).
**Priority:** P1.
**Dependencies:** INT-002, HITL-003.
**Maturity:** Target; blocked on OPN-001 (modeller-agents transport step) and OPN-002 (whether and when the pilot runs).

**Acceptance criteria:**
- One bounded modelling task produces one observation that is classified, transported, and reviewed end to end.
- The reviewer can trace the delivered candidate back to its observation, authority context, and ledger event without gaps.
- The exercise's outcome (pass, fail, or partial) is recorded rather than assumed.

**Validation method:** Manual pilot exercise, per brief §8; not automatable until the transport step exists.
**Related risks:** None additional beyond OPN-001/OPN-002's blocking status.
**Related architecture:** Full classification seam plus modeller-agents' (not-yet-built) transport agent.
**Related plan items:** Blocked on OPN-001, OPN-002.
**Status:** Draft, to be validated

---

## 15. Minimal traceability

The expected traceability chain is:

```text
Business need
-> Shared concept
-> Requirement
-> Architecture component
-> Delivery batch
-> Acceptance criterion
-> Test
-> Controlled risk
```

Each P0 requirement above links to a business-need section, a named architecture component or contract, an acceptance test already present under `tests/`, and, where applicable, one of the brief's four named risks (silent promotion, stale-context conflict resolution, ownership collision, scope leakage). No formal delivery-batch or backlog structure exists yet for this repository; requirements blocked on a not-yet-built dependency name that dependency directly in their Maturity and Related plan items fields instead.

---

## 16. Definition of Ready for a requirement

A requirement is **Ready** when:

- its statement uses exactly one clear normative modality (MUST / MUST NOT / SHOULD / MAY);
- the source and owner are identified, and it traces to a business-need section or a logged open question;
- dependencies and risks are known;
- the acceptance criteria are testable;
- the necessary business decisions are made, or explicitly flagged as blocking (§19);
- its Maturity field is set and, if not Operational, names the blocking dependency;
- the impact on permissions, audit, and accessibility is analyzed.

## 17. Definition of Done for a requirement

A requirement is **Done** when:

- the implementation is delivered in the target environment;
- the acceptance criteria are satisfied;
- the applicable automated and manual tests pass;
- the necessary logs and metrics exist;
- the user and technical documentation is updated;
- approved deviations are recorded;
- the owner accepts the result.

---

## 18. Current exclusions

Out of the normative scope of this version:

- repository intelligence (the code graph): no implementation exists on disk under `adapters/`, `policy/freshness.py`, or an `mcp/` server; this document obligates nothing about it beyond BR-001's non-authoritative-layer boundary, which any future build must also respect;
- standing, persistent companion recall: gated behind evaluation criteria (false authority rate, cross-project leakage, useful-recall precision) that have not been run; NFR-003 obligates the current scaffold to stay non-persistent until those gates pass;
- the modeller-agents transport step's own internal design: this document obligates only what modeller-memory must supply to it (INT-002, HITL-003) and must not itself do, not how the transport step is built;
- modelling-knowledge's inbox contract's internal design: this document obligates only that a delivered candidate must carry full context (HITL-003), not the inbox's own schema or review workflow;
- automated conflict pre-check against a vault metadata index: named as a possible future optimisation, not required for this version, and not a general vault-retrieval capability;
- supply-chain pinning (`upstreams.lock.toml`) for a future code-graph or companion backend: named as an intention only, no backend is selected or fetched yet;
- automatic promotion of a candidate without human review: incompatible with HITL-001, and not reconsidered without a governance change.

---

## 19. Blocking open decisions

| ID | Decision | Affected requirements |
|---|---|---|
| OQ-001 | When will modeller-agents build the transport step (memory agent) that performs the actual inbox write for a `vault-inbox` candidate? | INT-002, HITL-003, TEST-004 |
| OQ-002 | Is the suggested pilot (one workflow, one candidate, one round trip through human review) worth running now, and against which live modeller-agents task? | SEC-001, TEST-004, NFR-001 |
| OQ-003 | Is repository intelligence (the code graph) worth building at all, and at what pace, relative to hardening the classification seam? | None directly; affects future requirement scope beyond this version (§18) |
| OQ-004 | What are the evaluation thresholds for the companion-recall activation gate (false authority rate, cross-project leakage, useful-recall precision)? | NFR-003, FR-003, FR-004 |
| OQ-005 | Does modelling-knowledge's inbox contract need any change to receive a candidate carrying this repository's authority-context and provenance shape? | INT-002, HITL-003 |

---

## 20. Requirement family summary

| Family | Count | ID range |
|---|---|---|
| BR (Business requirements) | 3 | BR-001 to BR-003 |
| FR (Functional requirements) | 4 | FR-001 to FR-004 |
| INT (Integration requirements) | 3 | INT-001 to INT-003 |
| DATA (Data requirements) | 3 | DATA-001 to DATA-003 |
| SEC (Security requirements) | 3 | SEC-001 to SEC-003 |
| NFR (Non-functional requirements) | 3 | NFR-001 to NFR-003 |
| OBS (Observability requirements) | 2 | OBS-001 to OBS-002 |
| HITL (Human-in-the-loop requirements) | 3 | HITL-001 to HITL-003 |
| TEST (Verification requirements) | 4 | TEST-001 to TEST-004 |
| **Total** | **28** | |
