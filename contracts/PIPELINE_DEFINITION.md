# Pipeline Definition — Normative Specification

**Contract version:** 1.2
**Schema:** `contracts/schemas/pipeline.schema.json`

This document is normative. The keywords MUST, SHALL, SHOULD, MAY, and MUST NOT are used as defined
in RFC 2119.

---

## 1. File format

A pipeline definition MUST be a YAML file whose name ends in `.pipeline.yml`. It MUST validate
against `contracts/schemas/pipeline.schema.json` for the declared contract version.

---

## 2. Required top-level fields

| Field           | Type   | Rules                                                       |
|----------------|--------|-------------------------------------------------------------|
| `pipeline_id`   | string | Slug — lowercase alphanumeric and hyphens only; no spaces. Must be unique within the backend's registered pipelines. |
| `pipeline_name` | string | Human-readable display name. No uniqueness constraint.      |
| `version`       | string | Semver (MAJOR.MINOR.PATCH). Pipeline logic version, independent of contract version. |
| `description`   | string | One-paragraph description of what the pipeline does.        |
| `domain`        | string | Free string in v1 (e.g. `"transport"`, `"logistics"`). No controlled vocabulary yet. |

---

## 3. `steps[]`

`steps` MUST be a non-empty list. Each step object MUST contain:

| Field           | Type    | Rules                                                                 |
|----------------|---------|-----------------------------------------------------------------------|
| `id`            | integer or string | Unique within the pipeline. Either a positive 1-based integer, or a substep string matching `^[0-9]+[a-z]?$` (e.g. `"6b"`, a lettered substep of step 6). MUST NOT be zero or negative when integer. |
| `name`          | string  | Slug (lowercase alphanumeric and underscores). Unique within pipeline. Used as key in param overrides. |
| `title`         | string  | Human-readable step label.                                            |
| `action_module` | string  | Dotted Python module path (e.g. `my_pkg.actions.import_data`). MUST be importable in the backend environment. |
| `required`      | boolean | Default `true`. If `false`, a failure yields `partial` run status rather than `failed`. |

Each step object MAY contain:

| Field           | Type   | Rules                                                                  |
|----------------|--------|------------------------------------------------------------------------|
| `cache_inputs`  | array  | List of input key names whose values are hashed for cache keying.      |
| `params`        | object | Static default parameters merged with per-run overrides before dispatch. |
| `enabled`       | boolean | Default `true`. A step with `enabled: false` is declared but MUST NOT be dispatched. It does not count toward required/optional step tallying. |

### Normative rule — step ids are opaque

No step `id` value carries reserved meaning. The runner MUST NOT special-case any id, integer or
string. Step order and dependency are expressed exclusively via `gates[]`.

### Note — substep ids (added 1.2)

`id` MAY be a string matching `^[0-9]+[a-z]?$` (e.g. `"6b"`) to express a lettered substep of an
integer step, borrowing Dagster's op/sub-op naming convention. This is a string-pattern relaxation,
not a new nesting concept: a substep is a first-class step like any other for gating and result
purposes, it simply shares its leading digits with a sibling step by convention. Consumers that
assumed `id` is always an integer (pinned to contract version 1.1 or earlier) remain valid against
version 1.1 documents; a document using a string `id` declares itself version 1.2 or later.

### Normative rule — no undeclared-but-wired steps

Every step that the runner MAY invoke MUST appear in `steps[]`. A step absent from `steps[]` MUST
NOT be dispatched. The only exception is `enabled: false` steps, which are explicitly declared and
explicitly skipped.

---

## 4. `gates[]`

`gates` is an optional list of dependency edges and/or runtime conditions on step execution. Each
gate object:

| Field       | Type             | Rules                                                                    |
|------------|------------------|----------------------------------------------------------------------------|
| `step_id`   | integer or string | The step whose execution is gated.                                        |
| `requires`  | array of integer/string | Optional. Step ids that MUST have `status: "success"` before `step_id` runs. |
| `condition` | object           | Optional (added 1.2). See below.                                          |

A gate object MUST specify at least one of `requires` or `condition`.

The dependency-edge subgraph formed by `requires` MUST be acyclic (a DAG). A pipeline definition
with a cycle MUST be rejected at validation time, not at run time.

### Normative rule — conditional gates (added 1.2)

