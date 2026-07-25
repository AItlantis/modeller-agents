# modeller-agents: Business Need and Design Brief

**Recipients:** modeller-agents maintainers, sibling-repo maintainers (aimsun-psp, modeller-pipelines, modeller-memory, modelling-knowledge), ecosystem architecture owner
**Nature:** product vision, business framing, MVP scope and design mandate
**Status:** draft for alignment
**Version:** 0.1, 25 July 2026
**Product:** modeller-agents, composition and orchestration root
**Upstream document:** docs/vision/Vision.md (status: draft strategic reflection, not yet reviewed or accepted)
**Downstream document:** docs/vision/Product-requirements-document.md

> This document sets out the business problem, the product vision, the users, the MVP journeys, the role of the contextual AI, the product's boundaries, and the decisions needed for design.
> It does not replace `Product-requirements-document.md`, which carries the testable obligations, detailed rules, acceptance criteria, and non-functional requirements.

**Note on upstream status:** `Vision.md` is itself dated today, versioned 0.1, and self-labelled "draft strategic reflection and discussion document." It has not yet been reviewed or accepted by the ecosystem maintainers it names as its audience. This brief traces to that draft in good faith, because it is the only strategic direction the repository currently has, but any commitment built on this brief inherits that open status. Acceptance of `Vision.md` is a precondition this brief does not resolve.

---

## 1. Executive summary

modeller-agents is a composition and orchestration root for the modelling ecosystem. Its goal is to let a governed request from an orchestrating agent or an ecosystem maintainer reach the right method, in the right repository, under an explicit gate, and to leave behind artifact evidence that proves what happened.

It lets an orchestrating agent route a context envelope to a bundle, a skill, and the reference packs that authorize that skill, drive a deterministic, artifact-gated workflow through named roles, and invoke a registered backend only through its declared contract seam. A **single, visible contextual AI agent framing** applies here in a specific sense: modeller-agents itself has no end-user chat surface, but every request it routes carries exactly one accountable orchestrating agent identity through the envelope, workflow, and manifest, never a fragmented set of untraceable actors. It understands the project's authorized context: the envelope's declared intent, target repository, domains, risk level, and consent state. It can prepare a route, structure a workflow, and invoke an authorized backend, while leaving source-boundary checks, consent, and human-review checks in control of what actually executes. Today this happens through a set of skills invoked one at a time, plus CLI tooling that validates artifact and receipt shape after the fact, including a check that a workflow-closing receipt names a `reviewer.actor_type: human`; there is no live surface yet where a user watches a request route in real time, steers which method handles it, or approves an in-flight step. That user-in-control control-plane is a separate, named target, not yet built; Section 3 scopes it out of the MVP boundary and every later reference to it in this document is a cross-reference back to this paragraph and to Section 3, not a restatement.

modeller-agents is not meant to replace the domain judgement of the repositories it composes. `modelling-knowledge` remains the authority for accepted knowledge content, `modeller-memory` remains the authority for generated memory, `aimsun-psp` remains the authority for backend implementation, and `modeller-pipelines` remains the authority for pipeline result contracts. modeller-agents connects these; it does not absorb them.

> **Product promise: a governed request reaches the right method, in the right repository, under an explicit gate, and leaves behind artifact evidence that proves what happened, without modeller-agents becoming a second authority over the domains it routes to.**

The MVP succeeds when an ecosystem maintainer can run `doctor --strict --json` against the repository's own already-registered `aimsun-psp` backend and see an empty `readiness_blockers` array, and when a human reviewer can confirm, from the resulting artifacts, that a real backend smoke actually executed rather than being asserted.

---

## 2. Business problem and opportunity

### 2.1 Current situation

Today, routing, skills, gates, and the deterministic workflow runtime are built and exercised in this repository: 156 of 156 tests pass, and the mechanisms this brief describes are not proposals, they are running code. What is not yet proven is the complete, end-to-end path from a governed request through a registered backend to a validated result. An ecosystem maintainer or orchestrating agent who wants to rely on modeller-agents today must regularly check:

