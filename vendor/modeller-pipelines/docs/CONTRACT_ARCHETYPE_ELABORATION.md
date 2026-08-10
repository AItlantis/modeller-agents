# Contract Archetype Elaboration: Four Pipeline Shapes Against v1.1

**Status:** Proposed, not yet reviewed or adopted
**Date:** 26 July 2026
**Nature:** research finding and concrete revision proposal, not an executed change
**Scope:** `contracts/` (this repo), grounded in the three pipelines now actually
registered against contract v1.1 in `aimsun-psp/backend.json`
(`rendering-outputs`, `cem`, `osmimporter`), plus the OSM/geodata-import archetype
as the current source of the most contract friction.
**Relation to prior work:** COMPANION to `docs/CONTRACT_REVISION_PROPOSAL.md`
(hereafter "the Revision Proposal" / "RP"), **not a replacement**. It extends,
deepens, and in two places disagrees with specific RP sections. It does not
re-derive RP's findings; it cites them (`RP §3b`, `RP §5 step 3`, etc.).

This document, like the RP, does not implement any change. It proposes revisions
for review, following `docs/ADR/` discipline: a proposal precedes a decision, a
decision precedes an edit to `contracts/`.

---

## 0. Why a companion, and why now

The RP was written from an audit of two registered pipelines (`rendering-outputs`,
`cem`) plus a catalog-wide survey. Since then a **third** pipeline —
`osmimporter` — has been built out and registered (`backend.json:pipelines[2]`,
confirmed this session). It is the first registered pipeline that is
**long-running, staged, geo-heavy, and approval-gated**, and it exercises corners
of the contract the two-pipeline audit could not have seen. All evidence below was
read directly from the real files this session; file:line citations are given so a
reviewer can re-verify without trusting this summary.

The four archetypes this document reasons over:

| # | Archetype | Registered exemplar | Dispatch (out-of-contract, per `CLI_SEAM.md`) |
|---|-----------|---------------------|-----------------------------------------------|
| A | Artifact rendering (model-free) | `rendering-outputs` | `InProcessDispatch` |
| B | Data-warehouse / DB ingestion (model-bound, fixed model) | `cem` | `AconsoleSubprocessDispatch`, `model_path_required=True` |
| C | Model-bound simulation run | (not yet registered — see §6) | would be `AconsoleSubprocessDispatch` |
| D | OSM / geodata import (staged, gated, model-optional) | `osmimporter` | `AconsoleSubprocessDispatch`, `model_path_required=False` |

Archetype C has no registered exemplar yet; where this document reasons about it,
it says so and reasons from the shared `AconsoleSubprocessDispatch` shape B and D
already exercise, not from an invented pipeline.

**Filename rationale.** `CONTRACT_ARCHETYPE_ELABORATION.md` was chosen over
`CONTRACT_REVISION_PROPOSAL_2.md` deliberately: this is not a second general
revision pass, it is a lens (the four archetypes) applied to the same contract.
Naming it as an elaboration keeps the RP as the single canonical revision
proposal and makes clear this defers to it on everything it does not explicitly
revise.

---

## 1. What the current contract (v1.1) handles well, per archetype

Read `contracts/` directly, not only the summary below.

- **A (rendering).** Handled cleanly, no friction. `InProcessDispatch` runs the
  presenter in the CLI's own interpreter; `result_mapper.build_result_envelope()`
  produces a valid envelope; artifacts (HTML/JSON) are relative-path records.
  This archetype is the contract working exactly as designed and is the reason
  `CLI_SEAM.md`'s "dispatch is out of contract" stance (RP §2, "Keep unchanged")
  is correct — nothing about rendering leaks into the schema.
- **B (CEM / DB ingestion).** Handled well. `cem_aconsole.py` writes a
  `pipeline_result.json` envelope on **both** success and exception paths
  (`cem_aconsole.py:134`, `:182`), which `aconsole_dispatch.py` reads back and
  `result_mapper` normalizes. The `AconsoleSubprocessDispatch` shim keeps the
  aconsole shell-out entirely backend-local. The `success|partial|failed` model
  and the relative-artifact rule (RP §2) map cleanly. CEM always has a concrete
  `.ang` (`model_path_required=True`, `pipeline_registry.py:47`), so the
  contract's implicit "a model-bound backend points at a model file" assumption
  holds here without strain.
