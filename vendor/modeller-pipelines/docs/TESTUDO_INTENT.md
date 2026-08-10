# Testudo and modeller-pipelines: Intent and Scope

**Status:** intent-only — no refactor implied or planned in the current cycle.

## Background

Testudo is the product UI for the modelling ecosystem. Its `vwe` pipeline (VWE = Visual Workbench Explorer) is the **lineage ancestor** of the `modeller-pipelines` contract: `contracts/schemas/pipeline.schema.json` is generalized directly from Testudo's `vwe.pipeline.yml`. Most of the normative rules in `PIPELINE_DEFINITION.md` were distilled from Testudo/VWE invariants already proven in production.

## Current relationship

Testudo currently operates its VWE pipeline **outside** the `modeller-pipelines` contract. It has its own runner, its own result format, and its own pipeline-yml loader. It predates this contract and is not broken by it.

Testudo's relationship to `modeller-pipelines` today:

- It **reads** `result.json` produced by conforming backends (e.g. `aimsun-psp`'s VWE run) for result display and audit.
- The `modeller-pipelines` result schema is designed to be a **strict superset** of what Testudo already consumes — so a Testudo-consumed result file is already contract-valid.
- Testudo does **not** vendor or import this repo.

## Future intent (not planned)

A future epic *might* register Testudo as a conforming backend — exposing its `vwe` pipeline via the `describe`/`run` CLI seam, emitting a conformant `result.json`, and adding `backend.json` + `contract.lock`. This would allow `modeller-agents` to invoke VWE runs the same way it invokes `aimsun-psp` runs.

**No refactor is implied by this document.** It is recorded here so the design intent is not lost, not as a commitment.

## What this means for contract design

When the contract surface (`contracts/`) evolves, Testudo's VWE pipeline is the implicit compatibility oracle: a contract change that would break a Testudo-consumed `result.json` is a breaking change (major version bump), even if no backend has formally registered Testudo yet.