- whether a bundle-selected reference pack is `active` or still `draft`, since a draft pack can pass local advisory doctor but must not back a release;
- whether `modeller-memory` and `modeller-pipelines`, vendored into this repository, are pinned to an immutable revision or still sitting at `status = "planned"`;
- whether contract schema resolution is coming from the vendored copy under `vendor/modeller-pipelines/contracts/schemas` or silently falling back to a sibling checkout;
- whether the one backend currently registered in `backends.toml`, `aimsun-psp`, has ever actually been invoked through its declared runner and produced a schema-valid `result.json`, or whether `status = "planned"` is standing in for a claim that has never been exercised.

A significant share of confidence in this layer currently rests on knowing the mechanism exists, rather than on evidence that the full seam has been proven end to end against real, already-registered work.

### 2.2 Current risks

This gap between built mechanism and proven seam creates five main risks, each named directly in `Vision.md` Section 2:

1. **Unchecked boundary crossing**: a write, backend call, or knowledge promotion could target a repository that does not own the outcome, without a boundary check catching it before it happens.
2. **Unproven done claims**: a subagent can report a task as finished with no artifact that proves the required evidence, decisions, or verification actually exist, and nothing in the surrounding process would catch it.
3. **Knowledge duplication**: a reference pack could quietly duplicate knowledge content instead of pointing to the vault's authority by ID, eroding the single-source-of-truth guarantee the ecosystem depends on.
4. **Registered-but-untested backends**: a backend can be treated as ready because it is registered in `backends.toml`, without a real invocation ever proving the contract seam actually works end to end.
5. **No live user-in-control surface**: as scoped in Section 1's executive summary, today's routing and gating discipline lives inside skill invocations and post-hoc artifact checks, with no live surface for a user to watch or steer a request in flight.

> **Fundamental problem: the ecosystem has a routing and gating mechanism that is genuinely built and tested in isolation, but has not yet closed its own documented readiness gaps on the one real backend it already claims to support, so its central promise, evidence before "done," is not yet demonstrated on real work. Separately, and on a larger scale, the ecosystem has no live, user-in-control control-plane at all (risk 5 above).**

### 2.3 Opportunity with modeller-agents

The opportunity is not to build new orchestration capability. It is to close the repository's own already-documented strict-readiness blocker list against the backend it has already registered, so the seam this vision describes is proven rather than asserted.

| Today | With modeller-agents closing its own readiness gaps |
|---|---|
| Bundle-selected reference packs are `draft`; strict readiness blocks release on `reference-pack-not-active` | Every bundle-referenced pack is `active`, and strict readiness no longer reports this blocker |
| `modeller-memory` and `modeller-pipelines` are vendored as `planned`, unpinned entries | Both vendors are synced and pinned to an immutable revision, remediating `vendor-not-synced` and `vendor-not-pinned` |
| Contract schemas resolve through sibling fallback to `AItlantis\modeller-pipelines`, not the vendored copy | Schemas resolve from `vendor/modeller-pipelines/contracts/schemas`, remediating `schema-sibling-fallback` |
| `aimsun-psp` is registered in `backends.toml` with `status = "planned"` and no proven smoke | A real backend smoke through the declared `runner.command` has executed, produced a schema-valid `result.json`, and the backend is marked `active`, remediating `backend-not-active` and `backend-contract-unpinned` |
| `doctor --strict --json` currently reports a non-empty `readiness_blockers[]` array across the six documented blocker codes | `doctor --strict --json` exits `0` with an empty `readiness_blockers[]` array |

This table describes one bounded opportunity: closing the existing skills-only seam's own documented readiness gaps. The live, user-in-control control-plane named in Section 1 and Section 2.2 is a second, separate and materially larger opportunity, not part of this table and not proposed as MVP scope; Section 3 scopes it out of the product boundaries.

---

## 3. Product vision and product boundaries

modeller-agents becomes the ecosystem's proven composition and orchestration seam: not a new platform, but the disciplined connective layer that lets every other repository's existing capability be reached through one governed, evidenced path instead of ad hoc scripts or one-off prompts.

The contextual AI agent identity carried through an envelope is the connective layer of this experience. It replaces neither `testudo`'s product surface, nor `aimsun-psp`'s backend execution, nor `modelling-knowledge`'s authority over accepted content. It helps an orchestrating agent understand the authorized context of a request, route it to the correct bundle and skill, structure it into a gated workflow, invoke an authorized backend, and leave behind evidence a human reviewer can check.

