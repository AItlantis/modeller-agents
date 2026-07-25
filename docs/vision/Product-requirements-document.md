# modeller-agents, Product Requirements Document

**Nature:** Initial product specification, translating the repository's own business-need and design brief into testable obligations for an active codebase
**Status:** Draft, to be validated by the ecosystem maintainers named in the upstream brief's audience
**Version:** 0.1, 25 July 2026
**Upstream documents:** docs/vision/Business-need-design-brief.md
**Consistency matrix:** None exists for this doc set

---

## 1. Purpose and scope

This document translates the modeller-agents Business Need and Design Brief into testable requirements. It forms the basis for design, architecture, delivery breakdown, and the MVP validation described in the brief: an ecosystem maintainer running `doctor --strict --json` against the repository's own already-registered `aimsun-psp` backend and seeing an empty `readiness_blockers` array.

It does not replace:

- the business-need / design brief, which explains the why and the journeys;
- the detailed architecture decisions, recorded in `docs/architecture/BOUNDARIES.md`;
- the interface specifications for the `modeller` CLI;
- the API contracts owned by `modeller-pipelines` (`vendor/modeller-pipelines/contracts/schemas`);
- the technical test plans under the repository's own test suite;
- `docs/readiness/STRICT_READINESS.md`, which is authoritative on the six blocker codes' exact remediation steps.

This PRD carries live, issued obligations for the modeller-agents repository as it stands today, not a historical or consolidated record. Where a capability described in the brief is not yet built, the corresponding requirement's Maturity field says so plainly and names the blocking dependency, rather than asserting a status the codebase does not yet support.

---

## 2. Traceability to upstream documents

| Upstream document | Relevant sections | What this PRD obligates |
|---|---|---|
| `Business-need-design-brief.md` | §2 (business problem, current risks), §3 (product boundaries), §4 (users and responsibilities), §5 (MVP journeys), §6 (how modeller-agents supports the work), §7 (organization of a request), §9 (contextual AI agent), §10 (evidence and review), §11 (functional scope), §12 (parking lot) | Turns the MVP scope, the six-blocker remediation journey, the route/workflow/backend seam, and the human-review gate discipline into testable requirements |
| `docs/readiness/STRICT_READINESS.md` | Vendor, reference-pack, sibling-schema, and backend-smoke blocker sections | Confirms the exact remediation conditions each readiness requirement below cites as acceptance criteria |
| `AGENTS.md` | Boundary section | Confirms the forbidden-actions list this PRD's MUST NOT requirements re-key |

Every requirement below carries a **Source** field pointing back to one of these sections, or to an explicitly logged open question (see §19 Blocking Open Decisions) when the upstream decision is not yet made.

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
| **P0** | Required for the MVP's own definition of done: `doctor --strict --json` exits `0` with an empty `readiness_blockers[]` array |
| **P1** | Important for a complete, trustworthy MVP but not itself a strict-readiness blocker |
| **P2** | Improvement that can be deferred beyond the MVP |

### Status-ladder discipline

Use the ecosystem's full status-ladder word set only: Current, Operational, Emerging, Target, Proposed, Deferred, Legacy. A requirement against a capability that is not Operational says so in its own Rationale, not in a footnote.

- **CURRENT**: the requirement targets a capability that exists in the codebase today, but is not yet proven in production use.
- **OPERATIONAL**: the requirement targets a capability already proven in real use, evidenced by a passing test suite or a live run; only used where the codebase or a recorded run backs the claim.
- **EMERGING**: the requirement targets a capability under active but incomplete construction; the requirement text names the gap that keeps it from being Current.
- **TARGET**: the requirement targets a capability planned but not yet started; the requirement text says so and names the dependency that must land first.
- **PROPOSED**: the requirement targets a capability that is only a candidate direction, not yet committed; treated with the same caution as an open decision (see §19).
- **DEFERRED** / **LEGACY**: not used in this document. Nothing in this PRD's scope is deferred-but-obligated or historical; deferred capability is instead excluded from scope entirely (see §18).

Per the brief's own note on upstream status, `Vision.md` is itself dated today, versioned 0.1, and self-labelled "draft strategic reflection," not yet reviewed or accepted by the ecosystem maintainers it names as its audience. Every requirement below that traces to `Vision.md` inherits that open status; none of the Maturity fields below treat `Vision.md`'s acceptance as settled.

---

## 4. Definitions and actors

| Term | Definition |
|---|---|
| Governed context envelope | The declared unit of work: intent, target repository, domains, risk level, and consent state, carried through route, workflow, and manifest under one accountable orchestrating-agent identity. |
| Bundle | A manifest selecting the skill and the reference packs authorized to back it for a given routing key. |
| Reference pack | Repository-specific constraints and authorizing metadata; for knowledge packs, carries note IDs and routing metadata only, never note bodies, thresholds, or decision text. |
| Workflow run | A sequence of gated steps, each owned by a named role, each requiring specific artifact evidence before the next step opens. |
| Backend registration | `backends.toml`'s entry for a backend, its `expected_contract`, and its `status`, resolved against that backend's own `backend.json` and declared `runner.command`. |
| RunManifest | The closing artifact referencing workflow state, artifacts, gates, and subagent lane receipts by path and SHA-256 digest. |
| Strict readiness | The release/CI gate (`doctor --strict`), stricter than the advisory local `doctor` check; fails on any of six documented blocker codes. |

| Actor | Description |
|---|---|
| Ecosystem maintainer | Runs readiness checks, remediates blockers, decides when a backend or reference pack is release-ready. |
| Orchestrating agent | The primary machine actor issuing governed context envelopes and consuming routed and workflow output, bound by the envelope's own declared permissions and consent state. |
| Human reviewer | Sole authority for a human-review gate; approves or rejects medium/high risk execution; the workflow accepts only a receipt with `reviewer.actor_type: human`. |
| Sibling repository maintainer | Maintainer of `aimsun-psp`, `modeller-pipelines`, `modeller-memory`, or `modelling-knowledge`, consulted whenever a change touches their vendored content, registered backend, or authority. |

---

## 5. Requirement entry format

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

**Validation method:** {{how this will be tested, e.g. "end-to-end user test", "permission test"}}
**Related risks:** {{risk IDs, if a risk register exists upstream}}
**Related architecture:** {{architecture component IDs, if applicable}}
**Related plan items:** {{delivery batch IDs, if applicable}}
**Status:** Draft, to be validated

---

## 6. Business requirements (BR)

Product-level obligations that follow directly from the business need: what the routing and gating seam must be organized around, what it must never do to a sibling repository's authority, and what continuity of evidence it must preserve.

### BR-001 - Composition without absorption

