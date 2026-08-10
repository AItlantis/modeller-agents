# Dock Interface — Normative Specification

**Contract version:** 1.2
**Schema:** `contracts/schemas/dock.schema.json`

This document is normative. The keywords MUST, SHALL, SHOULD, MAY, and MUST NOT are used as defined
in RFC 2119.

This is a **spec, not a base class**. `modeller-pipelines` ships no importable dock base class; the
template's `template/docks/lib/base_dock.py` is a copyable illustration of one way to satisfy this
spec, per ADR-0001. A backend MAY implement the shape below however it likes, provided it conforms.

---

## 1. Widget shape

A dock widget class MUST subclass the host toolkit's dock-widget class (via the Qt compat shim — see
`DOCK_CONTRACT.md §6` — never a direct Qt binding import). Its constructor MUST accept, at minimum:

```python
def __init__(self, host, model, **kwargs):
    ...
```

- `host` — the Aimsun main window the dock attaches to.
- `model` — the Aimsun `GKModel` object.
- `**kwargs` — additional keyword arguments the dock class defines for its own configuration.

This matches what a loader's `integrate_dock`-shaped call site invokes: the loader calls
`dock_class(host, model, **kwargs)`; it does not itself decide the dock's title — the subclass fixes
its own title (e.g. by passing a fixed string to its superclass constructor).

## 2. Required methods

A dock widget class MUST implement:

- **`setup_ui()`** — builds the dock's contents. Called once on first construction.
- **`reset_state()`** — returns the dock to a clean state. Called by the loader whenever an existing
  instance is reused (`DOCK_CONTRACT.md §5`) instead of constructing a fresh one.

## 3. Recommended lifecycle hooks

A dock widget class SHOULD implement:

- **`on_show()`** — called when the dock becomes visible.
- **`on_hide()`** — called when the dock is hidden. If the dock persists state (§4), this is a
  recommended place to save it.
- **`on_close()`** — called when the dock is closed. If the dock persists state, this is the
  recommended place to save it, since `on_hide` is not guaranteed to fire before teardown on every
  host code path.

## 4. Persistence

A dock that persists UI state (filters, geometry, last-used values) SHOULD do so in `on_close` and/or
`on_hide`, writing to the per-model location described in `DOCK_CONTRACT.md §9`. Loading persisted
state SHOULD happen in `setup_ui()`, tolerating the absence of any prior state.

## 5. Documentation affordance

A dock widget SHOULD expose an **Info** control (e.g. a toolbar or button labelled "Info") that opens
a view rendering the dock's documentation file (`DOCK_CONTRACT.md §8`). The rendering mechanism (a
modal dialog, an embedded panel, etc.) is not prescribed.

---

## Out of contract

Widget internals — layout choices, specific child widgets, threading model, signal/slot wiring,
presenter dispatch, and the dock's actual domain logic — are explicitly NOT part of this contract,
consistent with `PIPELINE_DEFINITION.md`'s "dispatch is out of contract" principle applied to docks.
This document constrains only the constructor shape and the four lifecycle method names above.
