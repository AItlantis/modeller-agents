# ADR-0001: modeller-pipelines is a scaffold, not a framework

**Status:** accepted  
**Date:** 2026-07-09

## Context

We need pipeline backends to share contract semantics (schema shapes, CLI seam, result format) without creating a shared library that all backends import at runtime. The risk of a shared library is: any change to it forces all backends to update simultaneously; backends with different interpreters (Aimsun-embedded Python vs system Python) cannot share a pip package; and the library becomes a de-facto framework by accumulating extension points.

## Decision

`modeller-pipelines` ships:
- Versioned schemas + normative prose (`contracts/`)
- A black-box conformance test kit (`conformance/`)
- One copyable, runnable template pipeline (`template/`)

**Nothing in this repo is imported at runtime by any backend.** Backends duplicate ~100 lines of result-envelope code (`shared/result_builder.py`); schema validation in CI keeps the duplicates honest against the pinned contract tag.

## Consequences

**Positive:**
- Backends can evolve independently. An `aimsun-psp` change does not require a `modeller-pipelines` release.
- No import graph coupling. The conformance kit is black-box (subprocess + file assertions only).
- Different interpreters (Aimsun Python, system Python, Node) can all conform to the same contract.

**Negative:**
- Result-building code is duplicated per backend (~100 lines each).

**Mitigated by:** CI conformance ensures duplicates stay schema-valid. If/when a third backend appears and duplication becomes painful, extracting a contracts wheel is an explicit new decision (ADR-0003 or later), not a refactor.

## Anti-patterns guarded against

- Importing `minirunner.py` across repos — the file header forbids it; CI grep can enforce.
- Pip-packaging the schemas as a dependency — the slippery slope back to the excluded shared library.
- Adding extension points to `minirunner.py` — the 200-line budget and "zero extension points" rule block this.
- Dual schema authority — the `psp-pipeline-schema` skill must point at `contracts/schemas/pipeline.schema.json` at the pinned tag, not maintain its own copy.
