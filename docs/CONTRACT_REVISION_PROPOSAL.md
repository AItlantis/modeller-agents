# Contract Revision Proposal: Efficient for AI Agents, Performant for a UI

**Status (updated 10 August 2026 — see per-recommendation table below; original proposal text below is unchanged):**

| Recommendation | Status | Evidence |
|---|---|---|
| §3a — Version-consistency CI check | **Not shipped** | No CI check, `contracts/`-version grep job, or equivalent mentioned in `CHANGELOG.md` (checked the `[Unreleased] — contract-v1.2` and all earlier entries). |
| §3b — Optional incremental status file (`<run_dir>/status.json`) | **Shipped in contract-v1.2** | `CHANGELOG.md`, `[Unreleased] — contract-v1.2` entry: "`contracts/RESULT_CONTRACT.md` — ... documents the artifact `type` hint and the optional, best-effort `<run_dir>/status.json` incremental polling convention (`current_step_id`, `completed_step_ids`, `skipped_step_ids`)." |
| §3c — `pipeline.schema.json` sub-step id relaxation | **Shipped in contract-v1.2** | `CHANGELOG.md`, `[Unreleased] — contract-v1.2` entry: "`contracts/schemas/pipeline.schema.json` — `steps[].id` and `gates[].step_id`/`gates[].requires[]` widened from `integer` to `["integer", "string"]` with `pattern: "^[0-9]+[a-z]?$"`, admitting lettered substep ids (e.g. `"6b"`)." |
| §3d — Static discovery/lint-repo tool for the conformance kit | **Not shipped** | No `lint-repo`, discovery, or audit tool mentioned in `CHANGELOG.md`. |
| §4a — `run-config.schema.json` / `PIPELINE_DEFINITION.md §5` input typing | **Shipped in contract-v1.2** | `CHANGELOG.md`, `[Unreleased] — contract-v1.2` entry: "`inputs.required[]`/`inputs.optional[]`/`outputs[]` entries may now be an object `{"name": string, "type": string}` in addition to the existing bare string, carrying a minimal free-string type tag. Strict superset; existing bare-string lists validate unchanged." |
| §4b — `STEP_INTERFACE.md §1` reframing as adapter-layer contract | **Unconfirmed** | `contracts/STEP_INTERFACE.md §1` (as of contract-v1.2) still documents the module contract as `run(config, step_params, run_context)` with no "Adapting an existing action layer" subsection, and the `contract-v1.2` `CHANGELOG.md` entry does not call out §4b by name — but whether this recommendation was separately actioned elsewhere could not be verified from this repo's contract/changelog surface alone. Treat as unconfirmed, not as shipped or rejected. |

Recommendations §4c and the §5 adoption-path sequencing are not independently addressed above; consult `CHANGELOG.md`'s `contract-v1.2` entry directly against §4c's conformance-kit content-check proposal if that status is needed.

**Date:** 26 July 2026
**Nature:** research finding and concrete revision proposal, not an executed change
**Scope:** `contracts/` (this repo), informed by an audit of real usage in `aimsun-psp` and an industry survey of agent-tool-calling, workflow-orchestration, and streaming-UI-performance patterns

This document proposes revisions to the modeller-pipelines contract so it is efficient for an AI agent
to call reliably and performant for a UI to render responsively, grounded in what aimsun-psp's real
pipelines actually need. It does not implement any of the changes below; it is a design artifact for
review, following the same discipline as `docs/ADR/` (a proposal precedes a decision, a decision
precedes an edit).

---

## 0. A finding that already got fixed

Before this proposal was drafted, the research that produced it found a live bug: `contracts/VERSION`
said `1.1`, but all four normative documents (`STEP_INTERFACE.md`, `CLI_SEAM.md`,
`RESULT_CONTRACT.md`, `PIPELINE_DEFINITION.md`) still printed `**Contract version:** 1.0`, three of
four schema `$id`s were pinned to `.../contracts/1.0/...`, and `README.md`'s version banner and
curl example both still said `contract-v1.0`. This is exactly the class of drift ADR-0002's single
`contract_version` field discipline exists to prevent, and it had already happened inside this repo's
own documents. **This has been fixed** (all now consistently say `1.1`) as a prerequisite to this
proposal, so the recommendations below build on a self-consistent baseline. A CI check that greps
every `.md`/`$id` in `contracts/` for a version string and fails the build on any mismatch with
`contracts/VERSION` is recommended below (§3a) so this does not recur silently.

