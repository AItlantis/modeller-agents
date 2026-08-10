# Result Contract - Normative Specification

**Contract version:** 1.2
**Status:** normative

## Run-level result (`result.json`)

Every `run` invocation MUST produce a `result.json` in the run dir. Its shape MUST validate against `contracts/schemas/result.schema.json`.

### Required fields

| Field | Type | Description |
|---|---|---|
| `contract_version` | string | Must match the backend's declared `contract_version` |
| `backend_id` | string | Must match `backend.json:backend_id` |
| `pipeline_id` | string | The pipeline that was run |
| `pipeline_version` | string | Semver of the pipeline definition |
| `run_id` | string | Unique run identifier (UUID or timestamp slug) |
| `status` | enum | `"success"` \| `"partial"` \| `"failed"` |
| `timestamps` | object | `{"started_at": string, "completed_at": string}` as ISO 8601 timestamps |
| `config_path` | string | Path to the config file used |
| `steps` | array | Per-step results (see Step Result below) |
| `artifacts` | array | Run-level artifact records; paths MUST be relative to the run dir |

### Optional fields

`metrics`, `logs`, `error` - all SHOULD be present; absent means empty/null.

## Status semantics

- `"success"` - all required steps succeeded.
- `"partial"` - either: (a) all **required** steps succeeded; at least one optional step failed or was skipped due to error (matches "best-effort" semantics, e.g. decoration steps); or (b) added 1.2: a required step was gate-skipped by design (`skip_reason: "gate_condition_unmet"`, `PIPELINE_DEFINITION.md §4`'s conditional gates) and no required step failed. A by-design gate-skip of a required step is not a failure — the run did everything it was permitted to do; nothing failed; a required step was deliberately withheld pending a condition (e.g. an unapproved import). `"partial"` communicates this without inventing a fourth run-status token.
- `"failed"` - at least one required step failed or was invoked-but-not-gate-skipped-and-absent (an unexplained missing required step, not a gate skip), or the run could not start.

### Normative rule — every declared step MUST be accounted for (added 1.2)

The orchestrator MUST synthesize a step-result entry (`status: "skipped"`, `skip_reason:
"gate_condition_unmet"`) for every step whose `pipeline.schema.json` `gates[].condition` was not
met, even though that step's `run()` was never invoked (see `STEP_INTERFACE.md §2.3a`). A required
step absent from `steps[]` with no such synthesized entry is a conformance defect: the runner MUST
NOT allow a required step to simply be missing from the envelope. Absence without a corresponding
`skipped` entry indicates a runner crash mid-orchestration and MUST resolve to run-level `status:
"failed"`.

## Step result shape

Each entry in `steps[]` MUST validate against `contracts/schemas/step-result.schema.json`.

| Field | Type | Description |
|---|---|---|
| `status` | enum | `"success"` \| `"failed"` \| `"skipped"` |
| `step_id` | integer or string | Matches the `id` in the pipeline yml (string form is a substep id, e.g. `"6b"`, added 1.2) |
| `step_name` | string | Matches the `name` in the pipeline yml |
| `message` | string | Human-readable summary |
| `duration_s` | number | Wall-clock seconds |
| `cached` | boolean | True if the step was served from cache |
| `artifacts` | array | `[{"name": string, "path": string, "type": string}]` - relative paths; `type` is an optional free-string hint, added 1.2 |
| `metrics` | object | Arbitrary key-value metrics |
| `error` | object\|null | `{"type", "message", "traceback_path"}` on failure |
| `skip_reason` | string, optional | Added 1.2. One of `"optional_input_absent"`, `"gate_condition_unmet"`, `"cache_upstream_skip"`. Only meaningful when `status` is `"skipped"`. |

## Artifact path rule

ALL artifact paths in `result.json` (both run-level and step-level) MUST be **relative to the run dir root**. Absolute paths are a conformance failure. This rule makes run dirs portable across machines.

## Artifact type hint (added 1.2)

An artifact record MAY carry an optional `type` field (`{"name": string, "path": string, "type":
string}`), a free-string hint such as `"GeoPackage"`, `"application/geopackage+sqlite3"`,
`"text/html"`, or `"ANG"`. It is deliberately a free string rather than a closed enum or a strict
MIME-type format: there is no registered IANA media type for several real artifact kinds (e.g.
Aimsun's `.ang` model files, GeoPackage containers), so a strict format would force an unhelpful
`application/octet-stream` for exactly the types that most need a hint, and a closed enum would need
editing every time a new artifact type appears. `type` is a hint, not a contract: a UI or agent MUST
fall back to path-extension inference when it is absent, preserving pre-1.2 behavior exactly. A
backend SHOULD populate it when the value is already known (e.g. a pipeline's own `outputs[].type`
declaration, `PIPELINE_DEFINITION.md §6`) rather than leaving a UI to guess.

## Failure result shape

Even a failed run MUST produce a structurally valid `result.json`. The `error` field at the run level captures the top-level failure; individual step errors are in their step entries.

## Optional incremental status file: `<run_dir>/status.json` (added 1.2)

A backend MAY (not MUST) write and update `<run_dir>/status.json` after each step transition, for a
UI to poll at a UI-chosen interval during a long-running `run` invocation, without needing a live
connection into the backend process (the CLI seam's subprocess boundary stays exactly as documented
in `CLI_SEAM.md`; this is a durable, externally-pollable file, not a stream). Shape:

```json
{
  "contract_version": "1.2",
  "run_id": "...",
  "current_step_id": 3,
  "completed_step_ids": [1, 2],
  "skipped_step_ids": [],
  "updated_at": "2026-07-25T14:03:11Z"
}
```

`skipped_step_ids` (added 1.2, alongside `current_step_id`/`completed_step_ids`) lists step ids the
orchestrator has already gate-skipped (`STEP_INTERFACE.md §2.3a`) as of `updated_at`, so a polling UI
can render "step 10 will not run this time" rather than showing it as merely "not yet reached."

A UI that does not find `status.json` MUST fall back to today's behavior (render "running..." until
`result.json` appears). This file is written on a best-effort basis and is never authoritative —
only the terminal `result.json` is; a UI MUST NOT treat `status.json`'s absence, staleness, or
disagreement with the eventual `result.json` as an error.

## What agents consume

`modeller-agents` consumes **only** `result.json` plus the declared artifact files at their relative paths. It does not read any other file from the run dir. Backend-internal logs, intermediate files, or debug outputs are invisible to the host. `status.json`, when present, is consumed only by a UI polling loop, never by `modeller-agents`' own result-processing path.