**User-in-control control-plane (target, not yet built).** The MVP boundaries below scope the skills-and-CLI-checks reality described in Section 1: routing, workflow, and backend invocation happen one skill at a time, and a human-review gate is a post-hoc shape check on a receipt, not a live approval. The live control-plane named there is a distinct and materially larger target, excluded from the boundaries below, and would need its own brief scoped separately.

### Product boundaries

For the MVP, modeller-agents:

- routes a governed context envelope to a bundle, a skill, and the reference packs that authorize that skill, failing closed when any of the three cannot be resolved;
- runs a deterministic, artifact-gated workflow (`init` / `status` / `check` / `advance`) through named roles, each requiring specific artifact evidence before the next step opens;
- invokes a registered backend only through its declared contract seam (`backends.toml` to `backend.json` to `runner.command`), never by importing the backend's implementation;
- distinguishes advisory local `doctor` health from release-grade `doctor --strict`, so an operator can see exactly which blockers separate the current state from a release-ready one.

In the MVP, modeller-agents must not:

- move a repository-local agent into this repository, per `AGENTS.md`'s explicit boundary;
- copy `aimsun-psp` backend implementation, or copy Testudo product UI or runtime logic;
- define pipeline schemas, which remain owned by `modeller-pipelines`;
- store a generated memory index as authority, or accept an AI-drafted artifact as satisfying a human-review gate; the workflow's human-review gate accepts only a receipt with `reviewer.actor_type: human`, checked as a static, post-hoc field per Section 1 and the paragraph above, not a live approval;
- present the live, user-in-control control-plane described above as if it exists; it is out of MVP scope.

---

## 4. Users, responsibilities and access

The MVP is designed first for the **ecosystem maintainer**, who runs readiness checks, remediates blockers, and decides when a backend or reference pack is release-ready. The **orchestrating agent** is the primary machine actor issuing governed context envelopes and consuming route and workflow output; a **human reviewer** confirms risk, consent, and gate outcomes wherever the workflow calls for one. Sibling repository maintainers (aimsun-psp, modeller-pipelines, modeller-memory, modelling-knowledge) are consulted whenever a change touches their vendored content, registered backend, or authority. The matrix below is a working basis for design; it will need to be confirmed in the product requirements document.

| User | Main goal | Can do in the MVP | Cannot do by default | Authority or approval |
|---|---|---|---|---|
| **Ecosystem maintainer** | Close the repository's own strict-readiness blocker list | Run `doctor` / `doctor --strict`, promote a reference pack, pin a vendor, register a backend smoke | Mark strict readiness passing without the underlying blocker actually remediated | Confirms remediation evidence before calling a blocker closed |
| **Orchestrating agent** | Issue a governed context envelope and consume routed output | Call `route`, `workflow init/status/check/advance`, invoke a registered backend through the declared seam | Widen its own access beyond what the envelope declares; execute medium or high risk work without consent | Bound by the envelope's own declared permissions and consent state |
| **Human reviewer** | Confirm risk, consent, and gate outcomes | Approve or reject a human-review gate; approve medium or high risk execution | Approve on behalf of an AI-drafted receipt; the workflow only accepts `reviewer.actor_type: human` | Sole authority for human-review gates |
| **Sibling repository maintainer** | Protect their own repository's authority over its domain | Confirm a vendor sync's remote and ref; confirm a backend's manifest and pipeline id for a smoke | Have their repository's content copied into modeller-agents instead of referenced or invoked | Owns the content modeller-agents references or invokes; not overridden |

### Project responsibilities

| Project responsibility | Expected role |
|---|---|
| **Strict-readiness blocker remediation** | Ecosystem maintainer, evidenced by a re-run `doctor --strict --json` |
| **Envelope routing and workflow progression** | Orchestrating agent, within its own declared permissions and consent |
| **Human-review and consent gates** | Human reviewer, the only actor type the workflow accepts for a human gate |
| **Vendor and backend authority confirmation** | The owning sibling repository's maintainer, consulted before a pin or a smoke is treated as final |

