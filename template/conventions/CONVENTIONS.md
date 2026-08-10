# Pipeline Repo Conventions

These conventions apply to any conforming pipeline backend repo.

## 1. Thin step scripts

Each step module exposes exactly one function:

    def run(config: dict, step_params: dict, run_context: dict) -> dict

- Heavy imports go **inside** `run()`, not at module load. This keeps import time fast and avoids circular dependencies.
- `config` — the full pipeline config dict (from the config yml).
- `step_params` — the step's `params` block from the pipeline yml, merged with any per-run overrides.
- `run_context` — `{"run_dir": str, "run_id": str, "pipeline_id": str}`.
- Returns a dict validating against `step-result.schema.json`. **Never raise across the seam** — catch exceptions, return `{"status": "failed", ...}`.

## 2. Reuse-first / second-use test

A helper is promoted from an inline function into `shared/` only when a **second concrete consumer** exists or is concretely planned. Do not anticipate reuse. One consumer → keep it local. Two consumers → promote, leaving a re-export shim at the original location.

## 3. `shared/` rules

- `shared/` is **backend-LOCAL**. It is never imported by another repo.
- Starts near-empty (`result_builder.py` only). Grows only when the second-use test is met.
- If `shared/` starts importing from `pipelines/`, you have a layering violation.

## 4. `runner/minirunner.py`

- **Copy, never import.** The file header says so. Copying drift between repos is the system working.
- Hard 200-line CI budget. Zero extension points. No packaging metadata.
- When you copy it to a new backend, you own it — edit freely, but do not import it from `modeller-pipelines`.

## 5. `contract.lock`

Update by running:

    echo "modeller-pipelines contract-v<version> <sha>" > contract.lock

when pinning to a new contract version. The lock file is one line. CI fetches `modeller-pipelines` at this pin and runs the conformance kit.

## 6. Naming

- `pipeline_id`: lowercase slug, hyphens allowed (`trip-summary`), no spaces.
- Step `id`: integers starting at 1.
- Step module names: `<N>_<verb>_<noun>.py` (e.g. `1_acquire_trips.py`).
- Config dataclass: `<PipelineName>Config` with `from_yaml(path)` classmethod and `to_dict()` method.

## 7. Writes go to the run dir

Steps MUST write all outputs under `run_context["run_dir"]`. No writes to the source tree, no writes to absolute paths outside the run dir.

## 8. Optional steps

An optional step (`required: false`) that cannot run MUST return `{"status": "skipped", ...}` — not raise, not exit. The runner accumulates a `"partial"` status when optional steps are skipped.