- **C (simulation).** Would be handled by the same B machinery; a DUE/mesoscopic
  run is a long aconsole subprocess writing a result envelope. The `duration_s`
  content gap (RP §4c) bites hardest here (a 40-minute run reporting
  `duration_s: 0.0` is actively misleading), reinforcing RP §4c rather than
  adding to it.
- **D (osmimporter).** Handled well through step 9 (all pure-compute steps map to
  ordinary DAG edges and success/failed results). The friction is concentrated in
  four specific places — the approval gate, the "required step never invoked"
  status case, the absent model-path field, and the GeoPackage artifact type —
  addressed one-by-one in §2–§5 below.

The headline: **three of four archetypes need nothing beyond what the RP already
proposes.** The archetype lens does not blow up the contract. It surfaces exactly
one genuinely new expressiveness gap (the conditional gate, §2) plus three
smaller, tightly-scoped clarifications (§3, §4, §5), and it revises one RP
recommendation on versioning grounds (§7).

---

## 2. The conditional/approval gate — a real gap `pipeline.schema.json` cannot express

### 2.1 The evidence (verified this session)

`osmimporter.pipeline.yml` (the internal definition) carries, at lines 205–210, a
gate the contract's `gates[]` DAG cannot represent:

```yaml
gates:
  - if: "config.import_approved != true"
    block: [10, 12]
```

This is a **conditional-block** mechanism keyed on a **runtime config value**
(`import_approved: bool`), not a dependency edge. The contract's `gates[]`
(`PIPELINE_DEFINITION.md §4`, `pipeline.schema.json` lines 85–102) is a pure
`{step_id, requires: [ids]}` dependency-DAG whose semantics are "the required
steps must have `status: success` first." It has **no** slot for a config
predicate.

The generated contract-facing file `osmimporter.contract.pipeline.yml` therefore
derives **only** the ordinary chain edges (`step_id: 10 requires: [9]`,
`step_id: 12 requires: [10]`, lines 174–182) and **drops the conditional
entirely**. Read alone, the external contract yml states that step 10
(`required: true`) always runs after step 9 succeeds — when in reality step 10 may
be skipped by design whenever `import_approved` is false, which is its most common
state (default `false`, `osmimporter.pipeline.yml:286`). The external artifact is
not merely less expressive than the internal one; on this point it is **actively
misleading** to a reader who takes it as ground truth.

This is distinct from everything in the RP. The RP's `gates[]` treatment (RP §2)
explicitly lists gates under "Keep unchanged … no evidence of friction." That
judgement was correct for a two-pipeline audit where neither pipeline had a
conditional gate. `osmimporter` is the forcing case that revises it: **there is
now evidence of friction, and it is a silent-correctness problem, not a
convenience problem.**

### 2.2 Position: this belongs IN the contract, as a minimal additive field

I take the position that this **should** be expressible in the contract, and that
leaving it backend-local (the "dispatch is out of contract" precedent) is the
wrong analogy.

The "out of contract" precedent (`CLI_SEAM.md` "What is out of contract";
`STEP_INTERFACE.md §4`) covers **dispatch mechanism** — *how* a backend calls a
step (presenter, aconsole, thread pool). That is correctly hidden because the host
never needs to know it to understand *what the pipeline does or what happened*.
A conditional gate is categorically different: it changes **which declared steps
may run**, which is exactly the information the pipeline definition exists to
publish. `PIPELINE_DEFINITION.md §3`'s own rule "no undeclared-but-wired steps"
establishes the principle that *the set of steps the runner may invoke is
contract-visible*. A gate that can suppress a declared required step is the dual
of that rule and belongs in the same document. A host or UI that reads the
contract yml to render "here is what this pipeline will do" cannot currently show
"step 10 runs only if you approve" — it has to special-case `osmimporter` by name,
which is precisely the backend-specific knowledge the contract exists to abolish.

### 2.3 Concrete minimal schema shape

Add an **optional** `condition` field to a gate object, expressing a single
config-key predicate — deliberately not a general expression language:

