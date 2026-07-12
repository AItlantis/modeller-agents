---
name: backend-align
description: Align an existing pipeline backend to the current contract version by comparing its contract.lock, validating its artifacts against the modeller-pipelines schemas, and producing an ordered fix list. Use when a backend may have drifted from the pinned contract.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Backend Align

Align an existing backend to the current contract version. Read-and-report first; apply fixes only after `source-boundary-check`. Compose `pipeline-review` for the gap report.

Load `reference-packs/modeller-pipelines.toml` for schema paths and the vendor version file.

## Steps

1. Read `contract.lock` and parse `modeller-pipelines contract-v<version> <sha>`.
2. Resolve the current contract version from `vendor/modeller-pipelines/contracts/VERSION` (or sibling checkout). Record the version delta.
3. Compose `pipeline-review` to produce the full conformance gap report.
4. Check if `minirunner.py` matches the copy in the resolved checkout at the pinned ref (sha compare). Report staleness if it differs.
5. Produce an ordered fix list: version bump in `contract.lock` → schema-invalid fields → absolute artifact paths → stale runner → missing required files. Lowest-risk first.
6. Run `source-boundary-check` before any write. Apply fixes only inside the backend repository.
7. After fixes, run `pipeline-smoke` to verify the aligned backend end-to-end.

Repository-specific migration details belong in the backend's reference pack.
