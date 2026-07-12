---
name: pipeline-fix
description: Diagnose a pipeline execution failure from result.json, classify it as contract-class or domain-class, apply contract-class fixes, and route domain-class failures to the backend's local agents with evidence. Use when a pipeline run reports partial or failed status.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Pipeline Fix

Diagnose and triage a pipeline execution failure. Contract-class fixes are applied inside the backend repository after `source-boundary-check`. Domain-class failures are routed to the backend repo's local agents — not fixed here.

Load `reference-packs/modeller-pipelines.toml` for the CLI seam and result status values. Load the target backend's reference pack for domain-specific invariants and failure symptoms.

## Steps

1. Read `result.json`: overall `status`, each step result's `status`, `step_id`, `error`, `message`.
2. Identify failed and partial steps. Partial = all required steps passed, at least one optional failed.
3. Classify each failure:
   - **contract-class**: missing `result.json`, wrong exit code, absolute artifact path, missing `error` field on failure, schema-invalid result, final stdout line not a path.
   - **domain-class**: step logic error, environment crash, backend-internal exception, interpreter-level failure.
4. Fix contract-class failures: restore `result.json` write-last rule, make artifact paths run-dir-relative, set missing `error` field, fix exit-code mismatch.
5. Route domain-class failures: produce a triage summary (step id, error type, message, traceback path if present) and direct the caller to the backend repo's local agents with that evidence. Do not attempt domain-class fixes here.
6. Apply target backend's reference pack invariants as additional classification criteria (backend-specific symptoms map to domain-class).
7. Run `source-boundary-check` before any write.
8. Suggest re-run: `<backend-cmd> run <pipeline_id> --config <cfg.yml> --run-dir <dir>`, then re-validate the emitted `result.json`.

Contract-class fixes belong here. Domain-class fixes belong in the backend's local agents.
