# `modeller-agents` — V-Cycle Workflow Package

**Status:** implementation-ready specification  
**Date:** 2026-07-14  
**Target owner:** `modeller-agents`

**Source basis:** *Apports de l'intelligence artificielle générative sur le cycle en V d’un projet*, Hervé Lenglin, version 2, 07/07/2026.

This package adds a reusable V-cycle workflow family with three modes:

```text
full            Complete V-cycle.
stage           One selected stage.
paired-review   Review a descending artifact against its matching validation stage.
```

Core rule:

> AI may prepare, analyze, generate, compare, detect and recommend. A named human remains accountable for review, approval, acceptance and commitment decisions.

The package summarizes the operational concepts; it does not reproduce the source document's tables.

## Contents

- `docs/V_CYCLE_SPECIFICATION.md`
- `docs/V_CYCLE_VIGILANCE.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `skill/SKILL.md`
- `method/workflows/v-cycle.family.yaml`
- `method/workflows/v-cycle.stages.yaml`
- `method/policies/v-cycle-vigilance.yaml`
- `schemas/v-cycle-trace.schema.json`
- `schemas/human-review-receipt.schema.json`
- `examples/stage-request.yaml`
