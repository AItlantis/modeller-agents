# Modeller Memory: Business Need and Design Brief

**Recipients:** Maintainers of modeller-memory, modeller-agents, and modelling-knowledge
**Nature:** product vision, business framing, MVP scope and design mandate
**Status:** Draft for alignment
**Version:** 0.1, 25 July 2026
**Product:** modeller-memory, candidate-classification seam
**Upstream document:** docs/vision/Vision.md
**Downstream document:** docs/vision/Product-requirements-document.md

> This document sets out the business problem, the product vision, the users, the MVP journeys, the role of the contextual AI, and the product's boundaries.
> It does not replace `Product-requirements-document.md`, which carries the testable obligations, detailed rules, acceptance criteria, and non-functional requirements.

---

## 1. Executive summary

modeller-memory is a generated, non-authoritative connecting layer for the Aimsun agent ecosystem. Its goal is to give an in-flight agent, working on behalf of a transport modeller inside modeller-agents, a disciplined way to turn a working observation into something a human reviewer can safely consider for modelling-knowledge's governed vault, instead of letting that observation evaporate at session end or get written in informally.

Today, only one narrow slice of that goal is built and tested: an agent can submit a structured observation together with an orchestrator-supplied authority context, run it through `classify()`, and receive back a typed `MemoryCandidate` carrying a target, a classification, a confidence, provenance, and a sensitivity marking, with the transition recorded in a digest-chained candidate event ledger. A single, visible connecting layer, not a second decision-maker, supports this work: it proposes, it never approves, and it never writes to the vault. A smaller, explicitly non-persistent companion-recall scaffold also exists for session and project-scoped write-and-read-back of generated context.

modeller-memory is not meant to replace modelling-knowledge's governed inbox review, modeller-agents' orchestration, or a human reviewer's judgement. modelling-knowledge remains the sole authority over what becomes accepted knowledge; modeller-agents remains the sole owner of the skills that transport a candidate from this repository into that review.

> **Product promise: a working observation becomes a typed, evidenced candidate a human can review, never a silent second version of accepted knowledge.**

The MVP succeeds when an orchestrator acting for a modeller can submit one real observation and receive back a well-formed `MemoryCandidate` with correct target routing on both an ordinary and a stale-context case, and when a modelling-knowledge inbox reviewer, once modeller-agents' transport step exists, can trace that candidate back to the observation and authority context that produced it.

---

## 2. Business problem and opportunity

### 2.1 Current situation

An agent working inside modeller-agents on a bounded modelling task regularly produces observations and small decisions worth keeping: a repository structure noticed mid-task, a naming inconsistency, a candidate fact worth checking against accepted knowledge. Today those observations have nowhere disciplined to go. The orchestrator must regularly judge:

- whether an observation is worth keeping at all, with no typed object to keep it in;
- whether it might contradict something already accepted in modelling-knowledge, with no consistent way to check;
- whether it is safe to hand toward the vault, or whether it should stay session-local;
- whether, once produced, it can be traced back to the evidence and authority context that justified it.

A significant share of an agent's working output either evaporates at the end of a session, or gets written informally wherever is convenient, with no consistent seam into governed review.

### 2.2 Current risks

This fragmentation creates the four risks named in `Vision.md` Section 2 (stale-context conflict resolution, silent promotion of a memory-generated claim, ownership collision on a shared skill, and companion-recall scope leakage). This brief does not re-argue them; it names which ones the built classification seam already answers versus which remain open, in the opportunity table below.

> **Fundamental problem: an agent's working observations have no disciplined, evidenced path into human review, and any path built to close that gap must never become a second, quieter authority beside the vault it is meant to feed.**

### 2.3 Opportunity with modeller-memory

modeller-memory connects modeller-agents' working output to modelling-knowledge's governed inbox through one proven seam: classification. What is built today is narrow but real; the table below states plainly which relief already exists and which is still designed but not yet reachable end to end.

| Today | With modeller-memory (built today) |
|---|---|
| An observation has no typed shape; it is a note in a chat transcript or nowhere | `classify()` returns a typed `MemoryCandidate` (target, classification, confidence, provenance, sensitivity) |
| No record of how or when an observation was resolved | Every classification transition is recorded in a digest-chained, append-only candidate event ledger |
| Conflict detection would require memory to read the vault directly, which it cannot do safely | Classification runs an authority-context validator first and forces `target: flag` on incomplete or stale context, never a silent pass |
| A companion store, if built carelessly, could leak across projects | The in-memory companion scaffold requires an explicit `MemoryScope`; a blank or unscoped request returns nothing |

