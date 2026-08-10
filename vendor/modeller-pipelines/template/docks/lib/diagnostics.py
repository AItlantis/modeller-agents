# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# See docs/ADR/ADR-0003-dock-artefact-seam.md for the reuse/reparent state this reports on.
# Line budget: 120 lines (CI-enforced).
"""diagnostics — collect_dock_report: a paste-into-chat runtime state dump.

For a dock that "stops responding" after another script runs: the dock's
Diagnostics tab calls collect_dock_report(self, dock_key=...) and the user
copies the text back. Every access here is wrapped so a deleted C++ object
(RuntimeError) or a missing attribute never raises.
"""
from __future__ import annotations

from typing import Any, Optional

def _safe(fn, *, default: str = "") -> str:  # call fn() and stringify; never raise
    try:
        value = fn()
        return "<unavailable: empty>" if value is None else str(value)
    except Exception as exc:  # noqa: BLE001 - diagnostics must never raise
        return default or f"<unavailable: {type(exc).__name__}: {exc}>"

def _safe_bool(fn) -> str:
    return _safe(lambda: bool(fn()))

def _alive(obj: Any, probe: str = "objectName") -> str:  # touch a harmless method; alive iff it doesn't raise
    if obj is None:
        return "<none>"
    try:
        getattr(obj, probe)()
        return "alive"
    except RuntimeError as exc:
        return f"<deleted: {exc}>"
    except Exception as exc:  # noqa: BLE001
        return f"<unavailable: {type(exc).__name__}: {exc}>"

def collect_dock_report(dock, *, dock_key: Optional[str] = None, extra: Optional[dict] = None) -> str:
    # Plain-text multi-section report of ``dock``'s live runtime state.
    from .qt_compat import QtWidgets

    lines: list[str] = ["Dock diagnostics report", "=" * 24]

    def section(title: str) -> None:
        lines.append("")
        lines.append(f"=== {title} ===")

    def kv(label: str, value: str) -> None:
        lines.append(f"- {label}: {value}")

    try:
        app = QtWidgets.QApplication.instance()
    except Exception:  # noqa: BLE001
        app = None

    section("Identity / reuse")
    kv("class", _safe(lambda: f"{type(dock).__module__}.{type(dock).__qualname__}"))
    kv("id(dock)", _safe(lambda: id(dock)))
    if dock_key is not None:
        kv("dock_key", dock_key)
        if app is None:
            kv("registered instance", "<unavailable: no QApplication>")
        else:
            try:
                reg_obj = app.property(dock_key)
            except Exception as exc:  # noqa: BLE001
                reg_obj = f"<unavailable: {type(exc).__name__}: {exc}>"
            kv("registered instance", _safe(lambda: repr(reg_obj)))
            kv("registered is dock", _safe(lambda: reg_obj is dock))
            kv("registered id", "<none>" if reg_obj is None else _safe(lambda: id(reg_obj)))

    section("Parent & dock registration")
    kv("parent()/parentWidget()", _safe(lambda: repr(dock.parent())) + " / " + _safe(lambda: repr(dock.parentWidget())))
    kv("isFloating()", _safe_bool(dock.isFloating))
    host = None
    try:
        candidate = dock.parent()
        host = candidate if isinstance(candidate, QtWidgets.QMainWindow) else None
        if host is None and app is not None:
            host = next((w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow)), None)
    except Exception:  # noqa: BLE001
        host = None
    kv("host", "<unavailable: no QMainWindow found>" if host is None else _safe(lambda: repr(host)))
    if host is not None:
        kv("dockWidgetArea(dock)", _safe(lambda: host.dockWidgetArea(dock)))
    kv("isVisible()/isEnabled()", _safe_bool(dock.isVisible) + " / " + _safe_bool(dock.isEnabled))
    kv("widget()/widget().isEnabled()", _safe(lambda: repr(dock.widget())) + " / "
       + _safe_bool(lambda: dock.widget().isEnabled()))

    section("Signal connections")
    bar = getattr(dock, "_browse_bar", None)
    edit = getattr(bar, "_search_edit", None) if bar is not None else None
    kv("browse bar alive", _alive(bar))
    kv("browse bar filter_changed receivers", _safe(lambda: bar.receivers(bar.filter_changed)))
    kv("browse bar line edit alive", _alive(edit))
    kv("line edit textChanged receivers", _safe(lambda: edit.receivers(edit.textChanged)))
    kv("list widget alive", _alive(getattr(dock, "_list_widget", None)))

    section("Lifecycle counters")
    counters = getattr(dock, "_diag_counters", {})
    if not counters:
        lines.append("- <none recorded>")
    for name, value in counters.items():
        kv(str(name), _safe(lambda v=value: v))

    section("QApplication context")
    if app is None:
        lines.append("- <unavailable: no QApplication instance>")
    else:
        kv("top-level widgets", _safe(lambda: len(app.topLevelWidgets())))
        kv("QMainWindow count", _safe(
            lambda: sum(1 for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow))))
        kv("same thread as dock", _safe_bool(lambda: app.thread() is dock.thread()))

    if extra:
        section("Extra")
        for key, value in extra.items():
            kv(str(key), _safe(lambda v=value: v))

    lines.append("")
    return "\n".join(lines)