---

## 1. Evidence base

**aimsun-psp usage audit**, covering all ~24 numbered domains plus the pipelines actually
registered against this contract (`rendering-outputs`, `cem`, both in `backend.json` at the time of
this proposal's original drafting):

> **Correction (10 August 2026):** the "2 of an estimated 50+" registered-pipeline figure immediately
> below is stale. Per Manager-supplied pre-verified context from prior evidence-recon (not
> independently re-derived here, since `aimsun-psp` is outside this work item's read scope), a later
> check of `aimsun-psp/backend.json` found **8 registered pipelines**, against `aimsun-psp`'s own
> `contract.lock = 1.1` (i.e. `aimsun-psp` has not yet adopted contract-v1.2). The original count below
> is left as-is for historical/evidentiary fidelity; use the corrected figure of 8 for any current
> assessment of registration coverage.

- Only 2 of an estimated 50+ real pipeline-slugs across the catalog are registered at all (see
  correction above — this count is stale). The
  audited `_70_Scripting`/`_80_Calibration`/`_90_Document` domains contribute one more real pipeline
  (the DSM dock, a 9-step `action_interface.py`-conformant pipeline) that is **not** registered, plus
  several ad hoc CLI/Script-Manager scripts with no pipeline shape at all.
- Real conformant action modules (74/74 audited) implement `run(model, obj, io, params)` per
  `shared/protocol/action_action.ActionProtocol` — not `STEP_INTERFACE.md §1`'s documented
  `run(config, step_params, run_context)`. The only things that ever satisfy the documented signature
  are the adapter modules under `shared/modeller_contract/`, which translate one shape into the other.
  A third invocation shape exists too: the presenter/config pattern (`aconsole_runner.run_presenter_pipeline`)
  that `rendering-outputs` and `cem` actually use, itself different again from both of the above.
- At least four independent, mutually-incompatible progress/status mechanisms exist in the wild:
  a Qt `pyqtSignal`-based one, a manual `progress_callback(current, total, message)` threaded through
  presenters (used inconsistently: 8/9 call sites in some domains, 0 in `swm`'s presenter), the
  file-based `shared/work_unit/status_manager.py` (atomic, pollable, but used by none of the audited
  domains), and `_90_Document`'s own `run_state.py` (a **non-atomic** direct `write_text`, so a UI
  polling it mid-write can read a torn/incomplete JSON). None of these write anything the CLI seam's
  documented stdout contract or `result.json` shape can see.
- `contract_pipeline_yml.py` already has to silently drop the lidarimporter's real substep id `"6b"`
  because `pipeline.schema.json`'s `steps[].id` is `type: integer`-only — a concrete, hit-in-practice
  case, not a hypothetical one.
- `result_mapper.py` (the one real translator that exists) hardcodes `"duration_s": 0.0` and
  `"logs": []` — schema-valid but content-empty, because nothing in the schema or the conformance kit
  checks whether a backend bothers to populate a value it is capable of producing.
- `run-config.schema.json`'s `inputs`/`params`/`metadata` are each bare `{"type": "object"}` with no
  nested typing, which is the direct, already-observed cause of "a malformed key only surfaces as a
  downstream KeyError."

**Industry survey**, covering Anthropic/OpenAI/MCP-style tool-calling contracts, workflow engines
(Temporal, Airflow, Prefect, Dagster, Step Functions), and streaming/UI-performance patterns
(SSE, GraphQL subscriptions, polling). Full detail available in the research transcript; the pattern
each recommendation below borrows from is named inline.

---

## 2. Keep unchanged (evidenced, working, do not touch)

- **The CLI seam's subprocess boundary** (`CLI_SEAM.md` in full): exactly two subcommands
  (`describe`/`run`), last-stdout-line-is-the-result-path, `result.json` written on every outcome.
  This is what let `rendering-outputs` and `cem` become callable without modeller-agents knowing
  anything about aconsole, presenters, or GK objects.
- **The three-state status model** (`success|partial|failed` at run level,
  `success|failed|skipped` at step level) and the no-swallow rule (`STEP_INTERFACE.md §2.4`).
  `result_mapper.py` implements this precisely and it maps cleanly onto real aimsun-psp semantics.
- **The artifact-path-relative-to-run-dir rule** (`RESULT_CONTRACT.md`, `STEP_INTERFACE.md §2.2`):
  actively enforced in the one real translator, load-bearing for making a `--run-dir` relocatable.
- **Gates as the sole ordering mechanism**, step ids treated as opaque (`PIPELINE_DEFINITION.md §3-4`):
  a clean, minimal DAG model with no evidence of friction; every workflow-engine survey converges on
  the same "dependency edges, not implicit order" idea.
- **`backend.json` as a thin registration list**, with dispatch mechanism kept deliberately out of
  contract and in a backend-local shim (`pipeline_registry.py`'s `PIPELINE_DISPATCH`). This separation
  is correct and should not be collapsed by adding dispatch-kind fields to the contract schema.

---

## 3. Add (new capability, industry pattern it borrows, why it fits here)

### 3a. Version-consistency CI check

A CI job (or a conformance-kit addition) that greps every `.md` doc header and schema `$id` in
`contracts/` for a version string and fails the build on any mismatch with `contracts/VERSION`. This
is the concrete mechanism that prevents §0's exact bug class from recurring; ADR-0002 states the
discipline but nothing currently enforces it.

### 3b. Optional incremental status file: `<run_dir>/status.json`

Borrows Temporal's heartbeat-plus-queryable-history pattern, scaled down to a single JSON file rather
than an event log. SSE-with-resume and GraphQL subscriptions are the strongest *push* patterns in the
survey, but both require a live connection into the backend process, and `CLI_SEAM.md`'s entire design
is that the backend is an opaque subprocess modeller-agents shells out to and walks away from. A
durable, externally-pollable record that survives the caller not being connected maps onto a
poll-a-file mechanism naturally, because `run_dir` already exists and aimsun-psp *already built* this
mechanism (`shared/work_unit/status_manager.py`'s atomic writer) — it just isn't wired to anything the
contract or a UI can rely on, and three other, incompatible, sometimes-non-atomic reimplementations
have sprung up in its absence.

Concrete addition to `RESULT_CONTRACT.md`, a new optional section:
```json
{
  "contract_version": "1.1",
  "run_id": "...",
  "current_step_id": 3,
  "completed_step_ids": [1, 2],
  "updated_at": "2026-07-25T14:03:11Z"
}
```
at `<run_dir>/status.json`, written by the backend after each step transition (MAY, not MUST), polled
by a UI at a UI-chosen interval. No change to the CLI seam's stdout contract or the terminal
`result.json` shape. A UI that doesn't find the file falls back to today's "running... then flip to
done." Additive-only under ADR-0002: a minor bump, not major.

### 3c. `pipeline.schema.json` sub-step id relaxation

Borrows Dagster's op/sub-op naming convention (a string-pattern relaxation, not a new nesting concept)
rather than inventing child-step objects. `lidarimporter`'s real `"6b"` substep is the forcing
example. Concretely: widen `steps[].id` in `pipeline.schema.json` from `"type": "integer"` to
`"type": ["integer", "string"]` with `pattern: "^[0-9]+[a-z]?$"`, admitting `"6b"` while keeping `6`
valid and keeping the "ids are opaque" rule intact, since ordering still comes exclusively from
`gates[]`.

### 3d. A static discovery/audit tool for the conformance kit

Borrows MCP's `tools/list` idea, pointed at the filesystem instead of a live server (MCP's discovery
works because the server *is* the tool surface; aimsun-psp's problem is the opposite: `backend.json`
is a hand-maintained subset of a much bigger tree of `*.pipeline.yml` files, found by every audit only
by hand via grep). Add a `modeller-pipelines lint-repo <backend-root>` tool that walks a backend tree
for `*.pipeline.yml`, diffs against `backend.json:pipelines[]`, and reports the delta. Pure tooling,
no schema/version implications, no MUST added to any normative document.

---

## 4. Change (specific section, concrete revision)

### 4a. `run-config.schema.json` input typing

Current state: `inputs`/`params`/`metadata` are each bare `{"type": "object"}`. Concrete revision:
don't make `run-config.schema.json` itself typed (a single generic schema can't know per-pipeline
shapes); instead let `PIPELINE_DEFINITION.md §5`'s `inputs.required`/`inputs.optional` (currently bare
name lists) carry a minimal type tag per key:
```yaml
inputs:
  required:
    - name: demand_matrix_path
      type: string
```
A strict superset of the current list-of-strings shape (a bare string stays valid, treated as
`type: any`), additive under ADR-0002. Lets a conformance-kit or agent-side pre-flight validate
`config["inputs"]` against a pipeline's own declared shape before dispatch.

### 4b. `STEP_INTERFACE.md §1` — document the signature as the adapter-layer contract, not the action-module contract

Every real conformant action module implements `run(model, obj, io, params)`, never
`run(config, step_params, run_context)` directly; only `shared/modeller_contract/`'s translation layer
ever satisfies the documented signature. Reframe §1 as describing the CLI-seam-facing entry point, and
add a short "Adapting an existing action layer" subsection pointing at `result_mapper.py` +
`pipeline_registry.py`'s dispatch split as the sanctioned adapter pattern. Documentation clarification
only, no schema or version change.

### 4c. Conformance-kit content checks for `duration_s` and `error.traceback_path`

Not a schema change (the schema is already capable of expressing a real value). Add a conformance-kit
rule: at least one step in a successful multi-step run has `duration_s > 0`, and any step with
`status: failed` has a non-null `error.traceback_path` resolving to a real, non-empty file under
`run_dir`. This catches `result_mapper.py`'s current hardcoded `duration_s: 0.0` / `logs: []`, which
passes today's schema validation while carrying no real content.

---

## 5. Adoption path (no big-bang, does not break `rendering-outputs` or `cem`)

1. **Version-hygiene fix (§0) and CI check (§3a)**, as their own tagged release, zero schema semantic
   change. Verify by re-running `rendering-outputs` and `cem` unchanged; `result.json` still says
   `"contract_version": "1.1"` and every doc now agrees.
2. **`status.json` (§3b)**, opt-in, next. `rendering-outputs`'s in-process dispatch path is the
   natural first adopter, wiring the already-existing but orphaned `status_manager.py` to a real
   caller for the first time; `cem`'s aconsole subprocess path adopts second, since multi-hour aconsole
   runs are exactly where "freeze until done" pain is worst. No other pipeline is required to write it;
   absence means today's UI fallback behavior, unchanged.
3. **Step-id relaxation (§3c)**, a type-widening (`integer` to `integer|string`), so every existing
   pure-integer `*.pipeline.yml` (including both registered pipelines' contract files) validates
   unchanged.
4. **Input type-tagging (§4a)**, opt-in per-pipeline; bare-string lists (both current registered
   pipelines) keep validating as `type: any`.
5. **Conformance-kit content checks (§4c)**, shipped as a **warning, not a hard failure**, for one
   full minor-version cycle, since turning it on as a hard gate immediately would fail
   `rendering-outputs`' own current output the day it ships. Fix `result_mapper.py` to thread real
   per-action timing as a follow-up PR in aimsun-psp, then flip the check to blocking once the
   reference pipeline actually passes it.
6. **Discovery/audit tool (§3d)** can land at any point independently; running it against aimsun-psp
   immediately turns "~50 pipeline-slugs, ~2-3 registered" from a one-time manual finding into a
   trackable number, without forcing a "big bang" registration push. The DSM dock (already conformant
   to the internal `action_interface` contract, per §1's audit) and GEH (well-structured per the same
   audit) are natural next registration candidates, but that is aimsun-psp's own backlog decision, not
   something this contract revision needs to force or schedule.

Net effect: neither currently-registered pipeline ever needs a schema-breaking change at any step in
this sequence. The ~24 domains outside the seam remain outside it throughout; the discovery tool turns
closing that gap into an incremental, trackable backlog instead of a rewrite.

---

## 6. What this proposal does not cover

- `_80_Calibration` (zero pipelines, one Script-Manager script requiring a modal GUI dialog) and most
  of `_90_Document` (subprocess-chained CLI scripts, no `action_interface` usage at all) are not
  reachable by any near-term contract revision; they would need code changes in aimsun-psp itself
  before conformance is even meaningful.
- Full-catalog registration (all ~24 domains) is explicitly out of scope; see `aimsun-psp`'s own brief
  (`docs/vision/Business-need-design-brief.md`), which bounds its MVP to a single third pipeline.
- Dock (`docks/dsm/`) registration in `backend.json` is possible today (the schema already has a
  `docks[]` field) but is a decision for aimsun-psp's own backlog, not a contract change.