```json
"gates": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["step_id"],
    "properties": {
      "step_id": { "type": "integer" },
      "requires": { "type": "array", "items": { "type": "integer" } },
      "condition": {
        "type": "object",
        "required": ["input", "equals"],
        "properties": {
          "input":  { "type": "string" },
          "equals": { "type": ["boolean", "string", "number", "null"] }
        }
      }
    }
  }
}
```

Semantics (to be written into `PIPELINE_DEFINITION.md §4`): a step whose gate
carries a `condition` runs **only** when `config.inputs[condition.input] ==
condition.equals`; otherwise the runner MUST NOT dispatch it and MUST record it as
`skipped` with a reason (see §3, which this depends on). `requires` becomes
optional (a gate may be a pure condition, a pure dependency, or both).
osmimporter's real gate becomes:

```yaml
gates:
  - step_id: 10
    requires: [9]
    condition: { input: import_approved, equals: true }
  - step_id: 12
    requires: [10]
    condition: { input: import_approved, equals: true }
```

**Deliberately excluded:** general boolean expressions, `!=`/`<`/`>` operators,
multi-key predicates, cross-step-result conditions. `osmimporter`'s real case is a
single-key equality (`import_approved != true` is representable as `equals: true`
on the *positive* condition). The second-use test (ADR-0002 cultural rule) says a
field enters when a real backend needs it — one backend needs single-key equality,
so that is exactly what ships. Anything richer waits for a second forcing case.

### 2.4 Version classification and adoption path

**Additive → minor bump (1.1 → 1.2).** `condition` is a new optional field;
making `requires` optional widens what validates (every existing gate with
`requires` still validates). No existing `*.pipeline.yml` breaks:
`rendering-outputs` and `cem` have no conditional gates and are unaffected;
`osmimporter`'s *contract* yml validates today (it has no `condition` yet) and
would validate after, gaining the ability to stop lying about step 10.
Adoption is opt-in: `contract_pipeline_yml.py` (in aimsun-psp, out of this repo's
scope) can be taught to emit `condition` from its internal `{if, block}` DSL as a
follow-up — but that is aimsun-psp's backlog, and until it does, the contract yml
is no worse than today.

**This is the single most important addition in this document** and the one place
it most clearly extends beyond the RP's scope rather than deepening it.

---

## 3. "Required step never invoked" vs "optional step self-reported skipped"

### 3.1 The evidence (verified this session)

`STEP_INTERFACE.md §2.3` defines `skipped` as something **the step itself returns**
when it is `required: false` and cannot proceed. `RESULT_CONTRACT.md` and
`step-result.schema.json` inherit that single meaning. But osmimporter's approval
gate produces a **different** case the normative docs never describe: when
`import_approved=false`, the presenter **never invokes** step 10 (a `required:
true` step) at all. Step 10 does not run and return `skipped` — it simply never
appears in `action_results`.

aimsun-psp already hit this and fixed it backend-locally:
`result_mapper._missing_declared_steps()` (`result_mapper.py:90-118`) synthesizes a
`{"status": "skipped", …, "message": "required step did not run"}` entry for any
declared step id absent from the results. Its docstring (`:36-43`, `:94-100`)
spells out the exact reasoning: "a presenter that gates a step behind a runtime
condition and skips calling its action entirely, rather than calling it and it
failing." Without this synthesis, a **required** step that never ran would let the
run report `status: success` — a silent-correctness bug. This is the mirror image
of the `duration_s: 0.0` content gap the RP flagged (RP §1, RP §4c): both are
cases where a schema-valid envelope carries a semantically wrong value.

### 3.2 Position: yes, add normative language — and it should be the ORCHESTRATOR's duty, not the step's

The current contract has a blind spot: it assumes every non-success step outcome
originates *at the step*. The gate case originates at the **orchestrator/presenter**
— above the step, before it is ever called. Every future backend with an approval
gate will independently rediscover this and reinvent `_missing_declared_steps`.
That is exactly the "each backend reinvents it" cost the contract exists to
prevent, and it is worse than the `duration_s` gap because getting it wrong flips
a run from correctly-`failed`/`partial` to falsely-`success`.

I recommend distinguishing the two cases normatively. Two sub-options; I recommend
3.2b.

