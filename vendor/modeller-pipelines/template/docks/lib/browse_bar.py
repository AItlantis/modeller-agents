# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# Line budget: 110 lines (CI-enforced).
"""browse_bar — search box + optional toggle buttons in one horizontal bar.

The "browse" piece of a dock: a reusable filter row a dock's setup_ui() can
drop above a list/table to let the user narrow what is shown.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .qt_compat import QtWidgets, Signal

SIZE_POLICY_EXPANDING = QtWidgets.QSizePolicy.Policy.Expanding \
    if hasattr(QtWidgets.QSizePolicy, "Policy") else QtWidgets.QSizePolicy.Expanding
SIZE_POLICY_PREFERRED = QtWidgets.QSizePolicy.Policy.Preferred \
    if hasattr(QtWidgets.QSizePolicy, "Policy") else QtWidgets.QSizePolicy.Preferred


class DockBrowseBar(QtWidgets.QWidget):
    """Search line edit + N toggle buttons in one horizontal bar.

    Args:
        mode_specs: Sequence of ``(key, label, tooltip)`` tuples, one per
            toggle button. Each button is checkable; the caller decides any
            mutual-exclusivity logic.
        parent: Optional parent widget.
    """

    filter_changed = Signal(str)   # search text
    mode_changed = Signal(str)     # objectName of the toggled button

    def __init__(self, mode_specs: Sequence[tuple] = (), parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._mode_specs = list(mode_specs)
        self._toggle_buttons: dict[str, QtWidgets.QPushButton] = {}

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if self._mode_specs:
            layout.addWidget(QtWidgets.QLabel("Filters:"))
        for key, label, tooltip in self._mode_specs:
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setObjectName(key)
            btn.clicked.connect(lambda _checked, k=key: self.mode_changed.emit(k))
            self._toggle_buttons[key] = btn
            layout.addWidget(btn)

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("Search...")
        self._search_edit.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_PREFERRED)
        self._search_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._search_edit, 1)

    def _on_text_changed(self, text: str) -> None:
        self.filter_changed.emit(text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active_mode(self, key: str) -> None:
        btn = self._toggle_buttons.get(key)
        if btn is not None:
            btn.setChecked(True)

    def clear_search(self) -> None:
        self._search_edit.blockSignals(True)
        self._search_edit.clear()
        self._search_edit.blockSignals(False)

    def set_search_text(self, text: str) -> None:
        """Set the search box text without emitting filter_changed."""
        self._search_edit.blockSignals(True)
        self._search_edit.setText(text)
        self._search_edit.blockSignals(False)

    def get_toggle(self, key: str) -> Optional[QtWidgets.QPushButton]:
        return self._toggle_buttons.get(key)

    @property
    def search_text(self) -> str:
        return self._search_edit.text()

    @property
    def active_mode(self) -> str:
        for key, btn in self._toggle_buttons.items():
            if btn.isChecked():
                return key
        return ""