**Statement:** modeller-agents MUST route and gate requests to `modelling-knowledge`, `modeller-memory`, `aimsun-psp`, and `modeller-pipelines` without absorbing their domain authority.
**Rationale:** the brief names this as the product's core boundary; a routing layer that quietly becomes a second authority over accepted knowledge, generated memory, backend implementation, or pipeline contracts defeats the single-source-of-truth guarantee the ecosystem depends on.
**Source:** Business Need §3 (product boundaries), §18 (consolidated statement of need).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; the boundary is enforced today in `AGENTS.md`'s forbidden-actions list and exercised by the current test suite (156/156 passing).

**Acceptance criteria:**
- no code path in modeller-agents writes knowledge-pack content beyond note IDs and routing metadata;
- no code path imports `aimsun-psp` backend implementation, Testudo product/runtime logic, or `modeller-pipelines` schema definitions;
- a generated memory index is never stored or treated as authoritative.

**Validation method:** static source inspection for forbidden imports; schema validation rejecting copied-knowledge fields.
**Related risks:** knowledge duplication (Business Need §2.2).
**Related architecture:** `docs/architecture/BOUNDARIES.md`.
**Related plan items:** None.
**Status:** Draft, to be validated

### BR-002 - Single accountable orchestrating-agent identity

**Statement:** modeller-agents MUST carry exactly one accountable orchestrating-agent identity through a governed envelope's routing, workflow, and backend invocation, from issue to `RunManifest`.
**Rationale:** the single, visible contextual AI agent framing is the product's central accountability guarantee; a fragmented or untraceable set of actors behind one envelope would defeat the evidence chain the MVP exists to prove.
**Source:** Business Need §1 (executive summary), §9 (the contextual AI agent).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current; the envelope and manifest schemas carry an identity field today, but no MVP journey has yet exercised the full envelope-to-manifest chain end to end against a real backend (see INT-003, still Target).

**Acceptance criteria:**
- every envelope declares one orchestrating-agent identity;
- that identity is present, unchanged, in the resulting workflow run and `RunManifest`;
- no code path allows a second, undeclared actor to advance a workflow step under the same envelope.

**Validation method:** schema validation of the envelope and `RunManifest`; identity-continuity test across route, workflow, and manifest.
**Related risks:** unproven done claims (Business Need §2.2).
**Related architecture:** envelope and `RunManifest` schemas under `schemas/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### BR-003 - Evidence before "done"

**Statement:** modeller-agents MUST require artifact evidence, addressable by path and SHA-256 digest, before any workflow step or backend claim is treated as complete.
**Rationale:** direct answer to the "unproven done claims" risk named in the brief; the product's central promise is that a claim of done is checkable, not merely asserted.
**Source:** Business Need §2.2 (current risks), §6.6 (facilitate the review), §10 (evidence, review and publication).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current; the workflow's artifact-gating mechanism is built and test-covered, but the MVP's own definition of done, one real backend smoke producing schema-valid evidence, has not yet passed (Business Need §1). See INT-003.

**Acceptance criteria:**
- a workflow step does not advance without its required artifact evidence present;
- every `RunManifest` entry references evidence by path and SHA-256 digest, not by description alone;
- a human reviewer can independently retrieve and check the referenced evidence.

**Validation method:** workflow-gate test attempting to advance without required evidence, expecting rejection.
**Related risks:** unproven done claims (Business Need §2.2).
**Related architecture:** workflow runtime, `RunManifest` schema.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 7. Functional requirements (FR)

User-facing and CLI-facing capabilities mapped to the MVP journeys in the business-need brief: closing the strict-readiness blocker list, routing a governed envelope, and driving a workflow.

### FR-001 - Advisory and strict doctor distinction

**Statement:** the `modeller` CLI MUST provide both an advisory local `doctor` check and a release-grade `doctor --strict` check, and MUST NOT conflate the two in its output.
**Rationale:** local development tolerates planned vendors, draft packs, sibling schema fallback, and unproven backend wiring; release readiness must not, per `docs/readiness/STRICT_READINESS.md`.
**Source:** Business Need §3 (product boundaries), §6.5 (support the analysis), §14 (UI objective).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; both commands exist and run today, exercised in `docs/readiness/STRICT_READINESS.md`'s documented commands.

**Acceptance criteria:**
- `doctor --root .` and `doctor --root . --strict` are separately invocable;
- strict mode fails on any of the six documented blocker codes that advisory mode tolerates;
- CLI output visually distinguishes which mode produced a given result.

**Validation method:** CLI output inspection against both modes on a fixture with known blockers.
**Related risks:** unchecked boundary crossing if the two are conflated (Business Need §2.2).
**Related architecture:** `tools/` (`modeller` CLI), `docs/readiness/STRICT_READINESS.md`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-002 - Stable, remediable blocker codes

**Statement:** `doctor --strict --json` MUST emit `readiness_blockers[]` entries with stable `code`, `message`, `path`, and `remediation` fields for each of the six documented blocker codes.
**Rationale:** the ecosystem maintainer's entire MVP journey (Business Need §5.1) is driven by reading and remediating this array; an unstable or ambiguous shape would break the journey and any orchestrator parsing it.
**Source:** Business Need §5.1 (maintainer's journey), §11 (cross-cutting MVP capabilities), §15 (expected deliverables, item 3).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; the six codes (`reference-pack-not-active`, `backend-not-active`, `backend-contract-unpinned`, `vendor-not-synced`, `vendor-not-pinned`, `schema-sibling-fallback`) are live today per `docs/readiness/STRICT_READINESS.md` and confirmed producing 10 concrete blocker instances in the current repository state.

**Acceptance criteria:**
- every blocker entry carries non-null `code`, `message`, `path`, and `remediation`;
- the same underlying condition always produces the same `code` across repeated runs;
- remediating the underlying condition removes exactly that entry from a subsequent run, with no other entries changed.

**Validation method:** `doctor --strict --json` re-run before and after a targeted remediation, diffing the `readiness_blockers[]` array.
**Related risks:** registered-but-untested backends, unchecked boundary crossing (Business Need §2.2).
**Related architecture:** `tools/` (`modeller` CLI doctor command).
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-003 - Vendor sync and pin remediation

**Statement:** the `modeller` CLI MUST provide a `sync` command that prints the exact `git subtree pull` command for a named vendor without executing it, so an operator can confirm the remote and ref before pinning `modeller-memory` and `modeller-pipelines` to an immutable revision.
**Rationale:** direct re-key of the maintainer's journey step 2; a vendor pin must be a confirmed, human-checked action, not a silent automatic sync, per `AGENTS.md`'s prohibition on editing vendored subtrees by hand or trusting an unconfirmed source.
**Source:** Business Need §5.1 (maintainer's journey, step 2), §2.1 (current situation), §17 OPN-003.
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; `sync` exists and is documented as printing, not executing, the subtree command, per `docs/readiness/STRICT_READINESS.md`.

**Acceptance criteria:**
- `sync <vendor>` prints the subtree pull command and takes no write action itself;
- after an operator-confirmed sync and a `vendors.toml` update, the vendor's `status` is no longer `planned` and `pinned` records the immutable synced revision;
- `doctor --strict` no longer reports `vendor-not-synced` or `vendor-not-pinned` for that vendor.

**Validation method:** end-to-end vendor remediation test: run `sync`, apply the printed command, update `vendors.toml`, re-run `doctor --strict`.
**Related risks:** registered-but-untested backends (transitively, via unpinned contract schemas).
**Related architecture:** `vendors.toml`, `vendor/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-004 - Reference pack promotion to active

