# Implementation Plan

## P0 — Decision and assets

Add:

```text
.claude/plugins/modeller/skills/v-cycle/SKILL.md
method/workflows/v-cycle.family.yaml
method/workflows/v-cycle.stages.yaml
method/policies/v-cycle-vigilance.yaml
schemas/v-cycle-trace.schema.json
schemas/human-review-receipt.schema.json
```

Register the skill and workflow family in the generated catalog.

## P0 — Workflow-engine extensions

Required capabilities:

```yaml
workflow_family: v-cycle
invocation_mode: full | stage | paired-review
requested_stage: null | stage-id
selected_stages: []
```

Add:

- stage dependencies and conditional artifacts;
- `entry_stage`;
- paired-stage references;
- machine and human gates;
- `awaiting-human-review` state;
- receipt validation;
- material-change invalidation.

## P1 — Companion routing

Recognize V-cycle language and map natural-language requests to stages. Present selected stage, prerequisites, paired verification, outputs and required human roles.

## P1 — Traceability

Implement `v-trace.json` and checks for orphan requirements, missing design links, untested requirements, tests without sources, failed evidence and unresolved reservations.

## P1 — Local-agent federation

Repository-local agent manifests should declare supported `v_cycle_stages`. The central workflow selects and dispatches them without copying their definitions.

## P1 — Tool plan

Resolve approved tools, data classification, permissions, external effects and fallbacks per stage.

## P2 — Benefit measurement

Store source estimates as advisory and add before/after measurement artifacts. A use case is generalized only after internal evidence and human decision.

## Target CLI

```text
modeller workflows list
modeller workflow recommend --prompt ...
modeller workflow init --family v-cycle --stage functional-specification
modeller workflow trace-check --run-id ...
modeller workflow review --run-id ... --receipt ...
modeller workflow advance --run-id ...
```

## Acceptance tests

1. Every stage can run independently.
2. Full and paired-review modes work.
3. Missing prerequisites are surfaced, not invented.
4. Human gates block without a valid receipt.
5. An artifact digest change invalidates approval.
6. AI cannot issue a human receipt.
7. External effects require explicit action approval.
8. Every ascending result links to its descending source.
9. Stage-only runs create no unrelated artifacts.
10. Estimated gains remain advisory until measured.