| Today | Designed, not yet reachable (do not oversell) |
|---|---|
| No code-graph or structural repository intelligence exists on disk | Repository intelligence (fast, freshness-stamped structural evidence) is architecture only; nothing is built |
| A classified candidate has no way to actually reach modelling-knowledge's inbox today | The transport step that performs the inbox write is owned by modeller-agents and is not yet built there |
| Companion recall is a per-process scaffold only | Persistent, standing companion recall is gated behind evaluation criteria that have not been run |

---

## 3. Product vision and product boundaries

modeller-memory becomes the disciplined seam between an agent's working observation and a human reviewer's decision, never a second store of organisational truth.

The connecting layer sits between modeller-agents and modelling-knowledge. It replaces neither modeller-agents' orchestration, nor modelling-knowledge's inbox review, nor the human reviewer's own judgement. It helps an orchestrator turn an observation into a typed candidate, with the authority context that should govern it attached and checked, and stops there.

### Product boundaries

For the MVP, modeller-memory:

- accepts a structured observation plus an orchestrator-supplied authority context and runs `classify()` to produce a typed `MemoryCandidate`;
- runs the authority-context validator first (completeness, vault pinning to modelling-knowledge, receipt checks, digest currency) before any conflict decision;
- records every classification transition in an append-only, digest-chained candidate event ledger that performs no vault or file I/O of its own;
- offers a scoped, explicitly non-persistent companion-recall scaffold for session or project-local write-and-read-back of generated context.

In the MVP, modeller-memory must not:

- read or write the modelling-knowledge vault in any way, from any module outside `tools/vault_doctor/`, which is an orthogonal, explicitly separate tool that only reads vault files read-only via an explicit `--vault-path` argument;
- write an inbox draft directly; `classify()` returns a typed candidate and stops, the actual inbox write belongs solely to a modeller-agents-owned agent;
- author or ship executable skills such as `memory-recon` or `memory-maintain`; skill ownership belongs solely to modeller-agents, this repository may at most provide non-executable `*.reference.md` examples;
- return companion-recall results for a blank or unscoped request; retrieval always requires an explicit scope.

---

## 4. Users, responsibilities and access

The MVP is designed first for the **orchestrator acting on behalf of a transport modeller**, an in-flight agent process inside modeller-agents. modeller-memory has no user interface of its own; every other party interacts with it indirectly, through modeller-agents' orchestration or modelling-knowledge's inbox. The matrix below is a working basis for design; it will need to be confirmed in the product requirements document.

| User | Main goal | Can do in the MVP | Cannot do by default | Authority or approval |
|---|---|---|---|---|
| **Orchestrator (modeller-agents, on behalf of a modeller)** | Turn a working observation into a reviewable candidate | Submit an observation plus authority context to `classify()`; receive a typed `MemoryCandidate`; write and read back scoped companion context | Write to the vault; decide a candidate is accepted; invoke a memory-owned skill | No standing authority; every classification is advisory, subject to modeller-agents' own transport and modelling-knowledge's review |
| **Inbox reviewer / antagonist board (modelling-knowledge)** | Decide whether a candidate becomes accepted knowledge | Trace a promoted candidate back to its observation, authority context, and evidence, once modeller-agents' transport step delivers it | Query modeller-memory directly; modeller-memory has no interface exposed to them | Sole authority over acceptance; interacts with modeller-memory's output only, never with modeller-memory itself |
| **Maintainer (modeller-memory)** | Keep the classification seam correct, tested, and isolated | Extend `classify()`, the policy checks, and the event ledger; run the import-guard and candidate test suites | Add a vault read or write path; add an executable skill to this repository | Repository-local; changes to the vault-boundary ADRs need cross-repo agreement |
| **Maintainer (modeller-agents / modelling-knowledge)** | Decide whether and how to build the transport step and the code-graph build-out | Consume this repository's contracts (`docs/contracts/`, `schemas/`) as the API surface | Change modeller-memory's classification policy unilaterally | Joint, per the cross-repo decisions recorded in `modelling-knowledge`'s decision 0007 and this repository's ADR-0004 |

