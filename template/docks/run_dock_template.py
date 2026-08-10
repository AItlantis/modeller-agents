# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# See docs/ADR/ADR-0003-dock-artefact-seam.md for the entry-point seam this implements.
# Line budget: 140 lines (CI-enforced).
"""run_dock_template — launches the template's demo QtDock in Aimsun.

Entry point per contracts/DOCK_CONTRACT.md: run(model, _argv=None) -> bool.
Importing this module MUST NOT construct Qt objects or import a Qt binding
at module scope (contracts/DOCK_CONTRACT.md §2) — that is what lets the
conformance kit inspect it with no Qt installed. All Qt/widget imports below
are lazy, inside run().

Usage (from the Aimsun Next UI Script Manager, with an open model):
    run(model)

Development-only reimport: set DEMO_DOCK_DEBUG=1 to purge this dock's own
package from sys.modules before each relaunch, so edits to demo_dock/ or
lib/ are picked up without restarting Aimsun. The purge never touches a
shared/framework prefix — see contracts/DOCK_CONTRACT.md §7.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

_dock_instance = None

DEBUG = os.getenv("DEMO_DOCK_DEBUG", "0") == "1"

_THIS_FILE = Path(__file__).resolve()
_MARKER = Path("docks/run_dock_template.py")
_LAUNCHER_MODULE = "docks.run_dock_template"
# Explicit module prefixes to reimport under DEBUG. Only the dock's own
# package (its widget, info dialog, and copied lib/) — never a shared/
# framework prefix outside docks/, per contracts/DOCK_CONTRACT.md §7.
_RELOAD_PREFIXES = (
    "docks.demo_dock",
    "docks.lib",
)


def _find_package_root() -> Path:
    """Walk upward from this file until a folder contains the marker.

    Identifies the root by markers (this file's relative path existing
    under the candidate), not by a fixed parent depth, so the launcher works
    whether run from a dev checkout or a flattened export.
    """
    for candidate in (_THIS_FILE.parent, *_THIS_FILE.parents):
        if (candidate / _MARKER).is_file():
            return candidate
    raise RuntimeError(
        f"Could not locate the package root containing {_MARKER} above {_THIS_FILE}."
    )


def _purge_reimport_targets() -> None:
    """DEBUG-only: drop this dock's own modules so the next import is fresh.

    Purge-based, not importlib.reload(): reloading in place rebinds class
    objects while a live dock instance in the shared interpreter still
    references the old class, breaking reload-tolerant reuse
    (contracts/DOCK_CONTRACT.md §4). Deepest-first so child attributes are
    detached before their parent module vanishes from sys.modules.
    """
    targets = [
        name
        for name in list(sys.modules)
        if name != _LAUNCHER_MODULE
        and any(name == prefix or name.startswith(prefix + ".") for prefix in _RELOAD_PREFIXES)
    ]
    for name in sorted(targets, key=lambda n: n.count("."), reverse=True):
        sys.modules.pop(name, None)
        parent_name, _, child = name.rpartition(".")
        parent = sys.modules.get(parent_name) if parent_name else None
        if parent is not None and hasattr(parent, child):
            try:
                delattr(parent, child)
            except AttributeError:
                pass
    importlib.invalidate_caches()
    print(f"[DEMO DOCK] DEBUG: purged {len(targets)} module(s) for reimport")


def run(model, _argv=None) -> bool:  # noqa: ARG001 - _argv is part of the contract shape
    """Launch the demo dock (non-modal) in Aimsun. See contracts/DOCK_CONTRACT.md."""
    global _dock_instance

    try:
        package_root = _find_package_root()
        if str(package_root) not in sys.path:
            sys.path.insert(0, str(package_root))

        if DEBUG:
            _purge_reimport_targets()

        from docks.lib.integration import load_dock
        from docks.demo_dock.demo_dock_widget import DemoDock
    except ImportError as exc:
        print(
            "ERROR: Failed to import demo dock dependencies. "
            f"{type(exc).__name__}: {exc}"
        )
        return False
    except RuntimeError as exc:
        print(f"ERROR: Failed to locate the demo dock package root. {exc}")
        return False

    _dock_instance = load_dock(
        model,
        DemoDock,
        dock_key="template.demo.v1",
        dock_name="Demo Dock",
    )
    if _dock_instance is None:
        print("ERROR: Failed to launch demo dock")
        return False
    _dock_instance.raise_()
    _dock_instance.activateWindow()
    print("Demo Dock launched")
    return True


if __name__ == "__main__":
    run(model)  # noqa: F821 - injected by the Aimsun Script Manager
