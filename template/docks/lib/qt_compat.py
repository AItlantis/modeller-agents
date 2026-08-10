# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# See docs/ADR/ADR-0003-dock-artefact-seam.md for why docks copy this shim too.
# Line budget: 90 lines (CI-enforced).
"""qt_compat — Qt binding compatibility shim for dock UIs.

Use this module from dock code instead of importing PyQt5/PyQt6/PySide6
directly. Tries PySide6, then PyQt6, then PyQt5. Every symbol a dock needs
(QtCore/QtGui/QtWidgets, Signal, enum constants) is exported here so dock
modules never touch a binding-specific name.

DOCK_CONTRACT.md §2 requires this import itself to stay lazy at the call
site (inside a dock's run()/setup_ui(), never at a launcher's module scope)
so the conformance kit can inspect dock modules with no Qt binding installed.
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

    Signal = QtCore.Signal
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    except ImportError:
        from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore

    Signal = QtCore.pyqtSignal


def _enum_value(enum_owner, group_name: str, member_name: str, legacy_name: str):
    """Return a Qt enum value across PyQt5 flat aliases and PySide6/PyQt6 scoped enums."""
    legacy_value = getattr(enum_owner, legacy_name, None)
    if legacy_value is not None:
        return legacy_value
    group = getattr(enum_owner, group_name, None)
    if group is None:
        raise AttributeError(
            f"qt_compat._enum_value: {getattr(enum_owner, '__name__', enum_owner)!r} "
            f"has neither flat '{legacy_name}' nor scoped group '{group_name}'."
        )
    return getattr(group, member_name)


QT_LEFT_DOCK_WIDGET_AREA = _enum_value(
    QtCore.Qt, "DockWidgetArea", "LeftDockWidgetArea", "LeftDockWidgetArea"
)
QT_RIGHT_DOCK_WIDGET_AREA = _enum_value(
    QtCore.Qt, "DockWidgetArea", "RightDockWidgetArea", "RightDockWidgetArea"
)
QT_TOP_DOCK_WIDGET_AREA = _enum_value(
    QtCore.Qt, "DockWidgetArea", "TopDockWidgetArea", "TopDockWidgetArea"
)
QT_BOTTOM_DOCK_WIDGET_AREA = _enum_value(
    QtCore.Qt, "DockWidgetArea", "BottomDockWidgetArea", "BottomDockWidgetArea"
)
QT_RICH_TEXT = _enum_value(QtCore.Qt, "TextFormat", "RichText", "RichText")


def qt_exec(dialog_or_menu, *args):
    """Execute a Qt dialog/menu with the Qt6 name, falling back to Qt5's exec_()."""
    if hasattr(dialog_or_menu, "exec"):
        return dialog_or_menu.exec(*args)
    return dialog_or_menu.exec_(*args)


DOCK_AREA_BY_NAME = {
    "left": QT_LEFT_DOCK_WIDGET_AREA,
    "right": QT_RIGHT_DOCK_WIDGET_AREA,
    "top": QT_TOP_DOCK_WIDGET_AREA,
    "bottom": QT_BOTTOM_DOCK_WIDGET_AREA,
}