A gate MAY carry a `condition` object with the shape `{"input": string, "equals": boolean | string
| number | null}`. When present, the runner MUST NOT dispatch `step_id` unless
`config.inputs[condition.input] == condition.equals`. This is a single-key-equality predicate,
deliberately not a general expression language — richer predicates (inequality, multi-key,
cross-step-result conditions) are out of scope until a second real backend needs them (the
second-use-test discipline in `docs/ADR/ADR-0002-contract-versioning.md`'s cultural rule).

A step gated by an unmet `condition` MUST NOT be invoked at all (contrast with `STEP_INTERFACE.md
§2.3`, where a step invokes itself and self-reports `skipped`). The runner MUST instead synthesize a
step-result entry for it with `status: "skipped"` and `skip_reason: "gate_condition_unmet"` (see
`STEP_INTERFACE.md §2.3a` and `RESULT_CONTRACT.md`), so every declared step is accounted for in
`result.json`'s `steps[]` regardless of whether its action module ever ran.

Example — an approval-gated step that only runs once a config flag is set:

```yaml
gates:
  - step_id: 10
    requires: [9]
    condition: { input: import_approved, equals: true }
```

---

## 5. `inputs`

`inputs` is an optional object with two sub-keys:

- `required`: list of input entries the pipeline MUST receive to run.
- `optional`: list of input entries the pipeline MAY receive.

Each entry is either a bare string (the input key name, type unconstrained — treated as `type: any`)
or, added in 1.2, an object `{"name": string, "type": string}` carrying a minimal free-string type
tag (e.g. `"string"`, `"path"`, `"GeoPackage"`). The bare-string form remains valid indefinitely; the
object form is a strict superset, additive under `docs/ADR/ADR-0002-contract-versioning.md`. A type
tag is advisory: it lets a conformance kit or agent-side pre-flight validate `config["inputs"]`
against a pipeline's own declared shape before dispatch, but the runner MUST NOT reject an input
solely because its runtime value's apparent type does not match the tag (the tag is a hint, not a
strict schema).

Undeclared input keys passed via run-config SHOULD be logged as warnings and ignored.

---

## 6. `outputs[]`

`outputs` is an optional list of artifacts the pipeline promises to produce on success. Each entry is
either a bare string (the artifact name, type unconstrained) or, added in 1.2, an object
`{"name": string, "type": string}` carrying a minimal free-string type tag (e.g. `"GeoPackage"`,
`"JSON"`, `"ANG"`, `"text/html"`). The bare-string form remains valid indefinitely. This is
declarative documentation; the runner MUST NOT fail a pipeline solely because a declared output was
not produced by a step (step-level artifact presence is enforced separately). The type tag, when
present, SHOULD match the `type` hint the corresponding artifact record carries in `result.json`
(see `RESULT_CONTRACT.md`), but this is not cross-validated at the pipeline-definition level.

---

## 7. Example

```yaml
pipeline_id: trip-summary
pipeline_name: Trip Summary Pipeline
version: 1.0.0
description: >
  Imports raw demand data, aggregates by OD pair, and exports a summary report.
domain: transport

inputs:
  required:
    - demand_matrix_path
  optional:
    - filter_zone_ids

outputs:
  - summary_report.csv
  - od_aggregates.parquet

steps:
  - id: 1
    name: import_demand
    title: Import Demand Matrix
    action_module: trip_summary.actions.import_demand
    required: true
    cache_inputs:
      - demand_matrix_path
    params:
      format: csv

  - id: 2
    name: aggregate_od
    title: Aggregate OD Pairs
    action_module: trip_summary.actions.aggregate_od
    required: true
    params:
      min_trips: 10

  - id: 3
    name: export_report
    title: Export Summary Report
    action_module: trip_summary.actions.export_report
    required: true

gates:
  - step_id: 2
    requires: [1]
  - step_id: 3
    requires: [2]
```

## 8. Example — 1.2 capabilities (substep id, conditional gate, typed inputs/outputs)

```yaml
pipeline_id: geo-import
pipeline_name: Geo Import Pipeline
version: 1.0.0
description: >
  Imports a road network, lets an operator review the import plan, and only
  writes it into the target model once explicitly approved.
domain: geodata

inputs:
  required:
    - name: target_crs
      type: string
  optional:
    - name: template_model_path
      type: path

outputs:
  - name: import_gpkg
    type: GeoPackage
  - name: review_summary
    type: JSON

steps:
  - id: 6
    name: derive_rows
    title: Derive Aimsun-Ready Rows
    action_module: geo_import.actions.derive_rows
    required: true

  - id: "6b"
    name: derive_rows_geo_enrich
    title: Enrich Derived Rows With Elevation
    action_module: geo_import.actions.derive_rows_geo_enrich
    required: false

  - id: 9
    name: review_import_plan
    title: Review Import Plan
    action_module: geo_import.actions.review_import_plan
    required: true

  - id: 10
    name: import_and_save
    title: Import Into Model and Save
    action_module: geo_import.actions.import_and_save
    required: true

gates:
  - step_id: "6b"
    requires: [6]
  - step_id: 9
    requires: [6]
  - step_id: 10
    requires: [9]
    condition: { input: import_approved, equals: true }
```

Step 10 above only runs when the run-config's `inputs.import_approved` is `true`; when it is not,
the runner synthesizes a `status: "skipped"`, `skip_reason: "gate_condition_unmet"` entry for step
10 in `result.json` rather than omitting it (see `RESULT_CONTRACT.md`).