### Project responsibilities

| Project responsibility | Expected role |
|---|---|
| **Classification logic and policy checks** | modeller-memory maintainers, under `src/modeller_memory/candidate/` and `src/modeller_memory/policy/` |
| **Authority-context supply and completeness** | The orchestrator inside modeller-agents, which retrieves accepted knowledge before calling `classify()` |
| **Candidate transport into the inbox** | A modeller-agents-owned memory agent, not yet built |
| **Acceptance of a candidate as knowledge** | modelling-knowledge's inbox reviewers and antagonist boards, exclusively |

---

## 5. MVP user journeys

### 5.1 Orchestrator's main journey (built and testable today)

1. The orchestrator, acting on a modeller's behalf inside modeller-agents, completes a bounded step of a modelling task and produces an observation worth keeping.
2. It retrieves the accepted knowledge relevant to that observation and attaches it as an authority context: accepted-knowledge references, the source repository commit, and applicable decisions.
3. It submits the observation and authority context to modeller-memory's `classify()` contract.
4. modeller-memory runs the authority-context validator first: completeness, vault pinning to modelling-knowledge, receipt checks, digest currency.
5. If the context is incomplete or stale, `classify()` forces `target: flag` rather than silently proceeding.
6. If the context passes validation, `classify()` resolves the observation against it and returns a typed `MemoryCandidate` with a recommended target, classification, confidence, provenance, and sensitivity.
7. The classification transition is recorded as an event in the append-only, digest-chained candidate event ledger.
8. The orchestrator holds the returned `MemoryCandidate`, ready to hand to modeller-agents' own transport step once that step exists; modeller-memory's own involvement stops here.

### 5.2 Orchestrator's companion-recall journey (scaffold only, not standing recall)

1. Within a single session or project, the orchestrator writes a generated piece of context into the scoped companion provider, with an explicit `MemoryScope`.
2. Later in the same session or project, the orchestrator reads that context back using the same explicit scope.
3. A request made with a blank or unscoped `MemoryScope` returns nothing; there is no default, unscoped recall.
4. Nothing written here persists beyond the process; this is not standing recall, and is not represented to the orchestrator as durable.

### 5.3 Inbox reviewer's journey (designed, not yet reachable end to end)

1. A modeller-agents-owned memory agent, once built, receives a `MemoryCandidate` recommending `target: vault-inbox` and performs the actual write into modelling-knowledge's inbox.
2. The inbox reviewer opens the drafted candidate and reads its attached authority context and provenance.
3. The reviewer traces the candidate back to the observation and evidence that produced it, and to the classification event in the ledger.
4. The reviewer accepts, rejects, or requests correction; modeller-memory has no further part in this decision.

This journey cannot be exercised today: the transport step it depends on is not yet built in modeller-agents. It is recorded here as the shape the MVP is designed to complete, not as something already working.

### 5.4 Maintainer's journey

1. A maintainer extends or adjusts a classification policy check under `src/modeller_memory/policy/`.
2. The import-guard test (`tests/test_import_guards.py`) confirms no runtime module outside `tools/vault_doctor/` imports `vault_doctor`.
3. The candidate and policy test suites (`tests/candidate/`, `tests/policy/`) confirm the classification and ledger behaviour still holds.

The MVP must demonstrate the continuity of the built classification journey end to end, from observation through `classify()` to a ledger entry, even though the journey's final step, the actual inbox write and its review, currently depends on work not yet done in a sibling repository.

---

## 6. How modeller-memory supports the work

The single callable step, `classify(candidate, authority_context)`, is what Section 5.1 walks through end to end; this section adds only what that journey doesn't already cover. Sequencing, retry, and analysis of the result belong to the orchestrator, not to this repository; modeller-memory has no workflow, no dashboard, and no review surface of its own, only the classification call and the ledger event it produces (Section 5.1, steps 3-7).

Repository intelligence, the code-graph capability named in the vision, is designed to eventually connect an agent's plan to the actual state of a codebase, but nothing under `adapters/`, `policy/freshness.py`, or an `mcp/` server exists on disk today; the classification seam remains the only proven runtime touchpoint between modeller-memory and modeller-agents.

---

## 7. Organization of a modeller-memory interaction

