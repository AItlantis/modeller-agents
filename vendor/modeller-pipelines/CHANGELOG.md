# Changelog

All notable changes to the `modeller-pipelines` contract surface are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Contract versioning follows the rules in `CONTRACT_VERSIONS.md`.

---

## [Unreleased] — contract-v1.2 (archetype-driven revision: conditional gates, gate-skip semantics, artifact/IO type hints)

Adds capabilities surfaced by `docs/CONTRACT_ARCHETYPE_ELABORATION.md`, a four-archetype (artifact
rendering, data-warehouse ingestion, model-bound simulation, geodata/staged import) audit of the three
pipelines now registered against this contract in `aimsun-psp`. All additive; no existing backend or
pipeline definition (`rendering-outputs`, `cem`, `osmimporter`, `template/trip_summary`) requires any
change to keep validating.

- `contracts/VERSION` → `1.2`. Every normative doc banner and schema `$id` bumped in lockstep
  (including `DOCK_CONTRACT.md`/`DOCK_INTERFACE.md`/`dock.schema.json`, whose content is unchanged —
  ADR-0002's single-`contract_version`-for-the-whole-surface discipline applies even when only part
  of the surface has new content, to avoid recreating the exact drift class the 1.1 hygiene fix
  corrected).
- `contracts/schemas/pipeline.schema.json` —
  - `steps[].id` and `gates[].step_id`/`gates[].requires[]` widened from `integer` to
    `["integer", "string"]` with `pattern: "^[0-9]+[a-z]?$"`, admitting lettered substep ids (e.g.
    `"6b"`). Classified as part of this coordinated minor bump specifically because the corresponding
    consumer fields (`step-result.schema.json:step_id`) are widened in the same release — widening a
    producer field without widening the matching consumer field would narrow consumer guarantees and
    reintroduce drift; see `docs/CONTRACT_ARCHETYPE_ELABORATION.md §7.1`.
  - `gates[]` items gain an optional `condition: {input: string, equals: boolean|string|number|null}`
    single-key-equality predicate; `requires` becomes optional (a gate may be pure-condition,
    pure-dependency, or both). Lets a runtime-config-gated step (e.g. an approval-gated Aimsun import)
    be expressed in the contract yml instead of silently dropped by a lossy internal-to-contract
    projection.
  - `inputs.required[]`/`inputs.optional[]`/`outputs[]` entries may now be an object
    `{"name": string, "type": string}` in addition to the existing bare string, carrying a minimal
    free-string type tag. Strict superset; existing bare-string lists validate unchanged.
- `contracts/schemas/step-result.schema.json` — `step_id` widened to `["integer", "string"]` (see
  above); new optional `skip_reason` enum (`"optional_input_absent"`, `"gate_condition_unmet"`,
  `"cache_upstream_skip"`) distinguishing a step that self-reported `skipped` from one the
  orchestrator never invoked due to an unmet gate `condition`.
- `contracts/schemas/result.schema.json` — artifact `$defs/artifact` gains an optional `type` field
  (free string, not a closed enum or strict MIME format — no registered IANA type exists for several
  real artifact kinds, e.g. GeoPackage, `.ang`).
- `contracts/schemas/backend.schema.json`, `run-config.schema.json`, `dock.schema.json` — `$id` bumped
  to `1.2`; no content change.
- `contracts/PIPELINE_DEFINITION.md` — documents substep ids, the `condition` gate (with a full
  worked example, §8), and input/output type tagging.
- `contracts/STEP_INTERFACE.md` — new §2.3a distinguishing orchestrator-synthesized gate-skips from
  step-self-reported optional skips; documents `skip_reason` and artifact `type`.
- `contracts/RESULT_CONTRACT.md` — clarifies that a by-design gate-skip of a *required* step yields
  run-level `status: "partial"`, not `"failed"` (the run did everything it was permitted to do); adds
  a normative rule that every declared step MUST be accounted for in `steps[]`, gate-skipped or not;
  documents the artifact `type` hint and the optional, best-effort `<run_dir>/status.json` incremental
  polling convention (`current_step_id`, `completed_step_ids`, `skipped_step_ids`).
- `contracts/CLI_SEAM.md` — non-normative note that a model-bound backend MAY have no fixed
  model-path config field; cross-links `docs/BACKEND_ARCHETYPES.md`.
- `docs/BACKEND_ARCHETYPES.md` — new, non-normative. Surveys four observed backend shapes (artifact
  rendering, DB ingestion, model-bound simulation, geodata/staged import) and states plainly that
  "model-bound" and "has a fixed model-path field" are independent properties.
- `docs/CONTRACT_ARCHETYPE_ELABORATION.md` — the evidence-grounded proposal this release implements;
  a companion to (not a replacement of) `docs/CONTRACT_REVISION_PROPOSAL.md`.
- `README.md`, `docs/HOW_TO_CONFORM.md` — version banners, curl/clone examples, and `contract.lock`
  examples bumped to `1.2`; fixed a stale `contract_version: "1.0"` leftover in each that predated
  even the 1.1 hygiene fix.

---

## [Unreleased] — contract-v1.1 (QtDock artefact type)

Adds a second first-class artefact type — the **QtDock** — as an additive-minor reversal of the
`docs/INTEGRATION_PLAN.md §9` "no UI/dock template" v1 cut. See `docs/ADR/ADR-0003-dock-artefact-seam.md`.