**3.2a — reuse `skipped`, add orchestrator-duty prose (minimal).** Keep the
`step-result.schema.json` enum as-is. Add to `RESULT_CONTRACT.md` a normative
paragraph: *"When the orchestrator does not invoke a declared step (required or
optional) because a runtime gate condition was not met, it MUST synthesize a
`status: skipped` step-result entry for that step, so every declared step is
accounted for in `steps[]`. A required step so skipped MUST NOT yield run status
`success`: the run is `failed` (a required step did not complete) unless the step's
gate marks the skip as an expected, non-failing outcome."* This is the smallest
change that closes the silent-`success` hole and makes `_missing_declared_steps`
normative-guidance instead of folklore. **No schema change; doc-only; minor.**

**3.2b — add a `skip_reason` discriminator (recommended).** As 3.2a, PLUS an
optional `skip_reason` enum on the step-result schema to tell the two cases apart:

```json
"skip_reason": {
  "type": "string",
  "enum": ["optional_input_absent", "gate_condition_unmet", "cache_upstream_skip"]
}
```

Rationale for preferring 3.2b: the RP's whole thesis is that a UI and an agent
need to *render what happened* without guessing. "The optional report was skipped
because you didn't pass a filter" and "the required import was skipped because you
didn't approve it" are wildly different messages to a user; today's bare `skipped`
collapses them. The osmimporter case makes `gate_condition_unmet` a real,
second-use-justified value right now, and it pairs naturally with the §2 `condition`
field (a step skipped by a §2 gate reports `skip_reason: gate_condition_unmet`).
`optional_input_absent` is the existing `§2.3` case. This directly serves the RP's
"performant for a UI to render" north star.

**Crucial semantic point (revises the naive reading).** A required step skipped by
an *approved-by-design* gate is **not a failure** — an osmimporter run with
`import_approved=false` that stops before step 10 is a *successful dry preview*,
not a broken run. This means the run-status rule needs care:
`result_mapper.py:56` currently treats any required step in `("failed",
"skipped")` as forcing `status: failed` (`required_failed`). That is the
conservative-safe default (better to under-report success than falsely claim it),
but with §2's `condition` in the contract, a gate-skipped required step should
arguably yield `partial` (or even `success` with a distinct sub-state), not
`failed`. **I flag this as needing an explicit decision, not a silent default**:
if the contract admits conditional gates (§2), it must also say what run-level
status a by-design gate-skip produces. My recommendation: **`partial`** — the run
did everything it was permitted to do; nothing failed; a required step was
deliberately withheld. This is the cleanest existing status semantics
(`RESULT_CONTRACT.md`: partial = "best-effort") without inventing a fourth run
state (which would be breaking).

### 3.2c Version classification and adoption path

- 3.2a: doc-only, **minor** (arguably no version bump at all — it documents
  existing conformant behavior). Breaks nothing.
- 3.2b: new optional `skip_reason` field, **minor (1.1 → 1.2)**. Absent field =
  today's behavior; `rendering-outputs`/`cem` (no skips) unaffected;
  `osmimporter` gains the ability to say *why*. Fold into the same 1.2 as §2.
- The `partial`-vs-`failed` run-status decision is a **semantics clarification**;
  if it changes how a required-step-skip maps to run status it is arguably
  **breaking** (a run that was `failed` becomes `partial`). But note: it only
  changes behavior for pipelines that *use* §2 conditional gates, of which there
  are zero today until osmimporter adopts them — so in practice no registered
  pipeline's observed output changes. I classify it **minor, gated on §2 adoption**,
  and recommend stating it explicitly in `RESULT_CONTRACT.md §Status semantics`.

---

## 4. Model-bound backends that have no fixed model-path — acknowledge the archetype

### 4.1 The evidence (verified this session)

CEM (`AconsoleSubprocessDispatch`, `model_path_required=True`,
`pipeline_registry.py:47`) always needs a concrete `.ang`. osmimporter does not:
`OsmImporterConfig.template_ang_path: Optional[str] = None`
(`osmimporter_config.py:109`), where `None` means "operate on the
already-open/injected model" — its most common real usage, since it typically runs
against a model being built live in an interactive session. This session that
forced a new field on the internal dispatch descriptor:
`AconsoleSubprocessDispatch.model_path_required: bool = True`
(`pipeline_registry.py:46`), default preserving CEM's behavior, set `False` for
osmimporter (`:82`).

