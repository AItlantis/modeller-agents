---
name: pipeline-review
description: Review a pipeline backend implementation for contract correctness across static, runtime-contract, step-discipline, and shared-discipline tiers, returning ranked findings. Use to review a pipeline backend before handoff or as part of backend-align.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Pipeline Review

Read-only assessment. Return ranked findings. Compose `backend-contract-check` for the static validation tier.

Load `reference-packs/modeller-pipelines.toml` for schema paths and invariants.

## Static tier (compose `backend-contract-check`)

1. `backend.json` validates against `backend.schema.json`.
2. `contract.lock` is present and parses as `modeller-pipelines contract-v<version> <sha>`.
3. Every pipeline yml validates against `pipeline.schema.json`.

## Runtime-contract tier

4. `minirunner.py` is ≤200 lines, stdlib-only, and keeps the `COPY THIS FILE` header.
5. `run` writes `result.json` as its last act and prints its absolute path as the final stdout line.
6. `describe` exits 0 and emits a parseable `backend.json`.

## Step-discipline tier

7. Each step returns a result dict and never raises across the seam.
8. Every artifact path in `result.json` is relative to the run dir.
9. Failed step results carry a non-empty `error` field.

## Shared-discipline tier

10. `result_builder.py` is a local copy, not imported from `modeller-pipelines`.

## Backend-specific tier

11. Apply the target backend's reference pack invariants as additional review criteria.

## Output

Rank findings: boundary violations > behaviour bugs > missing verification > stale docs. State runtime checks not exercised when none were run.