- `contracts/VERSION` → `1.1`.
- `contracts/DOCK_CONTRACT.md` — normative prose spec for the dock entry-point seam: the
  `run(model, _argv=None) -> bool` module-scope function, Qt import-safety, single-instance
  persistence, reload-tolerant reuse (matched by class qualified name, not `isinstance`), reset-on-
  reuse, the `qt_compat` shim rule, DEBUG-purge discipline, the documentation/Info requirement, and
  the "no `result.json`" rule.
- `contracts/DOCK_INTERFACE.md` — normative prose spec (not a base class) for the dock widget shape:
  constructor `(host, model, **kwargs)`, required `setup_ui()`/`reset_state()`, recommended
  `on_show`/`on_hide`/`on_close`.
- `contracts/schemas/dock.schema.json` — new standalone JSON Schema 2020-12 for a dock manifest entry
  (`dock_id`, `title`, `dock_key`, `entry_module`, `doc` required; `area`, `debug_env`,
  `reload_prefixes`, `description`, `enabled` optional).
- `contracts/schemas/backend.schema.json` — bumped `$id` to `1.1`; added optional `docks[]` (the
  identical object inlined, no cross-file `$ref`) and optional `smoke_dock`. Both additive; `docks`
  stays out of `required`, so a 1.0 pipeline-only backend still validates.
- `template/docks/` — the copyable clean dock: `run_dock_template.py` (the launcher: marker-based
  root find, env-gated DEBUG purge, lazy Qt import, `load_dock(...)` call), `demo_dock/`
  (`DemoDock` widget: browse bar + status bar + Info button + per-model persistence, `info_dialog.py`,
  `README.md`), and `lib/` (`qt_compat.py`, `base_dock.py`, `integration.py`, `persistence.py`,
  `browse_bar.py`, `status_bar.py`) — distilled from `aimsun-psp`'s hardened `shared/ui/docks/`
  library, copy-don't-import, each file carrying the "COPY THIS FILE" header and a line budget.
- `template/backend.json` — registers `demo_dock` in `docks[]`, declares `smoke_dock`, bumps
  `contract_version` to `1.1`.
- `template/contract.lock` — re-pinned to `contract-v1.1`.
- `template/conventions/DOCK_CONVENTIONS.md` — new dock-specific authoring rules.
- `template/conventions/LAYOUT.md` — optional `docks/` block added to the normative layout tree.
- `conformance/test_dock_static.py`, `conformance/test_dock_source.py` (AST-only — no Qt import),
  `conformance/test_dock_schema_consistency.py`, `conformance/test_dock_describe.py` — Qt-free dock
  conformance tests. `conformance/test_dock_import.py` — host-only, skipped without a Qt binding.
  `conformance/conftest.py` — new `backend_docks` and `qt_available` fixtures.
  `conformance/fixtures/bad_dock_manifest.json` — missing-`dock_key` fixture for validator rejection.
- `docs/ADR/ADR-0003-dock-artefact-seam.md` — records the decisions above.
- `docs/HOW_TO_CONFORM.md` — new "Conforming a dock" section.
- `docs/INTEGRATION_PLAN.md` — note that §9's "no UI/dock template" cut is superseded as of 1.1.

---

## [Unreleased] — contract-v1.0 (initial scaffold)

- `contracts/schemas/pipeline.schema.json` — JSON Schema 2020-12 for `*.pipeline.yml` pipeline
  definition files, covering pipeline metadata, step declarations, gate DAG, and declared
  inputs/outputs.
- `contracts/schemas/step-result.schema.json` — JSON Schema 2020-12 for the dict returned by a
  step's `run()` function, covering status, artifacts, metrics, and structured error envelope.
- `contracts/schemas/result.schema.json` — JSON Schema 2020-12 for the run-level `result.json`
  envelope written by the CLI runner, covering run metadata, per-step results, aggregate artifacts,
  and top-level error.
- `contracts/schemas/backend.schema.json` — JSON Schema 2020-12 for `backend.json`, the backend
  manifest that describes a backend's identity, CLI runner command, registered pipelines, smoke
  pipeline, and optional plugin path.
- `contracts/schemas/run-config.schema.json` — JSON Schema 2020-12 for the `--config` YAML/JSON
  envelope passed to the CLI `run` subcommand, covering pipeline id, optional backend id, inputs,
  and per-step param overrides.
- `contracts/PIPELINE_DEFINITION.md` — normative prose spec for `*.pipeline.yml` shape and
  validation rules.
- `contracts/STEP_INTERFACE.md` — normative prose spec for the step module `run()` interface,
  behavioural requirements, and failure-handling contract.
- `contracts/CLI_SEAM.md` — normative prose spec for the `describe` and `run` subcommands, exit-
  code contract, and stdout machine-readable protocol.
- `contracts/RESULT_CONTRACT.md` — normative prose spec for `result.json` semantics, `partial`
  status definition, artifact portability rule, and consumer constraints.
- `contracts/VERSION` — plain-text contract version file (`1.0`).
- `template/trip_summary/` — copyable example pipeline illustrating a three-step trip summary
  workflow.
- `conformance/` — black-box conformance kit that verifies any backend's CLI seam and result
  envelope against the active contract version.