The lesson: the contract's *implicit* assumption "a model-bound backend always has
a concrete model file to point at" is **archetype-specific** (true for B and C,
false for D), not universal.

### 4.2 Position: acknowledge it non-normatively; do NOT add a schema field

The dispatch mechanism — including *whether* a model path is required and *which
config field* carries it — is correctly out of contract (`CLI_SEAM.md`,
`STEP_INTERFACE.md §4`). `model_path_required` and `model_path_field` live in
aimsun-psp's `pipeline_registry.py` and **should stay there**. Adding a
`requires_model_path` field to `backend.schema.json` or `pipeline.schema.json`
would be exactly the "adding dispatch-kind fields to the contract schema" the RP
correctly warns against (RP §2, final bullet: "This separation is correct and
should not be collapsed"). I fully endorse that and do not propose to touch a
schema here.

**But** the contract's *prose* currently frames model-bound backends in a way that
quietly assumes a fixed model path (the `CLI_SEAM.md` interpreter examples, the
general mental model that a model-bound run "opens the model"). A backend author
reading the contract could reasonably conclude a model-bound pipeline *must* take a
concrete model path — and osmimporter is the live counter-example. The fix is a
**non-normative acknowledgement**, not a rule:

- Add a short **"Backend Archetypes (non-normative appendix)"** to `CLI_SEAM.md`
  (or a new `docs/BACKEND_ARCHETYPES.md` cross-linked from it), sketching the
  four archetypes A–D and stating plainly: *a model-bound backend MAY operate on
  an already-open/injected model and therefore MAY have no fixed model-path input;
  whether and how a model is located is a dispatch concern and stays out of
  contract.* This is documentation-only, changes no MUST, adds no field.

Placement: I prefer a **standalone `docs/BACKEND_ARCHETYPES.md`** over a footnote
in `CLI_SEAM.md`, because `CLI_SEAM.md` is normative and terse by design and this
is explanatory. A footnote would blur the normative/non-normative line the contract
is careful about. Cross-link it from `CLI_SEAM.md`'s "What is out of contract"
section and from `docs/HOW_TO_CONFORM.md`.

### 4.3 Version classification

**Doc-only, non-normative. No version bump.** Breaks nothing; adds nothing to any
schema; `rendering-outputs`/`cem`/`osmimporter` all continue to conform unchanged.
This is the cheapest recommendation in the document and the one I hold most firmly:
the contract already made the right *mechanism* decision (dispatch out of contract);
it just never wrote down that "model-bound" and "has a model-path field" are
independent, and one real backend already proves they are.

---

## 5. Artifact type/mimetype hints — a genuine second forcing case now exists

### 5.1 The evidence (verified this session)

`RESULT_CONTRACT.md`'s artifact record is `{name, path}` (schema `$defs/artifact`,
`result.schema.json:80-93`) — a bare path string, no type. Across the three
registered pipelines the observed real artifact types are now: **HTML/JSON**
(`rendering-outputs`), **CSV/Parquet + the model** (`cem`), and — new with
osmimporter — **GeoPackage (`.gpkg`), JSON mapping, and `.ang`**
(`osmimporter.pipeline.yml:368-398` declares `type: GeoPackage`, `type: JSON`,
`type: ANG`). Notably osmimporter's *internal* output declaration **already
carries a `type:` field per output** — the backend authors reached for exactly the
hint the contract omits, and had to keep it internal-only because the contract
artifact record has nowhere to put it.

### 5.2 Position: yes, add an OPTIONAL `type` hint — the second forcing case is here

The RP did not raise this because its two pipelines produced HTML/JSON/CSV, all of
which a UI can reasonably infer from extension. The bar for adding a field
(ADR-0002 second-use test) is "a real backend needs it, not speculatively."
GeoPackage is the case that clears the bar: `.gpkg` is a SQLite container whose
extension tells a UI nothing about *how to preview it* (it is not "a spreadsheet"
or "an image"), and `.ang` is an opaque Aimsun binary a generic UI cannot render
at all and must be told *not* to try. "Infer from extension" quietly fails for
exactly the artifact types the geodata/model archetypes produce. And the forcing
evidence is not hypothetical: osmimporter's own author **already added `type:` to
every output record internally** because the bare-path shape was insufficient —
that is a concrete second use, not a speculative one.

