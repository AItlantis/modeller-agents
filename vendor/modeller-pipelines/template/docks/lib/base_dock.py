# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# See docs/ADR/ADR-0003-dock-artefact-seam.md for the dock lifecycle this implements.
# Line budget: 110 lines (CI-enforced).
"""base_dock — BaseDockWidget: the copyable dock lifecycle shape.

Implements the widget shape described in contracts/DOCK_INTERFACE.md: a
constructor of (title, host, model, **kwargs), a container + root layout,
and the setup_ui/reset_state/on_show/on_hide/on_close lifecycle hooks. This
is a spec illustration, not an importable base class shipped by
modeller-pipelines — copy it into your backend and subclass it there.
"""
from __future__ import annotations

from .qt_compat import QT_LEFT_DOCK_WIDGET_AREA, QT_RIGHT_DOCK_WIDGET_AREA, QtWidgets

QDockWidget = QtWidgets.QDockWidget
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout


class BaseDockWidget(QDockWidget):
    """Copyable base class for a single-instance, reload-tolerant dock widget."""

    def __init__(self, title: str, host, model, allowed_areas=None, **kwargs):
        super().__init__(title, host)
        if allowed_areas is None:
            allowed_areas = QT_LEFT_DOCK_WIDGET_AREA | QT_RIGHT_DOCK_WIDGET_AREA
        self.setAllowedAreas(allowed_areas)
        self.host = host
        self.model = model

        self.container = QWidget(self)
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(4, 4, 4, 4)
        self.root_layout.setSpacing(4)
        self.setWidget(self.container)

        self.setup_ui()

    # ------------------------------------------------------------------
    # Lifecycle — see contracts/DOCK_INTERFACE.md §2-3
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        raise NotImplementedError("Subclasses must implement setup_ui()")

    def reset_state(self) -> None:
        """Reset the dock to a clean state when the loader reuses it.

        Default behaviour: clear the root layout. Subclasses should override
        and call super().reset_state() to add their own reset logic, then
        rebuild via setup_ui() (or an equivalent) as needed.
        """
        self.clear_root_layout()

    def on_show(self) -> None:
        pass

    def on_hide(self) -> None:
        pass

    def on_close(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Qt event wiring
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self.on_close()
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        self.on_show()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.on_hide()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def clear_root_layout(self) -> None:
        """Remove all widgets from the root layout, recursing into sub-layouts."""
        def _clear(layout) -> None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                sub_layout = item.layout()
                if widget is not None:
                    widget.setParent(None)
                elif sub_layout is not None:
                    _clear(sub_layout)
                    sub_layout.deleteLater()

        _clear(self.root_layout)