---

## 5. MVP user journeys

### 5.1 Ecosystem maintainer's main journey

1. Run `python -m modeller.cli doctor --root . --strict --json` and read the current `readiness_blockers[]` array.
2. For each `vendor-not-synced` or `vendor-not-pinned` blocker, run `sync` for `modeller-memory` and `modeller-pipelines`, confirm the printed `git subtree pull` command with the owning repository's maintainer, execute it, and update `vendors.toml` with the immutable synced revision.
3. For each `reference-pack-not-active` blocker, confirm the bundle-referenced pack's shape and any draft-only open decisions are closed or explicitly moved out of release scope, then promote the pack's `status` to `active`.
4. For the `schema-sibling-fallback` blocker, confirm `vendor/modeller-pipelines/contracts/schemas` contains the required schema files and that `vendors.toml` pins `modeller-pipelines` to the revision that supplied them.
5. Confirm the `aimsun-psp` backend manifest with `python -m modeller.cli backends --root . --check aimsun-psp`.
6. Run one real backend smoke with `python -m modeller.cli run --root . aimsun-psp <pipeline-id> --config <config> --run-dir <dir> --backend-root <path>`, and confirm the process exits `0`, the final stdout line is the path to `result.json`, and `result.json` validates against the vendored `result.schema.json`.
7. Mark the `aimsun-psp` backend `active` in `backends.toml` once the smoke evidence exists.
8. Re-run `doctor --strict --json` and confirm `readiness_blockers[]` is empty.

### 5.2 Orchestrating agent's journey

1. Issue a governed context envelope stating intent, target repository, domains, risk, and consent state.
2. Call `route` and receive either a resolved bundle, skill, and authorizing reference packs, or an `ok: false` result when any of the three cannot be resolved.
3. Drive `workflow init/status/check/advance` through the named roles the workflow requires, supplying the artifact evidence each gate needs before the next step opens.

### 5.3 Human reviewer's journey

1. Receive a routed request that requires a human-review gate or a medium/high risk consent decision.
2. Review the envelope's declared context, the workflow's artifact evidence, and the backend invocation's manifest and result, alongside the risk level attached.
3. Approve or reject the gate, recorded as a receipt with `reviewer.actor_type: human`; the workflow does not accept an AI-drafted substitute.

### 5.4 Sibling repository maintainer's journey

1. Confirm, when asked, the correct remote and ref for a vendor sync of their own repository's content into modeller-agents.
2. Confirm, for `aimsun-psp`, the backend manifest's `contract_version` and the pipeline id to be used for the smoke.
3. Review the resulting `RunManifest` evidence, referenced by path and SHA-256 digest, to confirm their repository's authority was invoked through the declared seam and not copied or bypassed.

The MVP must demonstrate the continuity of these journeys: a blocker the maintainer remediates should be visibly reflected in the next `doctor --strict` run, a route the orchestrating agent issues should be traceable through the workflow to the human reviewer's decision, and a backend smoke should produce evidence the sibling maintainer can independently check.

---

## 6. How modeller-agents supports the work

**6.1 Understand and clarify the need.** A governed context envelope makes intent, target repository, domains, risk, and consent state explicit before anything routes. `route` fails closed rather than guessing when a bundle, skill, or authorizing pack cannot be resolved.

**6.2 Build the appropriate workflow.** `workflow init` turns a routed objective into a sequence of gated steps, each owned by a named role (orchestrator, planner, architect, executor, documenter), each requiring specific artifacts before the next step opens.

**6.3 Mobilize technical capabilities.** Routing selects reusable skills and reference packs instead of hardcoding repository knowledge into every caller. The backend seam calls a registered backend's declared `runner.command` through `backends.toml` and `backend.json`, never by importing its implementation.

**6.4 Oversee execution.** Medium and high risk work requires explicit consent before execution. Backend invocation goes through a manifest contract check and result-schema validation, so what is running and what it depends on stays visible.

**6.5 Support the analysis.** `doctor` and `readiness` distinguish advisory local health from release-grade strict readiness, so an operator can see exactly which blockers (draft packs, unpinned vendors, sibling schema fallback, unproven backend smoke) separate the current state from a release-ready one. It explicitly distinguishes a calculated readiness result from any interpretation of it.