Concrete shape — an **optional** `type` on the artifact `$def`:

```json
"artifact": {
  "type": "object",
  "required": ["name", "path"],
  "properties": {
    "name": { "type": "string" },
    "path": { "type": "string" },
    "type": { "type": "string" }
  }
}
```

I recommend a **free string** (`"GeoPackage"`, `"application/geopackage+sqlite3"`,
`"text/html"`, `"ANG"`) rather than a closed enum or a strict `mimetype` format,
for two reasons: (1) there is no registered IANA type for `.ang` or reliably for
`.gpkg`, so a strict mimetype constraint would force awkward `application/octet-stream`
for the two types that most need a hint; (2) a closed enum would need editing every
time a new artifact type appears, reintroducing the churn ADR-0002 avoids. A free
string carrying either a mimetype or a well-known label is the least-committal shape
that still lets a UI branch on "renderable / downloadable-only / model-object."
`RESULT_CONTRACT.md` should note the field is a **hint**, MAY be absent, and a UI
MUST fall back to extension-inference when it is (preserving today's behavior
exactly).

### 5.3 Version classification and adoption path

**Additive optional field → minor (1.1 → 1.2).** Fold into the same 1.2 as §2/§3.
Absent `type` = today's behavior; all three registered pipelines' current envelopes
validate unchanged (none emit `type` yet); `osmimporter` can populate it from the
`type:` it already tracks internally. No conformance test needs to require it;
`RESULT_CONTRACT.md` marks it SHOULD-when-known, MAY-omit.

This is a **real** disagreement-of-degree with the implied RP posture: the RP's
`{name, path}` sat under "Keep unchanged" (RP §2, artifact-path rule). I am not
touching the **path** rule (relative-to-run-dir stays sacrosanct) — I am adding an
orthogonal optional hint. The artifact *path* discipline and an artifact *type*
hint are independent, and the second archetype-wave produced the forcing case the
first could not.

---

## 6. What the four-archetype lens surfaces that two pipelines could not

Beyond §2–§5, the lens exposes several cross-cutting observations the RP's audit
had no way to see:

1. **`status.json` (RP §3b) is under-specified for the STAGED case, and its
   adoption order is now wrong.** RP §5 step 2 names `rendering-outputs` as the
   natural first `status.json` adopter (in-process, wiring the orphaned
   `status_manager.py`). But `rendering-outputs` is *fast* — the pipeline that
   most *needs* incremental status is the slowest, most-staged one, and that is now
   `osmimporter` (12 steps, multi-minute network fetch over a real city). I
   **revise RP §5 step 2's adoption order**: the incremental-status feature should
   be validated first against `osmimporter` (or CEM), where "freeze until done" is
   genuinely painful, not against the sub-second rendering pipeline where it is
   cosmetic. The RP's schema for `status.json` (`current_step_id`,
   `completed_step_ids`) is also incomplete for archetype D: with §2 conditional
   gates in play, a UI polling `status.json` needs to know a step was *gate-skipped*,
   not merely "not yet reached" — so `status.json` should also carry
   `skipped_step_ids: []`. This is a concrete extension of RP §3b, additive, minor.

2. **The "one contract yml derived from a richer internal yml" pattern is now the
   norm, and it silently loses information (§2 is the acute case, but not the
   only one).** `contract_pipeline_yml.py` flattens a 400-line internal
   `osmimporter.pipeline.yml` (with `depends_on`, per-input `type`/`enum`/`default`,
   per-output `type`/`filename`, and the `{if, block}` gate DSL) into a contract yml
   that keeps only the DAG edges and bare name-lists. §2 (conditional gate) and §5
   (`type`) each independently propose lifting one dropped facet into the contract.
   The **meta-finding**: the contract yml is becoming a lossy projection, and each
   lost facet is a candidate second-use case. RP §4a (input type-tagging) already
   proposed lifting one such facet (input `type`); §5 here lifts another (output
   `type`). These are the same pattern and should be understood as one direction of
   travel — *the internal yml is the empirical backlog of what the contract yml is
   missing* — rather than as scattered one-off additions. I recommend the RP's §4a
   and this document's §5 be adopted **together** in 1.2 as "artifact/IO type
   hints," since they are the same forcing pattern (an author already tracking
   `type` internally) applied to inputs and outputs respectively.

