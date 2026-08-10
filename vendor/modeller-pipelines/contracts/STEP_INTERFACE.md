# Step Interface — Normative Specification

**Contract version:** 1.2
**Schema:** `contracts/schemas/step-result.schema.json`

This document is normative. The keywords MUST, SHALL, SHOULD, MAY, and MUST NOT are used as defined
in RFC 2119.

---

## 1. Module contract

A step action module MUST expose a callable at module scope named `run` with the following
signature:

```python
def run(config: dict, step_params: dict, run_context: dict) -> dict:
    ...
```

The returned `dict` MUST validate against `contracts/schemas/step-result.schema.json`.

### Arguments

| Argument       | Content                                                                       |
|---------------|-------------------------------------------------------------------------------|
| `config`       | The full run-config dict (parsed from `--config` input). Read-only.           |
| `step_params`  | Merged params for this step: pipeline defaults overridden by per-run overrides. Read-only. |
| `run_context`  | Runner-injected context: at minimum `run_dir` (absolute path), `step_id`, `step_name`, `contract_version`. Treat as read-only. |

---

## 2. Normative behavioural requirements

### 2.1 Lazy imports

Heavy dependencies (large libraries, GUI toolkits, simulation runtimes) MUST be imported inside
`run()`, not at module load time. Module-level imports MUST be limited to the standard library and
lightweight utilities. This constraint exists because the module may be imported for inspection
(schema generation, introspection) without ever calling `run()`.

### 2.2 Filesystem discipline

A step MUST write files ONLY under the `run_context["run_dir"]` directory tree. Writing to paths
outside the run dir is forbidden. All paths carried in returned artifacts MUST be relative to the
run dir root — absolute paths in artifact records are a contract violation.

### 2.3 Optional step skip (self-reported)

If a step is declared `required: false` and it determines that it cannot meaningfully proceed (e.g.
the optional input it needs is absent), it MUST return:

```json
{
  "status": "skipped",
  "step_id": 3,
  "step_name": "export_optional_report",
  "message": "Input 'filter_zone_ids' not provided; step skipped.",
  "duration_s": 0.01,
  "cached": false,
  "artifacts": [],
  "metrics": {},
  "skip_reason": "optional_input_absent"
}
```

`skip_reason` (added 1.2) is optional and SHOULD be set when a step self-reports `skipped`; use
`"optional_input_absent"` for this case, or `"cache_upstream_skip"` when the step skips because an
upstream cache decision made its own work unnecessary. A skipped optional step MUST NOT be treated
as a failure.

### 2.3a Gate-skipped step (orchestrator-reported, added 1.2)

This is a distinct case from §2.3: a step never invoked at all because a `pipeline.schema.json`
`gates[].condition` was not met (`PIPELINE_DEFINITION.md §4`). Unlike §2.3, the step's own `run()`
never executes — there is no code inside the action module that could return anything.

The runner (not the step) MUST synthesize a step-result entry for every such step, so every step
declared in `steps[]` is accounted for in `result.json`'s `steps[]` regardless of whether it was
invoked:

```json
{
  "status": "skipped",
  "step_id": 10,
  "step_name": "import_and_save",
  "message": "Gate condition not met: import_approved != true.",
  "duration_s": 0.0,
  "cached": false,
  "artifacts": [],
  "metrics": {},
  "skip_reason": "gate_condition_unmet"
}
```

A runner that fails to synthesize this entry for a declared-but-uninvoked step produces a
`result.json` whose `steps[]` is silently incomplete — a required step that was never dispatched
must not be indistinguishable from a required step that never existed. See `RESULT_CONTRACT.md`
for how this interacts with run-level `status`.

### 2.4 Failure handling

A step that encounters an error MUST return a failure result dict. It MUST NOT raise an exception
across the `run()` call boundary. The runner does not catch exceptions as a substitute for proper
failure signalling — an unhandled exception is a runner crash, not a step failure, and bypasses the
result contract.

Swallowing errors silently (returning `status: "success"` when work failed) is explicitly
prohibited.

A failure result SHOULD include the `error` field with `type`, `message`, and optionally
`traceback_path` (a run-dir-relative path to a file containing the full traceback):

```json
{
  "status": "failed",
  "step_id": 2,
  "step_name": "aggregate_od",
  "message": "OD aggregation failed: input matrix has no rows.",
  "duration_s": 0.4,
  "cached": false,
  "artifacts": [],
  "metrics": {},
  "error": {
    "type": "ValueError",
    "message": "Input matrix has no rows.",
    "traceback_path": "logs/step2.err"
  }
}
```

### 2.5 Caching

If a step determines its outputs are already valid (cache hit), it MUST return `"cached": true` and
`"status": "success"`, and populate `artifacts` with the cached artifact records. It MUST NOT re-run
work unnecessarily. Cache validation logic is the step's responsibility; the contract does not
prescribe a caching mechanism.

---

## 3. Step-result shape

The full step-result shape validated by `contracts/schemas/step-result.schema.json`:

```json
{
  "status": "success",
  "step_id": 4,
  "step_name": "import_demand",
  "message": "Imported 142,300 trips from demand_matrix.csv.",
  "duration_s": 12.3,
  "cached": false,
  "artifacts": [
    {
      "name": "demand_matrix",
      "path": "inputs/demand_matrix.parquet"
    }
  ],
  "metrics": {
    "rows_imported": 142300,
    "zones_found": 512
  },
  "error": null
}
```

`status` MUST be one of: `"success"`, `"failed"`, `"skipped"`.

`skip_reason` (added 1.2) is optional; when present it MUST be one of `"optional_input_absent"`,
`"gate_condition_unmet"`, `"cache_upstream_skip"`. It only applies when `status` is `"skipped"`.

`artifacts[].path` MUST be relative to the run dir root. `artifacts[].type` (added 1.2) is an
optional free-string hint (e.g. `"GeoPackage"`, `"text/html"`) a UI or agent MAY use to decide how to
present an artifact without guessing from its path extension; absence MUST fall back to
extension-based inference.

`error` MUST be `null` (or omitted) when `status` is `"success"` or `"skipped"`.

---

## 4. Out of contract

How a backend dispatches to `run()` — whether via a presenter pattern, a work unit object,
an `aconsole` subprocess, a thread pool, or any other mechanism — is explicitly out of contract.
modeller-agents and the conformance kit interact only with the CLI seam (see `CLI_SEAM.md`) and
the result envelope (see `RESULT_CONTRACT.md`). They have no visibility into dispatch internals.