**6.6 Facilitate the review.** `workflow manifest` and `workflow close` produce a `RunManifest` that references workflow state, artifacts, gates, and subagent lane receipts by path and SHA-256 digest, so a human reviewer checks addressable evidence rather than a claim.

**6.7 Prepare the publication.** modeller-agents has no client-facing publication step in the MVP. What it does prepare is a `RunManifest` for the orchestrating agent or a downstream product surface to consume; nothing in this repository publishes to an external party without that consuming surface's own review step.

**6.8 Preserve useful project elements.** A workflow's `memory` and `decisions` artifact families exist specifically so a proposed observation becomes durable only through the classification and review path owned by `modeller-memory` and `modelling-knowledge`, never by modeller-agents writing directly into either authority. An unreviewed AI hypothesis does not automatically become accepted project knowledge.

---

## 7. Organization of a modeller-agents request

A governed context envelope represents one routed unit of work and constitutes the central unit this repository composes around. It contains at minimum:

- a declared intent and target repository;
- declared domains and a declared risk level;
- a declared consent state;
- a resolved bundle, skill, and authorizing reference packs, once `route` succeeds;
- a workflow run, once `workflow init` starts one;
- a `RunManifest`, once the workflow closes.

### Core relationships

- **Bundle**: a manifest that selects the skill and the reference packs authorized to back it for a given routing key.
- **Reference pack**: repository-specific constraints and authorizing metadata, carrying note IDs and routing metadata for knowledge packs, never note bodies, thresholds, or decision text.
- **Workflow run**: a sequence of gated steps, each owned by a named role, each requiring specific artifact evidence before the next step opens.
- **Backend registration**: `backends.toml`'s entry for a backend, its `expected_contract`, and its `status`, resolved against that backend's own `backend.json` and declared `runner.command`.
- **RunManifest**: the closing artifact that references workflow state, artifacts, gates, and subagent lane receipts by path and SHA-256 digest.

The active context must always let the user understand which envelope, which routed bundle and skill, and which workflow run they are working on.

---

## 8. Need-to-result cycle

1. **Express the objective.** An orchestrating agent issues a governed context envelope stating intent, target, risk, and consent.
2. **Structure the workflow.** `route` resolves the envelope to a bundle, skill, and authorizing reference packs; `workflow init` turns the result into a sequence of gated steps.
3. **Confirm the action.** Medium and high risk work requires explicit consent before execution; a human-review gate requires a `reviewer.actor_type: human` receipt.
4. **Execute and oversee.** A registered backend is invoked only through its declared contract seam; the workflow tracks artifact evidence at each gate.
5. **Analyze and review.** `doctor` and `readiness` distinguish advisory health from release-grade strict readiness. The user distinguishes a calculated readiness result, an interpretation of it, and a human decision about it.
6. **Validate and publish.** `workflow manifest` and `workflow close` produce a `RunManifest` referencing evidence by path and digest, for the consuming orchestrating agent or human reviewer to check.

This cycle replaces ad hoc scripts and one-off prompts with a continuity of routed context and gated control.

---

## 9. The contextual AI agent

An orchestrating agent interacts with modeller-agents as **a single accountable identity per envelope**. modeller-agents itself presents no end-user chat surface; the single-agent framing here means every routed request, workflow run, and backend invocation carries one traceable orchestrating-agent identity through to the `RunManifest`, never a set of untraceable or interchangeable actors.

### 9.1 Context understood by the agent

The routing and workflow layer uses only the envelope's own authorized and relevant context:

- the envelope's declared intent and target repository;
- the envelope's declared domains and risk level;
- the envelope's declared consent state;
- the resolved bundle, skill, and authorizing reference packs;
- the artifact evidence accumulated in the current workflow run.

The ecosystem maintainer or human reviewer must be able to see and correct the determining elements of this context before an important gate decision.

### 9.2 Actions supported in the MVP

The routing and workflow layer can: resolve a governed envelope to a bundle, skill, and authorizing reference packs; initialize, check, and advance a deterministic workflow; request consent for medium or high risk work; invoke a registered backend through its declared contract seam; validate a backend's `result.json` against the vendored result schema; produce a `RunManifest` referencing evidence by path and digest.

