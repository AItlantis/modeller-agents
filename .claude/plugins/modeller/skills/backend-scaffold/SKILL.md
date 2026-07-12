---
name: backend-scaffold
description: Scaffold a new conforming pipeline backend from scratch inside its owning source repository. Use when a repository needs a new modeller-pipelines backend with backend.json, contract.lock, pipeline yml, step stubs, and runner scaffolded against the current contract.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Backend Scaffold

Scaffold a new conforming pipeline backend. All writes go inside the owning source repository, never inside `modeller-agents`.

Load `reference-packs/modeller-pipelines.toml` for schema paths, the resolved vendor prefix, and invariants.

## Steps

1. Run `source-boundary-check`. Confirm the target repository owns the backend. Block if `modeller-agents` is the target.
2. Run `workflow` to gate the multi-step change: recon → plan → source-boundary → execute → verify.
3. Elicit: `backend_id`, pipeline names, ordered step names, `runner.command`, `runner.interpreter`, `runner.platform`.
4. Resolve the modeller-pipelines checkout via `vendor/modeller-pipelines` (vendors.toml pin) or a confirmed sibling checkout. Hard-fail if neither resolves — never embed contract content.
5. Create `backend.json` at the backend repo root.
6. Create `contract.lock` (one line: `modeller-pipelines contract-v<version> <sha>`) pinned to the resolved checkout's `contracts/VERSION` and its git sha.
7. Create one `<name>.pipeline.yml` per pipeline, using `pipeline.schema.json` from the resolved checkout as the authoritative field reference.
8. Create one step stub per step name. Each stub returns an ActionResult-shaped dict and never raises across the seam. Apply any backend-specific step conventions from the target backend's reference pack.
9. Copy `result_builder.py` from the resolved checkout's `template/shared/` into the backend repo as a local file.
10. Copy `minirunner.py` from the resolved checkout's `template/runner/` into the backend repo. Keep the `COPY THIS FILE — never import it across repos` header intact.
11. Copy the conformance kit from the resolved checkout's `conformance/` as a reference for the backend's own tests. Invoke static tier: `pytest <conformance-root> --backend-root <root> --backend-cmd "<cmd>" --skip-runtime`.
12. Run `pipeline-smoke` to verify the scaffold end-to-end.
13. Report created paths, pinned sha, and any failing conformance check.

Repository-specific step conventions and invariants belong in reference packs.