**Statement:** the ecosystem maintainer MUST be able to promote a bundle-referenced reference pack's `status` from `draft` to `active` once its shape is confirmed valid and any draft-only open decisions are closed or explicitly moved out of release scope.
**Rationale:** direct re-key of the maintainer's journey step 3; strict readiness blocks release on any bundle-selected pack that is still `draft`.
**Source:** Business Need §5.1 (maintainer's journey, step 3), §2.3 (opportunity table).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Emerging; the promotion mechanism (editing a pack's `status` field) exists, but the MVP has not yet demonstrated all four bundle-referenced packs (aimsun-psp, modeller-pipelines, modelling-knowledge, testudo) promoted to active in one confirmed pass, per the brief's own MVP-shaped scope.

**Acceptance criteria:**
- every bundle-referenced reference pack under `reference-packs/` has valid TOML and the required shape before promotion;
- the union of selected reference packs authorizes every central skill its bundle selects;
- `doctor --strict` no longer reports `reference-pack-not-active` for a promoted pack.

**Validation method:** `doctor --strict` re-run before and after promoting each of the four bundle-referenced packs.
**Related risks:** knowledge duplication if a pack is promoted without its shape confirmed (Business Need §2.2).
**Related architecture:** `reference-packs/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-005 - Vendored schema resolution over sibling fallback

**Statement:** contract schema resolution MUST use `vendor/modeller-pipelines/contracts/schemas` once that vendored copy exists and is pinned, and MUST NOT silently rely on sibling-checkout fallback for a strict-readiness pass.
**Rationale:** direct re-key of the maintainer's journey step 4; sibling fallback depends on a checkout layout that is not guaranteed to exist for every operator or CI runner.
**Source:** Business Need §5.1 (maintainer's journey, step 4), §2.1 (current situation, third bullet).
**Priority:** P0.
**Dependencies:** FR-003.
**Maturity:** Emerging; the fallback mechanism and the blocker detection both exist today, but the vendored copy is not yet populated and pinned in the current repository state, per the brief's confirmed live findings.

**Acceptance criteria:**
- `vendor/modeller-pipelines/contracts/schemas` contains `backend.schema.json`, `pipeline.schema.json`, `result.schema.json`, `run-config.schema.json`, and `step-result.schema.json`;
- `vendors.toml` pins `modeller-pipelines` to the revision that supplied those schemas;
- `doctor --strict` no longer reports `schema-sibling-fallback`.

**Validation method:** `doctor --strict` re-run confirming the sibling-fallback blocker is absent; schema-resolution unit test asserting the vendored path is used first.
**Related risks:** knowledge duplication, if the sibling and vendored copies silently diverge (Business Need §2.2).
**Related architecture:** `vendor/modeller-pipelines/contracts/schemas`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-006 - Route resolution to bundle, skill, and authorizing packs

**Statement:** `route` MUST resolve a governed context envelope to a bundle, a skill, and the reference packs that authorize that skill, or return `ok: false` when any of the three cannot be resolved.
**Rationale:** direct re-key of the orchestrating agent's journey step 2; this is the routing layer's core function and its fail-closed guarantee.
**Source:** Business Need §5.2 (orchestrating agent's journey), §3 (product boundaries), §9.2 (actions supported).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; `route` and its fail-closed behavior are built and exercised today (156/156 tests passing per Business Need §2.1).

**Acceptance criteria:**
- a resolvable envelope returns a bundle, a skill, and the authorizing reference packs;
- an envelope whose bundle, skill, or authorizing pack cannot be resolved returns `ok: false`, never a partial or best-guess result;
- the resolved output is stable and traceable to the envelope that produced it.

**Validation method:** route resolution test against both a resolvable and an intentionally unresolvable envelope fixture.
**Related risks:** unchecked boundary crossing (Business Need §2.2).
**Related architecture:** routing layer under `tools/`, `bundles/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### FR-007 - Deterministic workflow progression