### 9.3 Prohibited or tightly controlled actions

The routing and workflow layer cannot:

- silently widen a request's access beyond what the envelope declared;
- execute medium or high risk work without explicit consent;
- accept an AI-drafted artifact as satisfying a human-review gate;
- present a `doctor` interpretation as the calculated readiness result itself;
- import another repository's backend, product, or schema implementation instead of invoking or referencing it;
- write a generated memory index, or knowledge-pack content beyond note IDs and routing metadata, as if it were authoritative.

### 9.4 Risk-proportional control

| Level | Examples | Expected control today | Target control (not yet built) |
|---|---|---|---|
| **Low** | Reading `doctor` output; querying `route` for a resolvable envelope | Direct, visible, and reversible action | No change needed |
| **Medium** | Advancing a workflow step that consumes prepared artifact evidence | Declared consent checked before the step executes; evidence inspectable via CLI before and after `advance` (Section 1) | A live preview and correction before the gate opens, in flight |
| **High** | Invoking a registered backend; approving a workflow's human-review gate | Declared consent checked before execution; the review gate is the post-hoc receipt-shape check per Section 1, not a live approval | A live summary and in-the-moment confirmation acted on while the call or gate is in flight |
| **Very high** | Reactivating the knowledge axis; enabling background or scheduled execution | Out of MVP scope; gated on external decisions this repository does not control | Same; also depends on the control-plane target above |

### 9.5 Output types

The routing and workflow output must clearly distinguish: a calculated readiness result (`doctor --strict --json`'s `readiness_blockers[]`), a routed proposal (`route`'s resolved bundle and skill), a prepared workflow step, an executed backend invocation and its `result.json`, and a human reviewer's recorded decision.

---

## 10. Evidence, review and publication

Every important conclusion must remain linked to the context that produced it: the governing envelope, the resolved bundle and reference packs, the workflow's artifact evidence, and, where a backend was invoked, its manifest and `result.json`.

The MVP must make it possible to:

- retrieve the artifact evidence a workflow gate required before it opened;
- identify whether a `result.json` belongs to the correct backend, contract version, and pipeline id (`backend_id`, `contract_version`, `pipeline_id` must match the expected values);
- distinguish a calculated readiness result from an interpretation of it;
- re-read and correct a routed proposal before a human-review gate is decided;
- retain the approving human reviewer's identity in the gate's receipt.

Advanced features such as knowledge-axis reactivation and background or scheduled execution are out of MVP scope. The MVP must nonetheless clearly flag a failed backend invocation, a missing artifact, or an unresolved route, rather than silently proceeding; `route` and the strict readiness gate both fail closed by design.

---

## 11. MVP functional scope by user

| User | Actions covered by the MVP |
|---|---|
| **Ecosystem maintainer** | Run advisory and strict `doctor`; remediate the six documented blocker codes against the `aimsun-psp` backend; re-run strict readiness to confirm an empty `readiness_blockers[]` |
| **Orchestrating agent** | Issue a governed envelope; call `route`; drive `workflow init/status/check/advance`; invoke the registered backend through its declared seam |
| **Human reviewer** | Review and decide a human-review gate; approve or reject medium/high risk execution |
| **Sibling repository maintainer** | Confirm vendor sync remote and ref; confirm backend manifest and pipeline id; review the resulting `RunManifest` |

### Cross-cutting MVP capabilities

The routing and workflow layer must also provide: coherent tracing of an envelope through route, workflow, and manifest; a visible distinction between advisory and strict readiness; understandable blocker messages with stable `code`, `message`, `path`, and `remediation` fields; tracking of a running backend smoke; attribution of human-review decisions; a `RunManifest` addressable by path and SHA-256 digest; and command-line output usable by both a human operator and an orchestrating agent in a professional, scriptable context.

---

## 12. Parking lot

The following items are kept as future directions but must not shape the MVP:

