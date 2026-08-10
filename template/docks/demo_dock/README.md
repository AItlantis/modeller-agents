# Demo Dock

This is the template's copyable example **QtDock** — an Aimsun UI panel that
attaches to the main window, persists across relaunches, and reloads cleanly
during development. It conforms to `contracts/DOCK_CONTRACT.md` and
`contracts/DOCK_INTERFACE.md`.

This file is what the dock's **Info** button shows. When you copy this dock
into your own backend, replace this content with your dock's own
documentation — what it does, what data it reads, and any known limitations.

## What this demo does

- A **browse bar** search box filters a small in-memory list of demo items.
- The filtered list updates live as you type.
- A **status label** reports how many items match.
- The **Info** button (the one you clicked to see this) opens this README in
  a small dialog.
- The last-used filter text is saved to a per-model JSON file when the dock
  closes, and restored the next time it opens.

## Launching it

From the Aimsun Script Manager, run `docks/run_dock_template.py`. It:

1. Locates the package root by walking up from its own file until it finds
   a folder containing `docks/run_dock_template.py` — its own marker path —
   and adds that folder to `sys.path`.
2. Optionally purges its own package's modules from `sys.modules` if the
   `DEMO_DOCK_DEBUG` environment variable is set to `1` — never touching
   `lib/` shared framework modules mid-session with a live dock attached.
3. Lazily imports Qt (via `lib/qt_compat.py`) and the `DemoDock` widget.
4. Calls `lib.integration.load_dock(...)` with the stable `dock_key`
   `"template.demo.v1"`, so relaunching the script reuses the one live dock
   instance instead of creating a duplicate.

## Copying this dock into your backend

1. Copy `docks/` (the launcher, `demo_dock/`, and `lib/`) into your backend.
2. Rename `demo_dock/` and `DemoDock` to your dock's name; keep the file
   header comments on every `lib/*.py` file and the launcher — they are
   copy-don't-import law (see `docs/ADR/ADR-0001-scaffold-not-framework.md`).
3. Replace `DEMO_ITEMS` and `_populate_list` with your real domain data.
4. Write your own `README.md` — this file's content — for the Info button.
5. Pick a new stable `dock_key` (e.g. `"<backend_id>.<dock_id>.v1"`) and
   register the dock in your `backend.json`'s `docks[]` array.

## Diagnostics tab

If the dock stops responding to clicks or typing — for example after running
another script in the same session — open the **Diagnostics** tab next to
**Browse**, click **Refresh** to recompute the report, then click **Copy** to
put it on the clipboard. Paste the copied text when reporting the problem;
it describes the dock's live state (whether it is still registered with the
main window, whether its child widgets are still alive, and how many times
its setup/reset lifecycle has run) and helps pinpoint what "running another
script" changed.

## Known limitations

This is a template, not a finished dock: the demo list is hardcoded and in
memory, there is no long-running task in the status bar demo (the
`DockStatusBarController.task()` context manager is unused here — see
`lib/status_bar.py`'s docstring for how a real dock would drive it), and no
domain-object interaction (selecting an item does nothing) is wired up.