An interaction with modeller-memory represents one classification call, plus the ledger event it produces, and is the central unit this repository's contracts operate on. It involves at minimum:

- one structured observation, supplied by the orchestrator;
- one orchestrator-supplied authority context, attached before classification;
- one `classify()` call, producing exactly one typed `MemoryCandidate`;
- one ledger event, recording the transition;
- optionally, one scoped companion-recall write or read, independent of classification;
- eventually, one transport step and one inbox review, both outside this repository's own scope.

### Core relationships

- **Observation**: the structured input an orchestrator submits; it is not itself typed knowledge until classified.
- **Authority context**: the accepted-knowledge references, source commit, and applicable decisions the observation should be judged against; supplied by the orchestrator, never read independently by modeller-memory.
- **MemoryCandidate**: the typed output of `classify()`, carrying a target, classification, confidence, provenance, and sensitivity.
- **Candidate event ledger**: the append-only, digest-chained record of every classification transition; evidence, not a store of accepted fact.
- **MemoryScope**: the explicit session or project boundary a companion-recall write or read must specify; there is no unscoped default.

The active context must always let the orchestrator understand which observation, which authority context, and which resulting candidate they are working with.

---

## 8. Need-to-result cycle

Section 5.1 walks through this cycle in full (express the objective, attach authority context, classify, record the ledger event); modeller-memory's own part ends at that journey's step 7. What Section 5.1 doesn't state explicitly: this cycle replaces an observation's silent disappearance, or its informal write-in, with one evidenced, typed step, even though its final two steps (transport and inbox review) currently depend on work outside this repository.

---

## 9. The contextual AI agent

There is no user-facing AI agent inside modeller-memory. The "agent" a human ultimately deals with is the orchestrator inside modeller-agents; modeller-memory is a library and contract surface that orchestrator calls into, single and visible from the orchestrator's side, never a second assistant a person interacts with directly.

### 9.1 Context understood by modeller-memory

`classify()` uses only what is explicitly supplied:

- the structured observation itself;
- the orchestrator-supplied authority context (accepted-knowledge references, source commit, applicable decisions);
- nothing read independently from the modelling-knowledge vault;
- nothing read independently from the host repository's structure, since repository intelligence is unbuilt;
- an explicit `MemoryScope`, for any companion-recall write or read.

The orchestrator must be able to see and correct the authority context it supplies before an important classification, since `classify()` trusts that context and does not independently verify it against the vault.

### 9.2 Actions supported in the MVP

modeller-memory can: validate an authority context for completeness, pinning, receipt, and digest currency; classify a structured observation into a typed `MemoryCandidate`; record the classification transition in the candidate event ledger; store and retrieve scoped, non-persistent companion context within an explicit `MemoryScope`.

### 9.3 Prohibited or tightly controlled actions

modeller-memory cannot:

- read or write the modelling-knowledge vault, from any module outside `tools/vault_doctor/`;
- write an inbox draft directly, that action belongs solely to a modeller-agents-owned transport agent;
- approve, reject, or otherwise decide the fate of a candidate; that decision belongs solely to modelling-knowledge's inbox reviewers and antagonist boards;
- present its own classification as an accepted fact rather than a proposal;
- return companion-recall results outside an explicit scope;
- author or ship an executable skill.

### 9.4 Risk-proportional control

| Level | Examples | Expected control |
|---|---|---|
| **Low** | Reading back a scoped companion-context entry within the same session | Direct, visible, and reversible; scope-limited by construction |
| **Medium** | Submitting an observation with a complete, current authority context | `classify()` proceeds, but the returned candidate is a proposal only, never an executed action |
| **High** | Submitting an observation with an incomplete or stale authority context | `classify()` forces `target: flag`, never a silent `vault-inbox` or a silent discard |
| **Very high** | Any write to the modelling-knowledge vault | Out of modeller-memory's scope entirely; only modelling-knowledge's own governed inbox path may accept a candidate |

### 9.5 Output types

The interface a consumer builds on top of modeller-memory must clearly distinguish: the observation as submitted, the authority context as supplied, the classification confidence and target as a proposal, the ledger event as evidence of the transition, and the eventual human acceptance or rejection decision, which happens entirely outside this repository.

---

## 10. Evidence, review and publication

Every `MemoryCandidate` stays linked to the context that produced it: the observation, the authority context supplied at classification time, the classification outcome and confidence, and the ledger event recording the transition.