3. **Archetype C (simulation) is registered by NOBODY yet, and this is a coverage
   risk the RP's optimism understates.** RP §5 lists DSM and GEH as "natural next
   registration candidates." Neither is a long simulation run. The archetype most
   central to the product's stated purpose — actually *running a model* — has zero
   registered exemplars, so every simulation-specific contract stress (multi-hour
   `duration_s`, mid-run status for a run that outlives the caller's patience,
   partial-result semantics when a sim converges poorly) remains **unexercised**.
   RP §4c (duration content check) and §3b (status.json) are both really
   *simulation* requirements wearing CEM's clothes. I flag: **the contract should
   not be declared "archetype-complete" until one real simulation pipeline is
   registered**, because C is the archetype most likely to surface a *breaking*
   need (e.g. streaming partial results), and it is precisely the one with no
   evidence yet. This is not a change to propose — it is a scoping caution that the
   two-pipeline (soon three-pipeline) evidence base still has a model-run-shaped
   hole.

4. **The RP's `partial` status is doing double duty and osmimporter strains it.**
   `RESULT_CONTRACT.md` defines `partial` as "all required steps succeeded; an
   optional step failed/skipped." But §3.2's recommendation (a by-design
   gate-skipped *required* step → `partial`) overloads `partial` to also mean "a
   required step was deliberately withheld, nothing failed." These are different
   user-facing meanings ("something optional went wrong" vs "you chose not to do
   the final step") sharing one status token — the same collapse §3.2b's
   `skip_reason` fixes at step level, now visible at run level. I do **not** propose
   a fourth run status (breaking, and premature on one forcing case), but I flag
   that if a *second* "deliberately-withheld" case appears, a run-level analogue of
   `skip_reason` becomes the second-use-justified fix, and the contract should
   expect it.

---

## 7. Where this document disagrees with the Revision Proposal

Two disagreements, one on versioning classification (the sharpest), one on
sequencing.

### 7.1 (Sharpest) RP §3c's step-id relaxation is classified as minor; under ADR-0002 it is arguably BREAKING

RP §3c and RP §5 step 3 propose widening `pipeline.schema.json`'s `steps[].id`
from `"type": "integer"` to `"type": ["integer", "string"]` with a pattern, to
admit `lidarimporter`'s `"6b"` substep, and call it a "type-widening" that
validates every existing pure-integer yml unchanged — i.e. **minor**.

I disagree with the *classification*, and it matters because ADR-0002 and
`CONTRACT_VERSIONS.md` draw the minor/major line at exactly this: *"Existing
required fields MUST NOT be … have their type changed"* (`CONTRACT_VERSIONS.md`
line 15–16). `steps[].id` is a required field (`pipeline.schema.json:52`). Changing
its type from `integer` to `integer|string` **is** a type change on a required
field by the literal text of the versioning rule — even though it is a *widening*
that keeps old documents valid. The RP is right that no existing *producer* breaks;
but a *consumer* pinned to 1.1 that assumed `step_id` is an integer (and every
current consumer does — `result_mapper._map_action` does `int(action.get(...))`,
`result.schema.json` types `step_id` as `integer`, and the cross-file
`step-result.schema.json` correlation to `pipeline.schema.json` ids assumes
integer) can now receive a string id it cannot handle. **Widening a producer's
allowed range narrows a consumer's guarantees** — that is the classic covariance
trap, and it is why "type change on a required field" is drawn as breaking
regardless of direction.

Two honest ways to resolve, and the RP should pick one explicitly rather than
assert "minor":

- **(a) Call it major (2.0).** Correct by the letter of ADR-0002; costly (major
  bumps are heavyweight, and `"6b"` is a thin justification for one).