| Deferred feature | Main reason | Condition for reconsideration |
|---|---|---|
| Knowledge-axis reactivation (domain reference packs referencing vault notes) | The vault marks domains `draft`/`routable:false`; blocked on `modelling-knowledge` decision 0010 acceptance at general scope and, per the ecosystem's own attribution-protocol history, a DR-1 cure | Vault decision 0010 accepted, DR-1 cure confirmed closed |
| Background or scheduled execution mode | No governance envelope yet defined for unattended execution; `AGENTS.md` forbids only what is listed today, broader controls should follow a strategic decision, not precede it | A named governance envelope for unattended execution is proposed and accepted |
| Full Testudo-to-backend service loop beyond the single smoke | This MVP proves one seam against one registered backend; a full service loop is a larger scope than the repository's own readiness gate calls for | The single-backend smoke has passed and a second backend or a live product loop is explicitly proposed |
| Automatic publication without review | Incompatible with expected human control; no client-facing publication step exists in this repository at all | No reconsideration planned without a governance change |
| Silent modification of vendored subtrees or backend implementation | `AGENTS.md` forbids editing vendored subtrees by hand and copying backend implementation; trust and traceability risk | Must remain prohibited |

---

## 13. Expected outcomes and success measures

The measures must compare the MVP to the current, already-observed state of `doctor --strict --json`. Target values will be defined after observing real remediation work, not assumed in advance.

| User | Key action | Expected outcome | Candidate indicator |
|---|---|---|---|
| Ecosystem maintainer | Remediate the vendor and reference-pack blockers | Vendors pinned, packs active, blockers closed | Count of `vendor-not-synced`, `vendor-not-pinned`, `reference-pack-not-active`, `schema-sibling-fallback` entries in `readiness_blockers[]`, before and after |
| Ecosystem maintainer | Run the real `aimsun-psp` backend smoke | A schema-valid `result.json` is produced by an actual invocation, not a fixture | Smoke pass/fail against the documented remediation conditions in `docs/readiness/STRICT_READINESS.md` |
| Orchestrating agent | Route a governed envelope end to end | The envelope reaches a resolved bundle, skill, and workflow without a boundary or fallback error | Fraction of routed envelopes that resolve versus fail closed |
| Human reviewer | Decide a human-review gate | Every gate decision is traceable to a `reviewer.actor_type: human` receipt | Fraction of human-review gates with a recorded, correctly typed receipt |

---

## 14. UI objective

modeller-agents has no graphical interface in the MVP; its interface is the `modeller` command-line tool and the JSON payloads it emits for orchestrators. The design objective is for that command-line surface to let a maintainer or orchestrating agent understand the active envelope and workflow context, distinguish advisory from strict readiness, see exactly which blocker codes remain open, and retain control of consent and human-review decisions without needing to read source code to interpret an error.

The design must resolve as a priority:

- the persistent, unambiguous representation of which blocker codes are currently open against the `aimsun-psp` backend;
- the coexistence of advisory `doctor` output and release-grade `doctor --strict` output, without conflating the two;
- the preparation and confirmation of a real backend smoke, distinct from a fixture-validated dry run;
- tracking a running workflow step and understanding a failed gate;
- the distinction between a calculated readiness result, an interpretation of it, and a human reviewer's decision;
- a `--json` output shape stable enough for an orchestrating agent to parse without guessing at field names.

---

## 15. Expected deliverables from design

Because modeller-agents' MVP surface is a command-line tool and JSON payloads consumed by other agents and by an ecosystem maintainer, "design" here means interface and evidence design for that surface, not a graphical product. The design team must produce:

1. a documented journey for the ecosystem maintainer closing the strict-readiness blocker list end to end, matching Section 5.1;
2. a clear mapping from each of the six blocker codes to its remediation steps and its confirming re-check, consistent with `docs/readiness/STRICT_READINESS.md`;
3. a stable `--json` schema for `doctor --strict --json`'s `readiness_blockers[]` entries, confirmed with any orchestrating agent expected to parse it;
4. a specification of the `RunManifest`'s evidence references (path plus SHA-256 digest) sufficient for a human reviewer to independently check a claim;
5. a decision matrix distinguishing what a human-review gate requires from what an ordinary workflow gate requires;
6. a documented failure-message format for a fail-closed `route` result, a missing artifact, and a failed backend smoke;
7. a review protocol for confirming a vendor pin or a reference-pack promotion is genuinely remediated, not merely re-labelled;
8. accessibility and usability notes for the command-line output, since its consumers include both a human operator and an automated orchestrating agent.

