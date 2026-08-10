# ADR-0003: QtDock as a second first-class artefact type

**Status:** accepted
**Date:** 2026-07-14

## Context

Through contract-v1.0, `modeller-pipelines` standardized exactly one artefact
type: a **pipeline**, expressed as a headless subprocess CLI seam (`describe`
/ `run`, see `CLI_SEAM.md`). Real backends (starting with `aimsun-psp`) also
ship a second kind of user-facing artefact: an interactive Aimsun **QtDock** —
a persistent UI panel launched in-process by the Aimsun Script Manager, not a
subprocess. `aimsun-psp` had already converged on a proven shape for this
(`shared/ui/docks/`): a `BaseDockWidget` lifecycle, a `QApplication`-property
single-instance registry, a `qt_compat` shim, per-model JSON persistence, and
a hardened DEBUG-purge launcher pattern — including a same-session fix for a
reuse bug where a stale `isinstance` check orphaned a live dock after a
module reload (the "DSM crash fix").

`docs/INTEGRATION_PLAN.md §9` had explicitly cut "no UI/dock template" from
v1 scope. This ADR records the decision to reverse that cut in contract-v1.1
and documents the shape the reversal takes.

## Decision

1. **In-process Python entry-point seam, not the subprocess seam.** A dock's
   contract is `run(model, _argv=None) -> bool` at module scope plus its
   lifecycle (attach, single-instance reuse, reset, close) — never stdin/
   stdout/exit-code. `CLI_SEAM.md` is unaffected; `DOCK_CONTRACT.md` is a
   parallel, independent seam spec for a different kind of artefact.
2. **Additive-minor, not a parallel contract surface.** Per ADR-0002, this
   ships as `contract_version` `1.1`: a new optional `docks[]` field on
   `backend.schema.json`, a new standalone `dock.schema.json`, two new
   normative `.md` specs, and new conformance tests. Nothing existing is
   renamed, removed, or made required. A 1.0 pipeline-only backend continues
   to pass conformance against 1.1 unmodified.
3. **No live Qt in conformance.** Every mandatory dock conformance test is
   static (manifest/schema validation) or AST-based (source inspection,
   never import). A dock's import-safety rule (`DOCK_CONTRACT.md §2` — Qt
   imports must be lazy, inside `run()`) is what makes this possible: the
   conformance kit can inspect a launcher module with zero Qt bindings
   installed. The one test tier that needs a live `QApplication`
   (`test_dock_import.py`) is gated behind a `qt_available` fixture and
   skips cleanly when absent, mirroring how `test_run_smoke.py` already
   gates behind `--skip-runtime`.
4. **Copy-don't-import dock library.** `template/docks/lib/` ships the same
   way `runner/minirunner.py` does: a "COPY THIS FILE — never import it
   across repos" header on every file (ADR-0001), a per-file line budget,
   and zero packaging metadata. A backend copies `docks/` wholesale,
   subclasses the widget, and owns every line from that point on.
5. **Reload-tolerant identity as a normative rule, not a template quirk.**
   `DOCK_CONTRACT.md §4` elevates the DSM crash fix — match a stored dock by
   class *qualified name*, not `isinstance`, and close any non-matching or
   deleted stored instance before creating a fresh one — to a MUST for every
   conforming dock, because the failure mode (a shared-interpreter host
   rebinding a class object mid-session, orphaning a live dock) is a
   platform property (Aimsun's single-interpreter Script Manager), not an
   aimsun-psp-specific bug.

## Consequences

**Positive:**
- A backend author gets a persistent, single-instance, reload-safe dock by
  copying one directory and subclassing one widget — the DSM lesson is now
  baked into the contract, not something each new dock has to relearn.
- CI stays Qt-free: the mandatory dock tier never needs a Qt binding, so the
  keystone self-conformance job (`conformance/` vs `template/`) still runs
  anywhere Python runs.
- `aimsun-psp`'s existing dock framework (`shared/ui/docks/`) does not need
  to change to conform — `DOCK_CONTRACT.md` describes the shape it already
  implements; conforming is a matter of declaring `docks[]` in `backend.json`
  and pointing `entry_module` at an existing launcher (see
  `docs/HOW_TO_CONFORM.md`'s new "Conforming a dock" section).

**Negative:**
- A second artefact type doubles the surface area of `contracts/` and
  `conformance/` that must be kept in sync on every future revision.
- The inlined `docks[]` object in `backend.schema.json` duplicates
  `dock.schema.json` field-for-field (no cross-file `$ref`, per the existing
  self-contained-schema rule) — a schema-consistency test
  (`test_dock_schema_consistency.py`) is the ongoing tax that keeps this from
  silently drifting.

**Mitigated by:** the schema-consistency test above; the fact that dock
conformance tests are additive files, not edits to existing pipeline tests,
so a pipeline-only backend's conformance run is unaffected (its
`backend_docks` fixture is simply `[]`).

## Anti-patterns guarded against

- Adding a live-Qt requirement to any mandatory conformance test — the
  `qt_available` fixture boundary is the line; crossing it moves a test from
  the static tier to the host-only tier.
- Layout-lint on dock file placement inside a backend — conformance
  validates the *contract* (manifest shape, seam signature, source rules),
  never the template's illustrative directory layout (repo rule D1,
  `docs/INTEGRATION_PLAN.md §9`).
- Treating the dock library as importable — `template/docks/lib/` is fenced
  the same way `minirunner.py` is: copy-don't-import header, line budgets,
  zero extension points, asserted by `template/tests/test_self_conformance.py`.
