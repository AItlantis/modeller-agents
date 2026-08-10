# Dock Contract — Normative Specification

**Contract version:** 1.2
**Status:** normative
**Schema:** `contracts/schemas/dock.schema.json`

This document is normative. The keywords MUST, SHALL, SHOULD, MAY, and MUST NOT are used as defined
in RFC 2119.

A conforming backend MAY register zero or more **QtDock** artefacts alongside its pipelines. A dock
is an interactive Aimsun UI panel launched **in-process** by the Aimsun Script Manager — not a
subprocess — so its contract is the launcher entry-point shape plus its lifecycle, not stdin/stdout.

---

## 1. Entry-point seam

A dock is declared in `backend.json`'s `docks[]` array (see `contracts/schemas/backend.schema.json`
and the standalone `contracts/schemas/dock.schema.json`). Each entry's `entry_module` MUST resolve to
a Python module that exposes, at module scope:

```python
def run(model, _argv=None) -> bool:
    ...
```

- `model` is the Aimsun `GKModel` object injected by the Script Manager.
- The function MUST return `True` on successful attach and `False` otherwise.
- The function MUST NOT raise across this boundary. Any failure MUST be caught, logged, and reported
  via a `False` return.

## 2. Import-safety — the linchpin for Qt-free conformance

Importing the launcher module MUST NOT:

- construct any Qt object,
- require a running `QApplication`, or
- import a Qt binding (`PyQt5`, `PyQt6`, `PySide2`, `PySide6`) at module scope.

All Qt/widget imports MUST be lazy — performed inside `run()`, mirroring `STEP_INTERFACE.md §2.1`'s
lazy-import rule for heavy dependencies. This is what lets the conformance kit import and inspect the
launcher module with no Qt binding installed, exactly as static tests inspect a pipeline step module
without executing it.

## 3. Single-instance persistence

A dock MUST be registered under a stable, versioned `dock_key` (pattern
`^[a-z0-9]([a-z0-9_.-]*[a-z0-9])?\.v[0-9]+$`, e.g. `"template.demo.v1"`) on a process-wide registry.
Re-launching the same dock MUST reuse the one live instance rather than creating a duplicate. The
registry MUST be scoped to the running process (e.g. a `QApplication` property), never to a file or
external store.

## 4. Reload-tolerant reuse

Reuse detection MUST NOT rely on class-object identity (`isinstance`) alone. Aimsun runs every script
in one shared interpreter, so a DEBUG reimport (§6) can rebind the dock's class to a new class object
between launches while a previously stored instance still references the old one. A strict
`isinstance` check then fails, a duplicate dock is created, and the previous instance is orphaned
while still attached to the main window — a crash vector.

Reuse detection MUST instead match by the stored instance's class **qualified name**
(`module.QualifiedName`) against the incoming dock class's qualified name. A stored instance that is
not reusable — a different class, or one whose underlying UI object has already been deleted — MUST
be closed and detached from the host window before a fresh instance is created. No non-matching or
deleted instance may be left orphaned and attached.

## 5. Reset on reuse

A dock class MUST implement `reset_state()`. The loader MUST call it when reusing an existing
instance, before showing it, so the dock returns to a clean state rather than carrying over stale
data from its previous invocation.

## 6. Qt access

UI code MUST import Qt only through a compat shim (PySide6 → PyQt6 → PyQt5 fallback chain); direct
`PyQt5`/`PyQt6`/`PySide2`/`PySide6` imports at module scope anywhere in the dock's own modules are a
contract violation. As stated in §2, the GUI toolkit import in the launcher itself MUST be lazy
(inside `run()`).

## 7. DEBUG reimport

A dock MAY support a development-only reimport switch for iterating on dock code between Script
Manager runs without restarting Aimsun. If present, it MUST be:

- **env-gated** — off by default, enabled only via an explicit environment variable (see the
  optional `debug_env` manifest field),
- **purge-based** — dropping targeted modules from `sys.modules` (and detaching stale child
  attributes from their parent packages) rather than calling `importlib.reload()` in place, and
- **scoped to the dock's own package** — the purge list (see the optional `reload_prefixes` manifest
  field) MUST NOT include shared/framework module prefixes.

Reloading shared or framework modules in place rebinds class objects while a live dock instance in
the same interpreter still references the old class — this breaks reuse (§4) and can crash the host.
`importlib.reload(...)` MUST NOT appear in the launcher module.

## 8. Documentation

A dock MUST ship a documentation file (its `doc` manifest field, e.g. a `README.md` alongside the
dock's widget module) and MUST expose an in-dock **Info** affordance (e.g. a button) that renders
that file's content to the user.

## 9. Persistence discipline

Any state a dock persists across sessions (filters, geometry, last-used values) MUST be written to a
per-model config location, and the dock MUST tolerate that location's absence — falling back to fresh
defaults rather than failing. A dock MUST NOT write persisted state to a location shared across
different Aimsun models.

## 10. No `result.json`

Docks are interactive UI panels, not batch pipeline runs. A dock invocation MUST NOT produce a
`result.json` and is not subject to `RESULT_CONTRACT.md`. This absence is itself a normative
statement: a dock's seam is its lifecycle (attach, reuse, reset, close), not a machine-readable
output file.

---

## What is out of contract

The dock's actual domain work — what it displays, what domain data it reads, its internal threading
model, and any presenter/dispatch pattern it uses internally — is explicitly NOT part of this
contract, consistent with `STEP_INTERFACE.md §4`'s "dispatch is out of contract" rule. The contract
covers only what crosses the seam: the `run(model, _argv=None) -> bool` entry point, the single-
instance/reload-tolerant lifecycle, the Qt-import-safety rule, and the documentation requirement.
