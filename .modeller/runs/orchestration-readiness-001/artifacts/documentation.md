---
workflow_id: modeller-agents-build
run_id: orchestration-readiness-001
artifact: documentation
step: documentation
status: complete
updated_by: documenter
updated_at: 2026-07-10T20:57:33Z
---


# Documentation

## Purpose

Record documentation updates and runbook behavior.
## Evidence

Evidence: updated docs include README, docs/COMMANDS.md, and docs/workflows/DETERMINISTIC_WORKFLOW.md; runbook documents strict doctor, central runtime install model, path-safe run IDs, current-step artifact completion, owners, required terms, and subagent evidence handling.
## Decisions Or Outputs

Output: documentation accepted with updated docs and runbook evidence.
## Verification

Verification: docs were checked against implemented CLI behavior for doctor --strict and workflow complete-artifact.

## Closure Update - 2026-07-11

Updated docs include the new global architecture/workflow overview at `docs/architecture/ARCHITECTURE_AND_WORKFLOW.md`, the README pointer to that overview, and the modelling-knowledge registry, repository maps, decisions, development plan, migration plan, baselines, inventories, and stale finding record that refer to `modeller-agents`.

Runbook impact: the global overview now explains the central runtime shape, install model, command surfaces, routing invariants, deterministic workflow artifacts, backend contract seam, readiness modes, current evidence commands, residual risks, and next actions.
