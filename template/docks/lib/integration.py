# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# See docs/ADR/ADR-0003-dock-artefact-seam.md for the reload-tolerant reuse rule this implements.
# Line budget: 200 lines (CI-enforced).
"""integration — load_dock/integrate_dock/close_existing_dock: the
process-wide single-instance dock registry (contracts/DOCK_CONTRACT.md §3-5).

Reuse detection matches the stored instance's class *qualified name* rather
than using isinstance(), so a dock built before a DEBUG reimport (see
run_dock_template.py) is still recognised as the same dock and reused instead
of being orphaned while a duplicate is created alongside it.
"""
from __future__ import annotations

import importlib
import sys
from typing import Iterable, Optional, Type

from .qt_compat import DOCK_AREA_BY_NAME, QT_RIGHT_DOCK_WIDGET_AREA, QtCore, QtWidgets

QTimer = QtCore.QTimer

# Process-wide dock registry, keyed by dock_key: survives across script runs
# in the shared interpreter. QApplication.setProperty/property round-trips a
# QVariant and has been observed to drop a just-stored QObject (readback
# None) in real Aimsun/PyQt5 sessions. This dict is the source of truth;
# setProperty is still set as a best-effort mirror for diagnostics.py.
_DOCK_REGISTRY: dict = {}


def registered_dock(dock_key: str):
    """Return the dock registered under ``dock_key``, or None."""
    return _DOCK_REGISTRY.get(dock_key)


def reload_loaded_modules(prefixes: Iterable[str]) -> int:
    """Reload already-imported modules whose names start with one of the prefixes."""
    prefixes = tuple(prefixes)
    module_names = sorted(
        name for name in list(sys.modules.keys())
        if any(name.startswith(prefix) for prefix in prefixes)
    )
    reloaded = 0
    for name in module_names:
        module = sys.modules.get(name)
        if module is None:
            continue
        try:
            importlib.reload(module)
            reloaded += 1
        except Exception:
            continue
    return reloaded


def find_main_window() -> Optional["QtWidgets.QMainWindow"]:
    """Active window first, else the first VISIBLE QMainWindow (picking "the
    first" top-level widget outright is unstable and can pick a hidden one)."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None
    active = app.activeWindow()
    if isinstance(active, QtWidgets.QMainWindow):
        return active
    fallback = None
    for widget in app.topLevelWidgets():
        if isinstance(widget, QtWidgets.QMainWindow):
            if widget.isVisible():
                return widget
            if fallback is None:
                fallback = widget
    return fallback


def close_existing_dock(host, dock_key: str) -> bool:
    """Close and detach a dock stored in the process-wide registry, if present."""
    dock = _DOCK_REGISTRY.get(dock_key)
    if dock is None:
        return False
    try:
        if host is not None and hasattr(host, "removeDockWidget"):
            host.removeDockWidget(dock)
        if hasattr(dock, "close"):
            dock.close()
        if hasattr(dock, "deleteLater"):
            dock.deleteLater()
    except Exception:
        pass  # C++ object may already be deleted; registry is cleared below regardless
    finally:
        _DOCK_REGISTRY.pop(dock_key, None)
        _mirror_property(dock_key, None)
    return True


def _mirror_property(dock_key: str, value) -> None:
    # Best-effort QApplication property mirror; the registry stays authoritative.
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    try:
        app.setProperty(dock_key, value)
    except Exception:
        pass


def _qualified_class_name(cls: type) -> str:
    """Return a stable module+qualname identity for a class object."""
    return f"{getattr(cls, '__module__', '')}.{getattr(cls, '__qualname__', cls.__name__)}"


def _is_reusable_dock(dock, dock_class: Type) -> bool:
    """True when a stored dock can be reused for ``dock_class``. Matches the
    class's qualified name (not isinstance/identity) so a dock built before a
    DEBUG reimport is still recognised as the same dock. A dock whose C++
    object is already dead (RuntimeError on a harmless probe) is discarded.
    """
    if dock is None:
        return False
    try:
        dock.isVisible()  # probe: raises RuntimeError if the C++ object is dead
        if isinstance(dock, dock_class):
            return True
        return _qualified_class_name(type(dock)) == _qualified_class_name(dock_class)
    except RuntimeError:
        return False


def integrate_dock(host, model, dock_class: Type, dock_key: str, area=None, **kwargs):
    """Create or reuse a dock, keyed by ``dock_key`` in _DOCK_REGISTRY. If
    reusable, reset state, re-show, and re-assert it is docked into ``area``
    (a dock can end up detached, dockWidgetArea() == 0, after a host swap).
    Otherwise close and create fresh — never left orphaned. After return,
    host.dockWidgetArea(dock) is guaranteed non-zero and dock is registered.
    """
    if area is None:
        area = QT_RIGHT_DOCK_WIDGET_AREA
    app = QtWidgets.QApplication.instance()
    if app is None:
        raise RuntimeError("No QApplication instance. Must run inside a Qt host.")
    dock = _DOCK_REGISTRY.get(dock_key)
    if _is_reusable_dock(dock, dock_class):
        try:
            if hasattr(dock, "reset_state") and callable(dock.reset_state):
                dock.reset_state()
            if host is not None and hasattr(host, "dockWidgetArea") and not host.dockWidgetArea(dock):
                host.addDockWidget(area, dock)  # detached: re-add (idempotent, reparents)
            else:
                dock.setParent(host)
            dock.setFloating(False)
            dock.show()
            dock.raise_()
            return dock
        except Exception as exc:
            print(f"[DOCK] Reuse failed ({exc}), creating fresh instance")
            close_existing_dock(host, dock_key)
    elif dock is not None:
        close_existing_dock(host, dock_key)
    dock = dock_class(host, model, **kwargs)
    host.addDockWidget(area, dock)
    dock.setFloating(False)
    _DOCK_REGISTRY[dock_key] = dock
    _mirror_property(dock_key, dock)
    dock.show()
    return dock


def load_dock(
    model,
    dock_class: Type,
    dock_key: str,
    dock_name: str,
    area=None,
    host=None,
    reload_prefixes: "Iterable[str] | None" = None,
    **kwargs,
):
    """Standard dock entry point: find the host window, optionally reload, attach."""
    if isinstance(area, str):
        area = DOCK_AREA_BY_NAME.get(area, QT_RIGHT_DOCK_WIDGET_AREA)
    if area is None:
        area = QT_RIGHT_DOCK_WIDGET_AREA
    app = QtWidgets.QApplication.instance()
    if app is None:
        print("[ERROR] No QApplication found. Cannot create dock.")
        return None
    host = host or find_main_window()
    if host is None:
        print("[ERROR] Main window not found; cannot attach dock.")
        return None
    if reload_prefixes:
        reload_loaded_modules(reload_prefixes)

    try:
        dock = integrate_dock(host, model, dock_class, dock_key, area, **kwargs)
        print(f"[INFO] {dock_name} ready")
        return dock
    except Exception as exc:
        print(f"[ERROR] {dock_name} failed: {exc}")
        return None