The MVP must make it possible to:

- retrieve the observation and authority context that produced a given candidate;
- identify whether a candidate's classification depended on a complete and current authority context, or was forced to `flag` because it did not;
- distinguish modeller-memory's proposed classification from any eventual human acceptance decision;
- re-read a candidate and its ledger event after the fact;
- confirm, once modeller-agents' transport step exists, that a candidate reaching modelling-knowledge's inbox carries its full authority context and evidence with it.

Repository intelligence, standing companion recall, and any automated conflict pre-check against a vault metadata index are out of MVP scope; none exist on disk or have passed an evaluation gate. The MVP must nonetheless flag an incomplete or stale authority context explicitly, through the `target: flag` outcome, rather than silently proceeding.

---

## 11. MVP functional scope by user

| User | Actions covered by the MVP |
|---|---|
| **Orchestrator (modeller-agents)** | Submit observation plus authority context to `classify()`; receive a typed `MemoryCandidate`; read the candidate event ledger; write and read scoped companion context |
| **Inbox reviewer (modelling-knowledge)** | Trace a delivered candidate back to its evidence, once modeller-agents' transport step exists; not reachable end to end today |
| **Maintainer (modeller-memory)** | Extend classification policy; run the import-guard and candidate/policy test suites; keep `tools/vault_doctor/` isolated from the runtime |

### Cross-cutting MVP capabilities

The classification seam must also provide: a machine-enforced boundary preventing any runtime module outside `tools/vault_doctor/` from importing `vault_doctor`; a forced `target: flag` outcome whenever the authority-context validator finds the context incomplete or stale; an append-only, digest-chained event for every classification transition; explicit-scope-only retrieval for companion context; and a typed, versioned `MemoryCandidate` schema that a downstream consumer can rely on without reading this repository's internals.

---

## 12. Parking lot

| Deferred feature | Main reason | Condition for reconsideration |
|---|---|---|
| Repository intelligence (code graph) | No implementation exists on disk; the vision names it a capability, not a built system | A concrete build proposal, reviewed and resourced separately from the classification seam |
| Standing, persistent companion recall | Gated behind evaluation criteria (false authority rate, cross-project leakage, useful-recall precision) that have not been run | The evaluation gates in the integration plan's section 6f are run and pass |
| Automated conflict pre-check against a vault metadata index | Named as a possible future optimisation, not required for v1, and not a general vault-retrieval capability | A specific, scoped design proposal reviewed jointly with modelling-knowledge |
| Supply-chain pinning for a code-graph or companion backend (`upstreams.lock.toml`) | Named as an intention only; no backend is selected or fetched yet | A backend is actually chosen for repository intelligence or companion recall |
| Automatic promotion of a candidate without human review | Incompatible with expected human control | No reconsideration planned without a governance change |
| A modeller-memory-owned executable skill | Skill ownership belongs solely to modeller-agents by ADR-0002 | Only if the ecosystem's skill-ownership decision itself is revisited |

---

## 13. Expected outcomes and success measures

The measures must compare the MVP to the current situation, where an observation has no typed path into review at all. Target values will be defined after observing real workflows; the suggested pilot in the upstream vision (one bounded task, one candidate, one round trip through human review) is the intended first source of that observation.

| User | Key action | Expected outcome | Candidate indicator |
|---|---|---|---|
| Orchestrator | Submit an observation with a complete, current authority context | Receives a well-formed `MemoryCandidate` with a correct target recommendation | Classification correctness on a small hand-checked set, defined after the pilot |
| Orchestrator | Submit an observation with an incomplete or stale authority context | `classify()` forces `target: flag`, never a silent pass | Rate of correctly forced flags on deliberately incomplete test contexts |
| Maintainer | Run the test suite after a policy change | Import-guard and candidate/policy tests still pass | Test suite pass rate, tracked as part of normal CI |
| Inbox reviewer | Trace a delivered candidate back to its evidence | Full authority context and provenance are present and legible | Not measurable until modeller-agents' transport step exists |

---

## 14. UI objective

modeller-memory has no user interface of its own; this section addresses what any consumer surface built on top of its contracts (inside modeller-agents or modelling-knowledge) must resolve, not a screen this repository builds.

The design must resolve as a priority:

