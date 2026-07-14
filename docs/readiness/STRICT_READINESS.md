# Strict Readiness

Strict readiness is the release and CI gate for the central `modeller-agents` runtime. It is intentionally stricter than the advisory local doctor check: local development may tolerate planned vendors, draft reference packs, sibling schema fallback, and unproven backend wiring; release readiness must not.

Installing with `--include-runtime-assets` copies central runtime assets under `.modeller/runtime/` in a target project for local orchestration. It does not satisfy strict readiness by itself: copied draft packs remain draft, copied vendor registry entries remain planned/unpinned, and copied backend registry entries remain unproven until the backend smoke passes.

Run all commands from the workspace root:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict --json
```

The strict gate is clear only when `doctor --strict` exits with code `0` and reports no `error:` lines. Warnings may still identify local operator notes, but every blocker below must be remediated before release.

Use `--json` for CI and orchestrators. The payload includes `readiness_blockers[]` entries with stable `code`, `message`, `path`, and `remediation` fields. Current blocker codes are:

- `reference-pack-not-active`
- `backend-not-active`
- `backend-contract-unpinned`
- `vendor-not-synced`
- `vendor-not-pinned`
- `schema-sibling-fallback`

## Vendor Blockers

Strict readiness fails when any entry in `vendors.toml` is still planned or is not pinned to an immutable revision.

Current blockers are exposed by:

```powershell
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
python -m modeller.cli sync --root AItlantis\modeller-agents modeller-memory
python -m modeller.cli sync --root AItlantis\modeller-agents modeller-pipelines
```

The `sync` command prints the exact `git subtree pull` command for each vendor. It does not execute the sync. The operator must confirm the remote and ref, run the printed command, and then update `vendors.toml`.

A vendor blocker is remediated only when all of these conditions are true:

- the vendor content exists under the configured `prefix`, which must stay under `vendor/`;
- `status` is no longer `planned`;
- `pinned` records the immutable revision that was actually synced;
- `writable = false` remains unchanged;
- `doctor --strict` no longer reports `strict readiness requires vendor <name> to be synced, not planned`;
- `doctor --strict` no longer reports `strict readiness requires vendor <name> to be pinned`.

Do not mark a vendor ready based only on a branch name such as `main` or `contract-v1.0`. The pin must identify the immutable synced revision.

## Reference Pack Blockers

Strict readiness fails when any reference pack selected by a bundle is not active.

Expose the current state with:

```powershell
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
```

The blocker text is:

```text
strict readiness requires reference pack <path> to be active
```

A reference pack blocker is remediated only when all of these conditions are true:

- every bundle-referenced pack exists under `reference-packs/`;
- each referenced pack has valid TOML and the required shape;
- the union of selected reference packs authorizes every central skill that its bundle selects;
- each referenced pack has `status = "active"`;
- any draft-only open decisions have either been closed or explicitly moved out of the release scope;
- `doctor --strict` no longer reports a reference pack active-status error.

Unused draft packs may remain visible during development, but a release bundle must not depend on them.

## Sibling Schema Fallback Blocker

Strict readiness fails when contract schemas are resolved from the sibling checkout instead of the vendored contract authority.

Expose the active schema source with:

```powershell
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
```

The blocker text is:

```text
strict readiness requires vendored modeller-pipelines schemas, not sibling fallback: <path>
```

The schema lookup order is:

1. `AItlantis\modeller-agents\vendor\modeller-pipelines\contracts\schemas`
2. sibling fallback `AItlantis\modeller-pipelines\contracts\schemas`

The fallback is acceptable for local development only. A schema fallback blocker is remediated only when all of these conditions are true:

- `vendor/modeller-pipelines/contracts/schemas` exists inside `modeller-agents`;
- the vendored schema directory includes `backend.schema.json`, `pipeline.schema.json`, `result.schema.json`, `run-config.schema.json`, and `step-result.schema.json`;
- `vendors.toml` pins `modeller-pipelines` to the immutable revision that supplied those schemas;
- `doctor --strict` no longer reports sibling fallback.

Use the vendor sync planner to get the subtree command:

```powershell
python -m modeller.cli sync --root AItlantis\modeller-agents modeller-pipelines
```

## Real Backend Smoke Blocker

Strict readiness for a runtime backend is not satisfied by validating a fixture or by importing backend implementation code. The smoke must execute the backend through its declared contract seam.

Strict doctor also fails while a backend registry entry is still `status = "planned"`. That blocker is reported as `backend-not-active`. A backend may be marked active only after the manifest and smoke evidence below exist.

First confirm the backend manifest wiring:

```powershell
python -m modeller.cli backends --root AItlantis\modeller-agents --check aimsun-psp
```

If the backend root is not configured, either pass it directly to `run` or create `backends.local.toml` from the example and set the local path for the backend id.

Run the backend smoke through `backend.json.runner.command`:

```powershell
python -m modeller.cli run --root AItlantis\modeller-agents aimsun-psp <pipeline-id> --config <path\to\config.yml> --run-dir <path\to\run-dir> --backend-root <path\to\backend>
```

The smoke blocker is remediated only when all of these conditions are true:

- the backend is registered in `backends.toml`;
- the backend root contains `backend.json`;
- `backend.json.contract_version` matches the registry `expected_contract`;
- the requested pipeline id is declared in `backend.json.pipelines`;
- the command executed is the backend's declared `runner.command` plus `run <pipeline-id> --config <cfg> --run-dir <dir>`;
- the backend process exits with code `0`;
- the final non-empty stdout line is the absolute path to `result.json`;
- `result.json` validates against the vendored `result.schema.json`;
- `result.json.backend_id`, `contract_version`, and `pipeline_id` match the expected backend, contract, and pipeline;
- `result.json.status` is `success`;
- successful results include at least one step and at least one artifact;
- every artifact path in the result is relative to the run directory.

For `aimsun-psp`, the local reference pack currently identifies `seam_smoke` as the Aimsun-free smoke pipeline. Use the actual backend manifest as the source of truth for the pipeline id accepted by `modeller.cli run`.

## Release Checklist

Before calling the central runtime ready, collect these checks in the release notes:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
python -m modeller.cli backends --root AItlantis\modeller-agents --check aimsun-psp
python -m modeller.cli run --root AItlantis\modeller-agents aimsun-psp <pipeline-id> --config <path\to\config.yml> --run-dir <path\to\run-dir> --backend-root <path\to\backend>
```

Strict readiness is complete only when the strict doctor passes and the real backend smoke returns `backend run: OK`.
