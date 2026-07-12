---
name: pipeline-smoke
description: Run a backend's declared smoke pipeline, validate the emitted result.json against the contract schema, and verify all artifact paths are run-dir-relative. Use as a post-scaffold, post-align, or post-fix verification step.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Pipeline Smoke

Verify a backend end-to-end using its declared `smoke_pipeline`. Invokes via the CLI seam; validates the output contract.

Load `reference-packs/modeller-pipelines.toml` for the CLI seam and result schema path.

## Steps

1. Compose `backend-contract-check`: resolve the backend id in `backends.toml`, read `backend.json`, validate the manifest.
2. Read `backend.json` for `smoke_pipeline` and `runner.command`.
3. Run: `<runner.command> run <smoke_pipeline> --config <smoke_config> --run-dir <run_dir>`.
4. Assert exit code 0 for success, non-zero for failure — and verify the exit code matches the written `result.json` status.
5. Assert `result.json` is written at `<run_dir>/result.json` regardless of exit code.
6. Validate `result.json` against `result.schema.json` from the resolved modeller-pipelines vendor checkout.
7. Assert every artifact path in `result.json` (run-level and step-level) is relative to the run dir.
8. Report: overall status, step statuses, any artifact path violations, and schema validation errors.

If `smoke_pipeline` requires a licensed backend tool (e.g. Aimsun), note it and advise running a tool-free seam smoke instead.