- **(b) Keep it minor but ALSO widen every *consumer* schema in the same 1.2** —
  `result.schema.json:step_id` and `step-result.schema.json:step_id` must move to
  `["integer","string"]` **simultaneously**, and `result_mapper`'s `int(...)` cast
  must be documented as needing to tolerate strings, so no in-support consumer is
  left assuming integer. Under ADR-0002's *whole-surface single version* discipline,
  this is defensible: the whole surface moves together, so "consumer guarantee
  narrowed" is contained within one coordinated minor bump. **I recommend (b)**,
  and I recommend the RP's §3c be amended to say so explicitly, because as written
  it changes only `pipeline.schema.json` and would leave `result.schema.json`'s
  `step_id: integer` contradicting it — a *new* internal drift of exactly the class
  RP §0 just finished fixing. This is the most important correction in this
  document after §2.

### 7.2 (Sequencing) RP §5 step 2's `status.json` first-adopter should be osmimporter/CEM, not rendering-outputs

Covered in §6.1 above. The RP's ordering optimizes for "easiest to wire" (the
in-process path); the actual user value of incremental status is proportional to
run duration, and `rendering-outputs` has almost none. Validate the feature where
it matters. This is a revision of RP §5 step 2's stated order, not of the feature
itself (I fully endorse RP §3b's `status.json` design, and extend it with
`skipped_step_ids` in §6.1).

---

## 8. Consolidated recommendation table (all additive unless noted)

| # | Recommendation | Touches | Version impact | Breaks a registered pipeline? |
|---|----------------|---------|----------------|-------------------------------|
| §2 | Optional `condition` (single-key equality) on `gates[]` | `pipeline.schema.json`, `PIPELINE_DEFINITION.md §4` | minor (1.2) | No |
| §3.2a | Prose: orchestrator MUST synthesize `skipped` for un-invoked declared steps | `RESULT_CONTRACT.md` | minor (doc-only) | No |
| §3.2b | Optional `skip_reason` enum on step-result | `step-result.schema.json`, `RESULT_CONTRACT.md` | minor (1.2) | No |
| §3.2 | Decide: by-design gate-skip of a required step → run status `partial` | `RESULT_CONTRACT.md §Status semantics` | minor (gated on §2 use) | No (no pipeline uses §2 yet) |
| §4 | Non-normative `docs/BACKEND_ARCHETYPES.md`; model-bound ≠ has-model-path | new doc + `CLI_SEAM.md` cross-link | none | No |
| §5 | Optional free-string `type` hint on artifact records | `result.schema.json` `$defs/artifact`, `RESULT_CONTRACT.md` | minor (1.2) | No |
| §6.1 | Add `skipped_step_ids[]` to RP §3b's `status.json` | (extends RP §3b) | minor | No |
| §6.2 | Adopt RP §4a (input type) + §5 (output type) together as "IO type hints" | (sequencing) | minor | No |
| §7.1 | Reclassify RP §3c: widen consumer schemas in lockstep, or call it major | `result.schema.json`, `step-result.schema.json` | **correction to RP** | No (if done in lockstep) |
| §7.2 | Reorder RP §5 step 2: osmimporter/CEM as first `status.json` adopter | (sequencing) | none | No |

**Net:** one coherent minor bump (1.1 → 1.2) carries §2, §3.2b, §5, and §6.1;
§3.2a/§4 are doc-only; §6.2/§7.2 are sequencing; §7.1 is a correction to how RP §3c
must be executed to stay self-consistent. No recommendation in this document
requires a major bump, and none breaks `rendering-outputs`, `cem`, or the current
`osmimporter` registration.

---

## 9. What this document does not cover

- It does not re-derive or restate the RP. RP §3a (version-CI), §3d (lint tool),
  §4b (adapter-signature framing), §4c (duration/traceback content checks) stand as
  written and are not revisited except where cited.
- It does not touch dispatch mechanism (out of contract, correctly — §4 endorses
  this).
- It does not propose a fourth run-status token, a general gate-expression language,
  or a closed artifact-type enum — each deliberately deferred to a genuine second
  forcing case per ADR-0002.
- It does not register any new pipeline or edit `backend.json`, `contracts/`, or any
  schema. It is a proposal document, matching the RP's own nature.
- Archetype C (simulation) is reasoned about from the shared `AconsoleSubprocess`
  shape but has no registered exemplar; §6.3 flags this as an evidence gap rather
  than papering over it.