**Statement:** `workflow init` / `status` / `check` / `advance` MUST drive a sequence of gated steps, each owned by a named role, each requiring specific artifact evidence before the next step opens.
**Rationale:** direct re-key of the orchestrating agent's journey step 3 and the business need's description of a deterministic workflow runtime as already built and exercised.
**Source:** Business Need §5.2 (orchestrating agent's journey), §6.2 (build the appropriate workflow), §7 (organization of a request).
**Priority:** P0.
**Dependencies:** FR-006.
**Maturity:** Operational; the workflow runtime and its named roles (orchestrator, planner, architect, executor, documenter) are built and exercised today.

**Acceptance criteria:**
- `workflow init` turns a routed objective into a sequence of gated steps;
- `status` and `check` accurately report which steps are open, blocked, or complete;
- `advance` refuses to open the next step without the required artifact evidence for the current one.

**Validation method:** workflow progression test exercising a full init-to-advance sequence, including one intentionally withheld artifact.
**Related risks:** unproven done claims (Business Need §2.2).
**Related architecture:** workflow runtime.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 8. Integration requirements (INT)

How a governed request becomes a backend invocation, how the seam is proven rather than asserted, and how the MVP's own definition of done is exercised end to end.

### INT-001 - Backend invocation only through the declared contract seam

**Statement:** modeller-agents MUST invoke a registered backend only through its declared seam (`backends.toml` to `backend.json` to `runner.command`), and MUST NOT import that backend's implementation.
**Rationale:** direct re-key of the product boundary and `AGENTS.md`'s explicit prohibition on copying `aimsun-psp` backend implementation; this is the seam that keeps backend authority with `aimsun-psp`.
**Source:** Business Need §3 (product boundaries), §6.3 (mobilize technical capabilities), §9.3 (prohibited actions).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current; the seam mechanism (registry lookup, manifest check, subprocess invocation of `runner.command`) exists in code today, but has not yet been exercised end to end against `aimsun-psp` with a passing result (see INT-003).

**Acceptance criteria:**
- a backend invocation resolves `backend_id` through `backends.toml` to the backend's own `backend.json` before executing;
- the executed command is exactly the backend's declared `runner.command` plus the run arguments;
- no source file in modeller-agents imports a module from `aimsun-psp`.

**Validation method:** static import-boundary check; invocation test asserting the subprocess command matches the declared `runner.command`.
**Related risks:** registered-but-untested backends (Business Need §2.2).
**Related architecture:** `backends.toml`, backend seam under `tools/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### INT-002 - Backend manifest and contract-version confirmation

**Statement:** before a backend smoke runs, modeller-agents MUST confirm the backend manifest via `backends --check <backend-id>`, verifying `backend.json.contract_version` matches the registry's `expected_contract` and the requested pipeline id is declared in `backend.json.pipelines`.
**Rationale:** direct re-key of the maintainer's journey step 5 and the smoke-blocker remediation conditions in `docs/readiness/STRICT_READINESS.md`; an unconfirmed contract version would let a smoke pass against the wrong contract shape.
**Source:** Business Need §5.1 (maintainer's journey, step 5), §17 OPN-002.
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; `backends --check` exists and is documented as a live command in `docs/readiness/STRICT_READINESS.md`.

**Acceptance criteria:**
- `backends --check aimsun-psp` reports whether `backend.json` exists at the configured backend root;
- the check reports a mismatch if `contract_version` differs from the registry's `expected_contract`;
- the check confirms the requested pipeline id is present in `backend.json.pipelines`.

**Validation method:** manifest-check test against both a matching and an intentionally mismatched `backend.json` fixture.
**Related risks:** backend-contract-unpinned (Business Need §2.1, §2.3).
**Related architecture:** `backends.toml`, backend manifest schema.
**Related plan items:** None.
**Status:** Draft, to be validated

### INT-003 - Real backend smoke against aimsun-psp

**Statement:** modeller-agents MUST demonstrate one real backend smoke against the registered `aimsun-psp` backend, through its declared `runner.command`, producing a `result.json` that validates against the vendored `result.schema.json` with `status: success`, at least one step, and at least one artifact.
**Rationale:** this is the MVP's own definition of done, named directly in the business need's executive summary; it is the one capability in this document not yet proven, and the entire opportunity section of the brief is built around closing exactly this gap.
**Source:** Business Need §1 (executive summary), §5.1 (maintainer's journey, steps 6-8), §13 (success measures), §17 OPN-002.
**Priority:** P0.
**Dependencies:** INT-001, INT-002, FR-003, FR-005.
**Maturity:** Target. The seam mechanism and the smoke command exist and are documented in `docs/readiness/STRICT_READINESS.md`, but no passing smoke evidence has yet been produced against `aimsun-psp` in this repository's own record; the blocking dependency is completing the vendor-pin and schema-vendoring work (FR-003, FR-005) that the smoke's own preconditions require, and independent confirmation from `aimsun-psp` maintainers that their side of the seam (their own `backend.json`, their own readiness) is ready to receive the call, per Business Need §17 OPN-002.

**Acceptance criteria:**
- the backend process, invoked via `run --root . aimsun-psp <pipeline-id> --config <cfg> --run-dir <dir> --backend-root <path>`, exits with code `0`;
- the final non-empty stdout line is the absolute path to `result.json`;
- `result.json` validates against `vendor/modeller-pipelines/contracts/schemas/result.schema.json`;
- `result.json.backend_id`, `contract_version`, and `pipeline_id` match the expected backend, contract, and pipeline;
- every artifact path in the result is relative to the run directory;
- `backends.toml` marks `aimsun-psp` `active` only after this evidence exists.

**Validation method:** live smoke run per the release checklist in `docs/readiness/STRICT_READINESS.md`; `doctor --strict --json` re-run confirming `backend-not-active` is no longer reported.
**Related risks:** registered-but-untested backends (Business Need §2.2), the central risk this requirement exists to close.
**Related architecture:** `backends.toml`, `aimsun-psp` `backend.json` and `runner.command`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 9. Data requirements (DATA)

Identity and provenance for the units this repository composes around: the envelope, the workflow run, and the closing manifest.

### DATA-001 - Envelope as the unit of routed work

**Statement:** every routed request MUST be represented as a governed context envelope carrying, at minimum, a declared intent, target repository, domains, risk level, and consent state.
**Rationale:** direct re-key of Business Need §7's definition of the envelope as the central unit this repository composes around; without this minimum shape, downstream boundary and consent checks have nothing reliable to inspect.
**Source:** Business Need §7 (organization of a request), §9.1 (context understood by the agent).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; the envelope schema and its required fields exist and are exercised by `route` today.

**Acceptance criteria:**
- an envelope missing intent, target repository, domains, risk level, or consent state fails schema validation before routing;
- the envelope's declared fields, not an inferred value, are what `route` and the workflow layer act on;
- the envelope's fields remain visible and correctable by the ecosystem maintainer or human reviewer before an important gate decision.

**Validation method:** schema validation test against an envelope fixture missing a required field.
**Related risks:** unchecked boundary crossing (Business Need §2.2).
**Related architecture:** envelope schema under `schemas/`.
**Related plan items:** None.
**Status:** Draft, to be validated

### DATA-002 - RunManifest evidence addressed by path and digest

**Statement:** a `RunManifest` MUST reference workflow state, artifacts, gates, and subagent lane receipts by path and SHA-256 digest, not by description or claim alone.
**Rationale:** direct re-key of Business Need §6.6 and §10; this is what makes a `RunManifest` independently checkable by a human reviewer or a sibling repository maintainer rather than a narrative to be trusted.
**Source:** Business Need §6.6 (facilitate the review), §7 (core relationships), §10 (evidence, review and publication), §15 (expected deliverables, item 4).
**Priority:** P0.
**Dependencies:** BR-003.
**Maturity:** Current; the `RunManifest` schema and its path-plus-digest reference shape exist today, but has not yet been exercised against a real backend smoke's evidence (see INT-003).

**Acceptance criteria:**
- every evidence reference in a `RunManifest` includes both a path and a SHA-256 digest;
- a reviewer can retrieve the referenced artifact at that path and confirm the digest matches;
- `workflow manifest` and `workflow close` are the only commands that produce a `RunManifest`.

**Validation method:** manifest-generation test confirming every entry carries both fields; digest-mismatch test confirming a tampered artifact is detectable.
**Related risks:** unproven done claims (Business Need §2.2).
**Related architecture:** `RunManifest` schema.
**Related plan items:** None.
**Status:** Draft, to be validated

### DATA-003 - Vendor pin as immutable revision identity

**Statement:** a vendor entry in `vendors.toml` MUST identify its `pinned` revision as the immutable synced revision, not a mutable branch name such as `main` or `contract-v1.0`.
**Rationale:** direct re-key of `docs/readiness/STRICT_READINESS.md`'s explicit warning; a branch-name pin gives no reproducible guarantee of which contract schemas or memory content a given release actually used.
**Source:** Business Need §2.1 (current situation), §17 OPN-003; `docs/readiness/STRICT_READINESS.md` (vendor blockers section).
**Priority:** P0.
**Dependencies:** FR-003.
**Maturity:** Emerging; the pin field and its validation exist, but `modeller-memory` and `modeller-pipelines` are not yet pinned to an immutable revision in the current repository state, per the brief's confirmed live findings.

**Acceptance criteria:**
- `vendors.toml`'s `pinned` field for a synced vendor is a commit-level identifier, not a branch name;
- `doctor --strict` rejects a vendor whose `pinned` value resolves to a mutable ref;
- the pinned revision matches what was actually synced via the printed `git subtree pull` command.

**Validation method:** `doctor --strict` test against a `vendors.toml` fixture using a branch name as `pinned`, expecting rejection.
**Related risks:** registered-but-untested backends (transitively, via unpinned contract schemas).
**Related architecture:** `vendors.toml`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 10. Security requirements (SEC)

Access scope and boundary confinement for the routing and gating layer, as scoped for the MVP.

### SEC-001 - No vendored-subtree hand edits

**Statement:** modeller-agents MUST NOT permit a hand edit to a vendored subtree under `vendor/`; a vendored subtree's content MUST originate only from a confirmed `git subtree pull` against the owning sibling repository.
**Rationale:** direct re-key of `AGENTS.md`'s forbidden-actions list; a hand-edited vendor copy breaks the traceability guarantee that a pinned revision actually matches what the owning repository published.
**Source:** Business Need §3 (product boundaries, "must not" list); AGENTS.md (Boundary section).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Current; the prohibition is documented and the vendor directories are read-only by convention today, but no automated enforcement (for example a pre-commit or CI check rejecting a diff under `vendor/` not produced by `sync`) has yet been confirmed to exist.

**Acceptance criteria:**
- no commit modifies a file under `vendor/` except through a recorded `sync` and subtree-pull operation;
- `vendors.toml`'s `writable = false` remains unchanged for every vendor entry;
- a reviewer can trace any change under `vendor/` back to a specific subtree-pull command and remote ref.

**Validation method:** CI check rejecting a diff under `vendor/` that does not correspond to a recorded subtree-pull; manual audit of `vendor/` history.
**Related risks:** knowledge duplication if a vendored copy silently diverges from its source (Business Need §2.2).
**Related architecture:** `vendor/`, `vendors.toml`.
**Related plan items:** None.
**Status:** Draft, to be validated

### SEC-002 - Boundary confinement against sibling repository content

**Statement:** modeller-agents MUST NOT copy `aimsun-psp` backend implementation, Testudo product or runtime logic, or `modeller-pipelines` pipeline schema definitions into this repository.
**Rationale:** direct re-key of `AGENTS.md`'s Boundary section; this is the mechanism that keeps each sibling repository the sole authority over its own domain, per the product's core promise.
**Source:** Business Need §3 (product boundaries, "must not" list); AGENTS.md (Boundary section).
**Priority:** P0.
**Dependencies:** BR-001.
**Maturity:** Operational; the boundary is documented and no violating content currently exists in the repository, confirmed by the brief's own repo inspection.

**Acceptance criteria:**
- no source file under this repository (outside `vendor/`) duplicates `aimsun-psp` backend implementation, Testudo UI/runtime code, or a `modeller-pipelines` schema definition;
- a schema needed from `modeller-pipelines` is referenced via the vendored copy or sibling fallback, never redefined locally;
- static inspection of the repository tree confirms no such duplication.

**Validation method:** periodic static inspection / CI check scanning for known sibling-repository file signatures outside `vendor/`.
**Related risks:** knowledge duplication (Business Need §2.2).
**Related architecture:** `docs/architecture/BOUNDARIES.md`.
**Related plan items:** None.
**Status:** Draft, to be validated

### SEC-003 - Human-review gate accepts only a human receipt

**Statement:** the workflow's human-review gate MUST accept only a receipt with `reviewer.actor_type: human`, and MUST NOT accept an AI-drafted artifact as satisfying that gate.
**Rationale:** direct re-key of Business Need §3 and §9.3; this is the mechanism that prevents an AI actor from self-approving work that requires human accountability.
**Source:** Business Need §3 (product boundaries, "must not" list), §5.3 (human reviewer's journey), §9.3 (prohibited actions), §13 (success measures).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Operational; the receipt-type check is built and exercised today as part of the workflow runtime's gate logic.

**Acceptance criteria:**
- a workflow attempting to close a human-review gate with a receipt whose `reviewer.actor_type` is not `human` is rejected;
- every accepted human-review receipt records the approving reviewer's identity;
- no code path lets an AI-drafted summary or recommendation stand in for the receipt itself.

**Validation method:** permission test submitting a non-human receipt to a human-review gate, expecting rejection.
**Related risks:** unproven done claims, if an AI-drafted receipt were silently accepted (Business Need §2.2).
**Related architecture:** workflow runtime, human-review gate logic.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 11. Non-functional requirements (NFR)

### NFR-001 - Fail-closed resolution

**Statement:** `route` and the strict-readiness gate SHOULD fail closed (return `ok: false` or a non-zero exit with reported blockers) whenever a bundle, skill, authorizing pack, or readiness precondition cannot be resolved, rather than proceeding on a best-guess default.
**Rationale:** direct re-key of Business Need §3 and §10; a routing or readiness layer that silently guesses undermines the boundary-check guarantee the product exists to provide.
**Source:** Business Need §3 (product boundaries), §10 (evidence, review and publication).
**Priority:** P0.
**Dependencies:** FR-006, FR-002.
**Maturity:** Operational; fail-closed behavior for `route` and strict readiness is built and exercised today.

**Acceptance criteria:**
- an unresolvable envelope never returns a partial or inferred bundle/skill/pack combination;
- a strict-readiness precondition that cannot be evaluated is reported as a blocker, not silently skipped;
- no code path substitutes a default value for a required, unresolved field.

**Validation method:** fault-injection test removing a required bundle or pack, expecting a fail-closed result rather than a fallback.
**Related risks:** unchecked boundary crossing (Business Need §2.2).
**Related architecture:** routing layer, strict-readiness gate.
**Related plan items:** None.
**Status:** Draft, to be validated

### NFR-002 - Scriptable, stable CLI output

**Statement:** the `modeller` CLI's `--json` output for `doctor`, `route`, and `workflow status` SHOULD remain stable in field names and shape across a minor release, usable by both a human operator and an orchestrating agent in a scriptable context.
**Rationale:** direct re-key of Business Need §11 (cross-cutting capabilities) and §14 (UI objective); an orchestrating agent parsing this output cannot tolerate silently shifting field names.
**Source:** Business Need §11 (cross-cutting MVP capabilities), §14 (UI objective), §15 (expected deliverables, item 3), §17 OPN-005.
**Priority:** P1.
**Dependencies:** FR-002.
**Maturity:** Emerging; the `--json` shape exists and is documented for `doctor --strict --json`, but whether any orchestrating agent or downstream product surface already depends on today's shape, such that a change would be breaking, is an open question (Business Need §17 OPN-005) not yet resolved.

**Acceptance criteria:**
- a documented `--json` schema exists for `doctor`, `route`, and `workflow status` output;
- a schema change within a minor version is additive only (new optional fields), not a rename or removal of an existing field;
- an orchestrating-agent integration test parses the documented schema without a version-specific workaround.

**Validation method:** schema-diff check between minor releases; integration test parsing live CLI output against the documented schema.
**Related risks:** none additional beyond general integration fragility.
**Related architecture:** `tools/` (`modeller` CLI).
**Related plan items:** None.
**Status:** Draft, to be validated

### NFR-003 - No governance envelope for unattended execution

**Statement:** modeller-agents MUST NOT enable background or scheduled execution by default; any such mode remains disabled until a named governance envelope for unattended execution is proposed and accepted.
**Rationale:** direct re-key of Business Need §12 (parking lot); unattended execution changes the risk profile of every gate in this document and must not be enabled by omission.
**Source:** Business Need §9.4 (risk-proportional control, "very high" row), §12 (parking lot).
**Priority:** P0.
**Dependencies:** None.
**Maturity:** Target, explicitly out of MVP scope; the blocking dependency is a named governance envelope for unattended execution, not yet proposed, per the brief's own parking-lot entry.

**Acceptance criteria:**
- no default configuration or CLI flag enables background or scheduled execution;
- any experimental scheduling code path, if present, is disabled by default and documented as unattended-execution-pending-governance;
- enabling such a mode requires an explicit, separately reviewed configuration change.

**Validation method:** default-configuration audit confirming no scheduled/background execution path is reachable without explicit opt-in.
**Related risks:** very-high risk-proportional control category (Business Need §9.4).
**Related architecture:** None yet; a future governance envelope would define this.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 12. Observability requirements (OBS)

### OBS-001 - Envelope-to-manifest traceability

**Statement:** the routing and workflow layer MUST provide coherent tracing of a governed envelope through `route`, the workflow run, and the closing `RunManifest`.
**Rationale:** direct re-key of Business Need §11 (cross-cutting MVP capabilities); without this, a maintainer or reviewer cannot reconstruct which envelope produced a given manifest.
**Source:** Business Need §11 (cross-cutting MVP capabilities), §7 (organization of a request).
**Priority:** P0.
**Dependencies:** DATA-001, DATA-002.
**Maturity:** Current; the identifying fields exist across the envelope, workflow, and manifest schemas, but end-to-end tracing has not yet been exercised against a completed real-backend run (see INT-003).

**Acceptance criteria:**
- the envelope's identity is present, unchanged, in the workflow run it produced;
- the workflow run's identity is present, unchanged, in the resulting `RunManifest`;
- a maintainer can, given only a `RunManifest`, locate the originating envelope.

**Validation method:** end-to-end trace test following one envelope through route, workflow, and manifest, asserting identity continuity at each step.
**Related risks:** unproven done claims (Business Need §2.2).
**Related architecture:** envelope, workflow, and `RunManifest` schemas.
**Related plan items:** None.
**Status:** Draft, to be validated

### OBS-002 - Calculated result distinguished from interpretation and decision

**Statement:** the routing and workflow layer MUST distinguish, in its output, a calculated readiness result (`readiness_blockers[]`), a routed proposal (`route`'s resolved bundle/skill), and a human reviewer's recorded decision, never presenting one as if it were another.
**Rationale:** direct re-key of Business Need §9.5 (output types) and §9.3 (prohibited actions); conflating a calculated result with an interpretation or a decision would erode the evidence-before-done guarantee.
**Source:** Business Need §9.3 (prohibited actions), §9.5 (output types), §10 (evidence, review and publication).
**Priority:** P0.
**Dependencies:** OBS-001.
**Maturity:** Current; the output types are structurally distinct in the schemas today, but no dedicated cross-cutting test confirms a consumer cannot mistake one for another in every surfaced view.

**Acceptance criteria:**
- `readiness_blockers[]` output is never labeled or rendered as a human decision;
- a routed proposal from `route` is visibly distinct from an executed backend result;
- a human reviewer's recorded decision carries its own receipt type, distinct from any AI-produced summary.

**Validation method:** output-shape test asserting distinct type markers across the three output categories.
**Related risks:** unproven done claims (Business Need §2.2).
**Related architecture:** CLI output formatting, schemas under `schemas/`.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 13. Human-in-the-loop requirements (HITL)

### HITL-001 - Explicit consent for medium and high risk execution

**Statement:** modeller-agents MUST require a declared consent state on the envelope before executing medium or high risk work, and MUST check that state before the action proceeds, as declared by the envelope's risk level.
**Rationale:** direct re-key of Business Need §3, §6.4, and §9.4; this is the mechanism that keeps a backend invocation or a workflow-advancing action from proceeding on an AI actor's own judgement alone. The Business Need's original risk-proportional control table described medium/high risk control in terms suggesting a live preview and in-the-moment confirmation; that framing was corrected in Business Need §9.4 and is not what this requirement claims: today's consent check is a pre-declared field checked before the action runs, not a live prompt the user acts on while the action is in flight. The live version is HITL-004, a separate Target requirement.
**Source:** Business Need §3 (product boundaries), §6.4 (oversee execution), §9.4 (risk-proportional control table).
**Priority:** P0.
**Dependencies:** DATA-001.
**Maturity:** Current; the risk-level field and consent-check mechanism exist in the envelope and workflow schemas and are checked before execution, but the check has not yet been exercised against a real medium/high risk backend invocation (see INT-003, the one high-risk action named in Business Need §9.4 not yet proven end to end).

**Acceptance criteria:**
- an envelope's declared consent state is checked before a medium-risk workflow step advances, and the artifact evidence it consumed remains inspectable via CLI output before and after the step;
- a high-risk action (backend invocation, human-review gate approval) does not proceed without a declared, checked consent state on the envelope;
- no medium or high risk action executes on a declared-but-unconfirmed consent state.

**Validation method:** permission test attempting a high-risk action with consent withheld, expecting rejection.
**Related risks:** unchecked boundary crossing (Business Need §2.2).
**Related architecture:** envelope schema (risk/consent fields), workflow gate logic.
**Related plan items:** None.
**Status:** Draft, to be validated

### HITL-002 - Human reviewer can retrieve and correct the determining context before a gate decision

**Statement:** the ecosystem maintainer or human reviewer MUST be able to retrieve, via CLI output, the envelope's declared intent, target, domains, risk, and consent state, and the resolved bundle/skill/pack context, before recording an important gate decision, and MUST be able to correct an incorrect declared field by re-issuing a corrected envelope before the gate is decided.
**Rationale:** direct re-key of Business Need §9.1; a reviewer who cannot retrieve or correct the determining context cannot meaningfully exercise the review authority this product depends on. This is a CLI retrieval-and-reissue capability, not a live, interactive review surface the reviewer watches or acts on while a step is in flight; that live surface is HITL-004, a separate Target requirement.
**Source:** Business Need §9.1 (context understood by the agent), §5.3 (human reviewer's journey).
**Priority:** P0.
**Dependencies:** DATA-001.
**Maturity:** Current; the underlying fields are all inspectable via CLI output today, and correction happens by re-issuing a corrected envelope; no dedicated interactive review-and-correct surface exists beyond this.

**Acceptance criteria:**
- before a human-review gate decision, the reviewer can retrieve the full envelope context and the resolved route via CLI output;
- a reviewer identifying an incorrect declared field can correct it by re-issuing a corrected envelope before the gate is decided;
- the gate decision, once recorded, references the exact context version the reviewer saw.

**Validation method:** review-flow test confirming the context shown to a reviewer matches the context referenced in the resulting gate receipt.
**Related risks:** unproven done claims, unchecked boundary crossing (Business Need §2.2).
**Related architecture:** envelope schema, workflow gate logic.
**Related plan items:** None.
**Status:** Draft, to be validated

### HITL-003 - Sibling maintainer confirmation before pin or smoke is final

**Statement:** a vendor pin or a backend smoke's manifest confirmation SHOULD be confirmed by the owning sibling repository's maintainer before being treated as final remediation evidence.
**Rationale:** direct re-key of Business Need §4 (project responsibilities) and §5.4 (sibling maintainer's journey); the vendor's or backend's own maintainer is best placed to confirm the remote, ref, and pipeline id are correct.
**Source:** Business Need §4 (project responsibilities table), §5.4 (sibling repository maintainer's journey).
**Priority:** P1.
**Dependencies:** FR-003, INT-002.
**Maturity:** Emerging; the journey describes a confirmation step, but no CLI or workflow mechanism yet formally records a sibling maintainer's confirmation as distinct from the ecosystem maintainer's own action.

**Acceptance criteria:**
- a vendor sync's remote and ref, and a backend smoke's manifest and pipeline id, are confirmed with the owning sibling maintainer before being marked final;
- the confirmation is recorded in a form the ecosystem maintainer or a reviewer can later check;
- a pin or smoke marked final without a recorded sibling confirmation is flagged, not silently accepted.

**Validation method:** process audit of a remediation pass, confirming a recorded sibling-maintainer confirmation exists.
**Related risks:** knowledge duplication, registered-but-untested backends (Business Need §2.2).
**Related architecture:** None yet formalized; currently a process step, not a code mechanism.
**Related plan items:** None.
**Status:** Draft, to be validated

### HITL-004 - Live, user-in-control routing and approval surface (target)

**Statement:** modeller-agents SHOULD provide a live control-plane, in the spirit of a model/provider router, through which a user watches which method a governed request is routed to, can steer that routing choice, and can approve or reject a workflow step or backend invocation while it is in flight.
**Rationale:** direct re-key of Business Need §1 (executive summary), §2.2 (risk 5), and §3 (product vision and boundaries, "user-in-control control-plane" note); this is the capability gap this correction pass exists to name honestly. Nothing in the current codebase provides live routing visibility, in-flight steering, or an in-flight approve/reject action: HITL-001's consent check and SEC-003's human-review gate are both pre-declared-state checks evaluated before or after an action runs, not a live surface a user watches or acts on while the action is in flight. This requirement is a distinct, materially larger target than closing the existing strict-readiness blockers (INT-003, TEST-001) and is explicitly out of the current MVP boundary (Business Need §3).
**Source:** Business Need §1 (executive summary), §2.2 (current risks, risk 5), §2.3 (opportunity, closing note), §3 (product vision and product boundaries), §9.4 (risk-proportional control table, target column).
**Priority:** P2.
**Dependencies:** FR-006, FR-007, INT-001, HITL-001.
**Maturity:** Target; no live control-plane exists in the codebase today. The blocking dependency is a separate, dedicated design and delivery effort scoped on its own terms, per Business Need §3's note that this "would need its own brief scoped separately." It is not unblocked by closing INT-003 or TEST-001, which prove the existing skills-only seam, not this capability.

**Acceptance criteria:**
- a user can observe, while a governed request is routing, which bundle, skill, and backend method it is being resolved to, before routing completes;
- a user can steer or override a routing choice before it is acted on, without re-issuing a new envelope from scratch;
- a user can approve or reject a workflow step or backend invocation while it is in flight, distinct from and in addition to the existing post-hoc receipt-shape check;
- the existing post-hoc artifact and receipt checks (BR-003, SEC-003, HITL-001, HITL-002) continue to function unchanged; this capability adds a live surface on top of them, it does not replace them.

**Validation method:** no validation method applies yet; this requirement is Target and unimplemented. A future validation method would require an end-to-end interactive test driving a live routing/approval session, not a CLI-only test.
**Related risks:** no live user-in-control surface (Business Need §2.2, risk 5).
**Related architecture:** None yet; a future control-plane component would need its own architecture entry.
**Related plan items:** None.
**Status:** Draft, to be validated

---

## 14. Verification requirements (TEST)

### TEST-001 - Strict-readiness blocker list reaches zero

**Statement:** the test/verification process MUST demonstrate `doctor --strict --json` exiting `0` with an empty `readiness_blockers[]` array against the repository's own configuration, as the MVP's definition of done.
**Rationale:** this is the exact, named acceptance condition in Business Need §1 and §18; every other requirement in this document either feeds this outcome or is a boundary condition around it.
**Source:** Business Need §1 (executive summary), §13 (success measures), §18 (consolidated statement of need).
**Priority:** P0.
**Dependencies:** FR-003, FR-004, FR-005, INT-003.
**Maturity:** Target; the check itself (`doctor --strict --json`) runs today and currently reports a non-empty `readiness_blockers[]` array across the six blocker codes in 10 concrete instances, per the brief's own confirmed live findings. The blocking dependency is completing FR-003 through FR-005 and INT-003.

**Acceptance criteria:**
- `doctor --strict --json` exits with code `0`;
- the `readiness_blockers[]` array is empty;
- the result is reproducible on a clean checkout following the documented remediation steps.

**Validation method:** `python -m modeller.cli doctor --root . --strict --json`, run from a clean checkout after applying the documented remediation.
**Related risks:** all four risks named in Business Need §2.2, since this is the composite proof they are closed.
**Related architecture:** `tools/` (`modeller` CLI), `docs/readiness/STRICT_READINESS.md`.
**Related plan items:** None.
**Status:** Draft, to be validated

### TEST-002 - Boundary and consent behavior coverage

**Statement:** the test suite MUST verify that `route` fails closed on an unresolvable envelope, that a non-human receipt is rejected by a human-review gate, and that no medium/high risk action executes without recorded consent.
**Rationale:** direct verification of BR-001, SEC-003, and HITL-001, the product's core containment guarantees.
**Source:** Business Need §3 (product boundaries), §9.3 (prohibited actions), §9.4 (risk-proportional control).
**Priority:** P0.
**Dependencies:** FR-006, SEC-003, HITL-001.
**Maturity:** Operational; this class of test exists today as part of the 156-test suite the business need cites, though the specific three assertions above have not been individually confirmed present by name in this pass.

**Acceptance criteria:**
- a test asserting `route` fail-closed behavior exists and passes;
- a test asserting human-review-gate receipt-type rejection exists and passes;
- a test asserting consent is required before medium/high risk execution exists and passes.

**Validation method:** targeted test-suite run against the three named assertions.
**Related risks:** unchecked boundary crossing, unproven done claims (Business Need §2.2).
**Related architecture:** routing layer, workflow gate logic.
**Related plan items:** None.
**Status:** Draft, to be validated

### TEST-003 - Real backend smoke evidence verification

**Statement:** the verification process MUST confirm, by direct inspection, that a `result.json` produced by the `aimsun-psp` smoke was generated by an actual subprocess invocation of the declared `runner.command`, not by a fixture or a mocked backend.
**Rationale:** direct re-key of Business Need §13's success measure; the MVP's promise depends on the smoke being real, and this is explicitly the one thing this repository's own record does not yet demonstrate.
**Source:** Business Need §13 (success measures, second row), §17 OPN-002.
**Priority:** P0.
**Dependencies:** INT-003.
**Maturity:** Target; cannot be Current or Operational until INT-003 itself passes. Blocked on the same dependency: vendor pin and schema completion, plus independent confirmation from `aimsun-psp` maintainers that their side of the seam is ready to receive the call.

**Acceptance criteria:**
- the smoke's process invocation is logged with its exact command line, matching the backend's declared `runner.command`;
- `result.json`'s content is traceable to that specific process run, not a checked-in fixture;
- a reviewer can independently re-run the same command and reproduce an equivalent result.

**Validation method:** manual reviewer re-run of the documented smoke command, comparing the reproduced `result.json` against the recorded one.
**Related risks:** registered-but-untested backends (Business Need §2.2), the risk this test exists to close.
**Related architecture:** `aimsun-psp` `backend.json`, `runner.command`.
**Related plan items:** None.
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

Each P0 requirement above links to a section of `Business-need-design-brief.md`, the responsible actor from §4, and, where the codebase already provides one, a named architecture component. "Delivery batch" is not yet defined for this repository: no delivery-plan document exists alongside this PRD, so P0 requirements above list "None" for that field until one is produced. A risk is named for every requirement that traces to one of the four risks in Business Need §2.2; a requirement without a named risk states so explicitly rather than leaving the field blank.

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

Out of the normative scope of this version, per Business Need §12 (parking lot):

- knowledge-axis reactivation (domain reference packs referencing vault notes), blocked on `modelling-knowledge` decision 0010 acceptance at general scope and a DR-1 attribution-protocol cure;
- background or scheduled execution mode, pending a named, accepted governance envelope for unattended execution;
- a full Testudo-to-backend service loop beyond the single `aimsun-psp` smoke;
- automatic publication without review; no client-facing publication step exists in this repository at all;
- silent modification of vendored subtrees or backend implementation, which remains prohibited without a reconsideration path.

---

## 19. Blocking open decisions

| ID | Decision | Affected requirements |
|---|---|---|
| OQ-001 | Has `Vision.md` itself been reviewed and accepted by the ecosystem maintainers it names as its audience? | All requirements tracing to `Vision.md` sections, notably BR-002, NFR-003 |
| OQ-002 | Which `aimsun-psp` pipeline id is confirmed as the Aimsun-free smoke pipeline, and has `aimsun-psp`'s own side of the seam (its `backend.json`, its own readiness) been independently confirmed ready to receive the call? | INT-003, TEST-001, TEST-003 |
| OQ-003 | Who confirms the remote and ref for the `modeller-memory` and `modeller-pipelines` vendor syncs, and on what cadence should the pin be refreshed afterward? | FR-003, DATA-003, HITL-003 |
| OQ-004 | What is the reconsideration path and owner for `modelling-knowledge` decision 0010 and the DR-1 attribution-protocol cure that currently block knowledge-axis reactivation? | None in this version's normative scope; tracked because it gates §18's first exclusion |
| OQ-005 | Does any orchestrating agent or downstream product surface already depend on the current `--json` output shape of `doctor`, `route`, or `workflow status`, such that changing it during this MVP would be a breaking change? | NFR-002 |

---

## 20. Requirement family summary

| Family | Count | ID range |
|---|---|---|
| BR (Business requirements) | 3 | BR-001 to BR-003 |
| FR (Functional requirements) | 7 | FR-001 to FR-007 |
| INT (Integration requirements) | 3 | INT-001 to INT-003 |
| DATA (Data requirements) | 3 | DATA-001 to DATA-003 |
| SEC (Security requirements) | 3 | SEC-001 to SEC-003 |
| NFR (Non-functional requirements) | 3 | NFR-001 to NFR-003 |
| OBS (Observability requirements) | 2 | OBS-001 to OBS-002 |
| HITL (Human-in-the-loop requirements) | 4 | HITL-001 to HITL-004 |
| TEST (Verification requirements) | 3 | TEST-001 to TEST-003 |
| **Total** | **31** | |
