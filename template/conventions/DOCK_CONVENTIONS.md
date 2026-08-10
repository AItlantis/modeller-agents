# Dock Conventions

These conventions apply to any conforming pipeline backend that also registers
one or more QtDock artefacts (`backend.json`'s `docks[]`). They apply on top
of `CONVENTIONS.md`; they do not replace it.

## 1. Copy-don't-import the dock library

`docks/lib/` ships **copy-don't-import**, exactly like `runner/minirunner.py`
(`CONVENTIONS.md §4`). Each `lib/*.py` file and the launcher carry a "COPY
THIS FILE — never import it across repos" header. When you copy `docks/` into
your backend, you own every file in it — edit freely, but never import it
back from `modeller-pipelines` or from another backend.

## 2. `dock_key` versioning

Every dock is registered under a stable, versioned `dock_key` matching
`^[a-z0-9]([a-z0-9_.-]*[a-z0-9])?\.v[0-9]+$`, e.g. `"<backend_id>.<dock_id>.v1"`.
Bump the trailing `.vN` when a dock's widget class changes in a way that
should not be transparently reused by an already-open instance (rare — most
changes should go through `reset_state()` instead). The `dock_key` literal in
the launcher MUST equal the `dock_key` declared in `backend.json` — drift
between the two is a conformance failure (`test_dock_source.py`).

## 3. Info doc requirement

Every dock ships a documentation file (its manifest `doc` field) and exposes
an in-dock **Info** control that renders it. Keep this file honest: it is
what an operator sees when they click Info, not an internal design note.

## 4. DEBUG-purge, never blanket reload

A dock MAY support a `DEBUG` environment-gated reimport for local iteration
(see `run_dock_template.py`). It MUST be purge-based (drop from
`sys.modules`, detach the stale child attribute, `importlib.invalidate_caches()`)
and scoped to the dock's own package. It MUST NOT reload `lib/` in a way that
rebinds a class object still referenced by a live dock instance across
*different* docks, and MUST NOT ever call `importlib.reload()` on a shared or
framework prefix. This is the DSM crash fix, generalized: reloading in place
rebinds a class while the old instance survives, which breaks reload-tolerant
reuse and can crash the host.

## 5. `qt_compat` rule

All Qt access — in the launcher, the widget, the info dialog, and every
`lib/*.py` file — goes through `docks/lib/qt_compat.py`. No dock module
imports `PyQt5`, `PyQt6`, `PySide2`, or `PySide6` directly. The launcher's Qt
imports are additionally lazy (inside `run()`), so the module can be
statically inspected with no Qt binding installed at all.

## 6. Naming

- `dock_id`: lowercase slug, hyphens/underscores allowed, no spaces.
- Dock widget class: `<Name>Dock` (e.g. `DemoDock`), subclassing the copied
  `BaseDockWidget`.
- Launcher module: `run_<dock_id>_dock.py` in a real backend (the template's
  is named `run_dock_template.py` to match its own filename convention).

## 7. No `result.json`

A dock is not a pipeline. It never writes `result.json` and is not subject to
`RESULT_CONTRACT.md`. See `DOCK_CONTRACT.md §10`.
