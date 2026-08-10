# Backend Archetypes (non-normative)

**Status:** informational. Nothing in this document is normative — `contracts/` is the single source
of normative truth. This is a survey of observed backend shapes, written so a new backend author does
not have to independently rediscover that "model-bound" and "has a fixed model-path config field" are
independent properties, or that dispatch mechanism is deliberately out of contract for a reason.

**Origin:** written as part of the contract-v1.2 revision, informed by
`docs/CONTRACT_ARCHETYPE_ELABORATION.md §4` and a real usage audit of `aimsun-psp`, the first backend
with three concurrently-registered pipelines exercising materially different shapes.

---

## Why this document exists

`CLI_SEAM.md` and `STEP_INTERFACE.md §4` correctly keep dispatch mechanism — *how* a backend calls a
step (presenter, work_unit, `aconsole` subprocess, thread pool, direct function call) — out of
contract. That is the right call: the host (`modeller-agents`) never needs to know it to understand
what a pipeline does or what happened.

But dispatch-mechanism-agnosticism can be misread as "every model-bound backend works the same way
internally, it just varies in *how* it opens a model." That reading is false, and one real backend
already disproves it: some model-bound pipelines have a fixed model-path config field, and some
legitimately have none at all. This document sketches the shapes actually observed so a new backend
author calibrates expectations correctly before designing their own dispatch.

---

## The four archetypes

| # | Archetype | What it does | Model-bound? | Fixed model-path field? |
|---|-----------|---------------|---------------|---------------------------|
| A | Artifact rendering | Produces a UI-ready artifact (HTML dashboard, report) from data already on disk; no live simulation model involved. | No | N/A |
| B | Data-warehouse / DB ingestion | Pulls external data (a DB query, a CSV/Parquet extract) and writes it into a live model object. | Yes | Yes — always opens a named model file. |
| C | Model-bound simulation run | Runs an actual simulation/optimization against a live model, potentially for a long time. | Yes | Usually yes, but see caveat below. |
| D | Geodata / staged import | Fetches, normalizes, and (after review) imports external geometry into a live model; often multi-stage with an approval gate. | Yes, for its final step(s); earlier steps are model-free. | **Not necessarily** — see below. |

### A — Artifact rendering (model-free)

The simplest shape: no live model, no `aconsole`-style subprocess needed. Runs entirely in whatever
interpreter the backend's CLI seam itself uses. `CLI_SEAM.md`'s subprocess boundary and
`RESULT_CONTRACT.md`'s envelope apply exactly as documented, with no wrinkle. This archetype is the
contract working exactly as designed.

### B — Data-warehouse / DB ingestion (model-bound, fixed model path)

Needs a live model to write into (e.g. creating a real-data-set object bound to a specific model), but
the model is always a known, named file — the pipeline's config always carries a concrete path to it.
If the backend's own interpreter cannot open a live model in-process (e.g. the CLI seam runs as plain
system Python but the modelling tool requires its own embedded interpreter), dispatch shells out to
that tool's subprocess mode, passing the model path along. This is the most "textbook" model-bound
shape and needs nothing beyond what `STEP_INTERFACE.md §4`'s dispatch-is-out-of-contract stance
already covers.

### C — Model-bound simulation run

The archetype most central to "running a model" in the ordinary sense. Shares B's dispatch shape in
every observed case so far. The property that stresses the contract hardest here is **duration**: a
real simulation run can take minutes to hours, which is exactly the case `RESULT_CONTRACT.md`'s
`status.json` (added 1.2) and the `duration_s` content-quality expectation exist for. No registered
example of this archetype exists yet at the time of writing — everything above is reasoned from the
shared dispatch shape B and D already exercise, not from an observed simulation pipeline. Until one is
registered, C's specific stresses (mid-run status for a run that outlives the caller's patience,
partial-result semantics when a simulation converges poorly) remain unexercised by real evidence, and
the contract should not be considered validated against this archetype until one lands.

### D — Geodata / staged import (model-optional dispatch, possibly approval-gated)

The archetype that most needed writing down, because it breaks an assumption B and C both hold. A
staged geodata-import pipeline's early steps (fetch, normalize, validate) are model-free — they only
touch files on disk. Only its later step(s) touch a live model, and even then, the pipeline's most
common real usage mode may be "operate on whatever model is already open in the current interactive
session," which means the pipeline's config legitimately has **no fixed model-path field at all**.

**A model-bound backend MAY operate on an already-open/injected model and therefore MAY have no
fixed model-path input; whether and how a model is located is a dispatch concern and stays
out of contract.** A backend author should not assume the opposite — that every model-bound pipeline
must carry a `model_path`-shaped config key — just because archetype B does.

This archetype is also the one most likely to need `PIPELINE_DEFINITION.md §4`'s conditional gates
(added 1.2): a "review, then approve, then write" workflow gates its final model-writing step behind
a runtime approval flag, not behind another step's success. See `PIPELINE_DEFINITION.md §4` and
`STEP_INTERFACE.md §2.3a` for the normative treatment of that case.

---

## What stays out of contract regardless of archetype

- Whether dispatch uses a subprocess, a thread, an in-process call, or something else.
- Which config field (if any) carries a model path, and what it's named.
- How a backend locates "the currently open model" when it has no fixed model-path field.
- Internal step-invocation mechanics (presenter pattern, work-unit objects, direct function calls).

## What archetype D specifically motivated adding to the normative contract (v1.2)

- `pipeline.schema.json` `gates[].condition` — a runtime-config predicate gate (`PIPELINE_DEFINITION.md §4`).
- `step-result.schema.json` `skip_reason` and the gate-skip case (`STEP_INTERFACE.md §2.3a`).
- `RESULT_CONTRACT.md`'s clarification that a by-design gate-skip of a required step yields `partial`,
  not `failed`.

These are genuinely normative (they affect what a conforming `result.json` looks like) and are
documented in `contracts/`, not here. This document only covers the non-normative "what shapes exist"
framing; see `contracts/PIPELINE_DEFINITION.md`, `contracts/STEP_INTERFACE.md`, and
`contracts/RESULT_CONTRACT.md` for the normative rules themselves.