- a clear, persistent representation of which observation and which authority context produced a given candidate;
- the distinction between a candidate's confidence and target as a proposal, and any human acceptance decision;
- a legible explanation when `classify()` forces `target: flag` because the authority context was incomplete or stale;
- tracking a candidate from classification through to an eventual inbox review, once transport exists, without hiding the gap that exists today;
- a simplified path for a maintainer confirming the import-guard boundary still holds after a change.

---

## 15. Expected deliverables from design

The design team must produce:

1. a detailed journey for the orchestrator's classification call, from observation through `classify()` to the ledger event, matching what is actually built today;
2. a service blueprint linking the orchestrator, `classify()`, the authority-context validator, the candidate event ledger, and the not-yet-built modeller-agents transport step, with the gap clearly marked;
3. an information architecture for how a `MemoryCandidate` and its ledger event are presented to a maintainer or, eventually, an inbox reviewer;
4. an interaction model for the scoped companion-recall scaffold, making clear it is session or project-local and non-persistent;
5. wireframes, if any consumer surface is planned, for viewing a candidate's authority context and classification outcome;
6. a design decision matrix distinguishing what modeller-memory's contracts already support from what depends on modeller-agents' or modelling-knowledge's own unbuilt work;
7. rules for presenting a classification confidence, a forced flag, and a human decision as visibly distinct output types.

---

## 16. Expected input from product and technology

### Product and business

Definition of what counts as a complete and current authority context, sufficient for the N-2 validator to be trusted; the criteria for the suggested pilot's definition of a successful round trip; the priority and sequencing of the repository-intelligence build-out relative to hardening the classification seam; the evaluation thresholds a companion-recall activation gate must meet before section 6f's criteria are run.

### Technology

Confirmation from modeller-agents of when its transport step (the memory agent that validates a candidate's destination and performs the inbox write) will be built; confirmation from modelling-knowledge of the inbox contract's stability for a live candidate exercise; the supply-chain pinning approach for any future code-graph or companion backend; the outcome of running the companion-recall evaluation gates in section 6f of the integration plan; performance and reliability expectations for `classify()` under a live modeller-agents workflow, once one is run.

---

## 17. Priority open questions

| ID | Question | Main impact | Suggested owner |
|---|---|---|---|
| **OPN-001** | When will modeller-agents build the transport step (memory agent) that performs the actual inbox write for a `vault-inbox` candidate? | Blocks the classification seam from ever completing an end-to-end round trip | modeller-agents maintainers |
| **OPN-002** | Is the suggested pilot (one workflow, one candidate, one round trip through human review) worth running now, and against which live modeller-agents task? | Determines whether the N-2 authority-context fence gets its first live proof | modeller-memory and modeller-agents maintainers jointly |
| **OPN-003** | Is repository intelligence (the code graph) worth building at all, and at what pace, relative to hardening the classification seam? | Determines whether design effort should extend beyond the classification MVP scoped here | modeller-memory maintainers, per the vision's own framing |
| **OPN-004** | What are the evaluation thresholds for the companion-recall activation gate (false authority rate, cross-project leakage, useful-recall precision)? | Blocks any move from the current in-memory scaffold toward standing companion recall | modeller-memory maintainers |
| **OPN-005** | Does modelling-knowledge's inbox contract need any change to receive a candidate carrying this repository's authority-context and provenance shape? | Affects whether the transport step, once built, can hand off cleanly | modelling-knowledge maintainers |

---

## 18. Consolidated statement of need

modeller-memory must let an orchestrator acting on behalf of a transport modeller submit a structured observation with its authority context, receive back a typed, evidenced `MemoryCandidate`, and have that transition recorded in an auditable, digest-chained ledger, all without modeller-memory itself ever reading or writing modelling-knowledge's vault.

This connecting layer must understand only the context explicitly supplied to it, propose a classification without deciding a candidate's fate, and stop cleanly at the boundary where modeller-agents' transport step and modelling-knowledge's governed review begin. Nothing it produces becomes accepted knowledge on its own authority.

Every classified candidate must remain linked to the observation and authority context that produced it, and to an identifiable human decision once it reaches review. Design work should proceed against what is actually built today, the classification seam, and should treat repository intelligence, the transport step, and standing companion recall as named, honestly unbuilt or unproven pieces this brief does not ask design to assume are already working.