---

## 16. Expected input from product and technology

### Product and business

Definition of the six strict-readiness blocker codes' remediation conditions as already documented in `docs/readiness/STRICT_READINESS.md`; confirmation of which pipeline id `aimsun-psp` accepts for the smoke; responsibilities and permissions per user as scoped in Section 4; approval rule for a human-review gate and for medium/high risk consent; criteria for calling a vendor "synced and pinned" versus merely branch-tracked; minimum content of a `RunManifest`; rules, if any, for how a downstream product surface consumes routed output.

### Technology

Capabilities available to prepare and launch a backend smoke through `backend.json.runner.command`; technical states of a workflow run and the events `status`/`check`/`advance` report; available stop, relaunch, and recovery mechanisms for a failed workflow step; data and results accessible from a `result.json` for validation against `result.schema.json`; authentication and authorization mechanisms for who may promote a reference pack or pin a vendor; availability of logs and correlation identifiers across a routed envelope, a workflow run, and a `RunManifest`; performance limits observed on a representative backend smoke; architecture of the routing and gating layer relative to the backends and packs it composes; dependencies, licenses, and environment constraints for the vendored `modeller-memory` and `modeller-pipelines` subtrees.

---

## 17. Priority open questions

| ID | Question | Main impact | Suggested owner |
|---|---|---|---|
| **OPN-001** | Has `Vision.md` itself been reviewed and accepted by the ecosystem maintainers it names as its audience? | Whether this brief's upstream grounding is settled or still provisional | Ecosystem architecture owner |
| **OPN-002** | Which `aimsun-psp` pipeline id is confirmed as the Aimsun-free smoke pipeline for the real backend smoke, and has the `aimsun-psp` side of that seam (its own `backend.json`, its own readiness) been independently confirmed ready to receive the call? | Whether the MVP's definition of done can actually be exercised without first doing readiness work inside `aimsun-psp` itself | aimsun-psp maintainers |
| **OPN-003** | Who confirms the remote and ref for the `modeller-memory` and `modeller-pipelines` vendor syncs, and on what cadence should the pin be refreshed afterward? | Whether the vendor blockers are closed once, or need an ongoing remediation owner | modeller-memory and modeller-pipelines maintainers |
| **OPN-004** | What is the reconsideration path and owner for `modelling-knowledge` decision 0010 and the DR-1 attribution-protocol cure that currently block knowledge-axis reactivation? | Whether knowledge-pack routing stays parked indefinitely or has a concrete path back into scope | modelling-knowledge maintainers |
| **OPN-005** | Does any orchestrating agent or downstream product surface already depend on the current `--json` output shape of `doctor`, `route`, or `workflow status`, such that changing it during this MVP would be a breaking change? | Whether Section 15's `--json` schema deliverable is greenfield or must preserve an existing contract | Orchestrating-agent integrators, if any exist today |

---

## 18. Consolidated statement of need

modeller-agents must let an ecosystem maintainer close the repository's own already-documented strict-readiness blocker list against the `aimsun-psp` backend it has already registered, so that `doctor --strict --json` exits `0` with an empty `readiness_blockers[]` array, proving by evidence rather than by registration alone that the routing and gating seam this repository was built to provide actually works end to end.

A single accountable orchestrating-agent identity must carry every governed envelope through routing, workflow gates, and backend invocation, proposing routes and workflow steps without hiding the context, the effects, or the limits of its involvement. `modelling-knowledge`, `modeller-memory`, `aimsun-psp`, and `modeller-pipelines` retain authority within their own domains throughout; modeller-agents composes and gates their capability, it does not absorb it.

Every important conclusion, from a routed envelope to a backend smoke's `result.json`, must remain linked to its artifact evidence and, where a human-review gate applies, an identifiable human reviewer's decision. There is no client-facing publication step in this repository's MVP; what it prepares is a `RunManifest` for a consuming orchestrating agent or downstream product surface to review and act on under its own governance.
