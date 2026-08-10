# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# Not CI-budget-enforced (only template/docks/lib/*.py and the launcher are).
"""demo_dock_widget — DemoDock: the copyable clean-dock example.

Subclasses BaseDockWidget (contracts/DOCK_INTERFACE.md) and demonstrates the
full contract in one small widget: a browse bar that filters an in-memory
demo list, a status bar, an Info button that opens the dock's README, and
per-model persistence of the last-used filter text (loaded in setup_ui,
saved in on_close). A Diagnostics tab reports the dock's live runtime state
(reuse/reparent status, lifecycle counters) so a stuck dock can be debugged
by clicking Refresh then Copy and pasting the report.

A backend copies this file, renames the class, replaces the demo list with
real data, and keeps the lifecycle wiring.
"""
from __future__ import annotations

from pathlib import Path

from ..lib.base_dock import BaseDockWidget
from ..lib.browse_bar import DockBrowseBar
from ..lib.diagnostics import collect_dock_report
from ..lib.persistence import build_dock_config_path, load_json, save_json
from ..lib.qt_compat import QtWidgets
from ..lib.status_bar import DockStatusBarController

QListWidget = QtWidgets.QListWidget
QLabel = QtWidgets.QLabel
QProgressBar = QtWidgets.QProgressBar
QPushButton = QtWidgets.QPushButton
QHBoxLayout = QtWidgets.QHBoxLayout
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget
QTabWidget = QtWidgets.QTabWidget
QPlainTextEdit = QtWidgets.QPlainTextEdit

DEMO_ITEMS = [
    "alpha section",
    "bravo node",
    "charlie centroid",
    "delta detector",
    "echo turning",
]

_DOC_PATH = Path(__file__).parent / "README.md"
_DOCK_KEY = "template.demo.v1"


class DemoDock(BaseDockWidget):
    """The template's copyable demo dock."""

    def __init__(self, host, model, **kwargs):
        self._diag_counters = {"init": 0, "setup_ui": 0, "reset_state": 0}
        self._diag_counters["init"] += 1
        self._config_path = build_dock_config_path(model, "Demo Dock")
        self._list_widget: "QtWidgets.QListWidget | None" = None
        self._status_label: "QtWidgets.QLabel | None" = None
        self._progress_bar: "QtWidgets.QProgressBar | None" = None
        self._status: "DockStatusBarController | None" = None
        self._browse_bar: "DockBrowseBar | None" = None
        self._diag_text: "QtWidgets.QPlainTextEdit | None" = None
        super().__init__("Demo Dock", host, model, **kwargs)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        self._diag_counters["setup_ui"] += 1
        self.clear_root_layout()

        if self._browse_bar is not None:
            try:
                self._browse_bar.filter_changed.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._list_widget = None
        self._status_label = None
        self._progress_bar = None
        self._status = None
        self._browse_bar = None
        self._diag_text = None

        tabs = QTabWidget(self.container)
        tabs.addTab(self._build_browse_tab(), "Browse")
        tabs.addTab(self._build_diagnostics_tab(), "Diagnostics")
        self.root_layout.addWidget(tabs, 1)

        footer = QHBoxLayout()
        self._status_label = QLabel("Ready", self.container)
        self._progress_bar = QProgressBar(self.container)
        self._progress_bar.setVisible(False)
        info_btn = QPushButton("Info", self.container)
        info_btn.clicked.connect(self._on_info_clicked)
        footer.addWidget(self._status_label, 1)
        footer.addWidget(self._progress_bar)
        footer.addWidget(info_btn)
        self.root_layout.addLayout(footer)

        self._status = DockStatusBarController(self._status_label, self._progress_bar)

        saved = load_json(self._config_path, default={})
        last_filter = (saved or {}).get("filter_text", "")
        self._populate_list(last_filter)
        if last_filter:
            self._browse_bar.set_search_text(last_filter)

        self._refresh_diagnostics()

    def _build_browse_tab(self) -> "QtWidgets.QWidget":
        tab = QWidget(self.container)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browse_bar = DockBrowseBar(parent=tab)
        self._browse_bar.filter_changed.connect(self._on_filter_changed)
        layout.addWidget(self._browse_bar)

        self._list_widget = QListWidget(tab)
        layout.addWidget(self._list_widget, 1)
        return tab

    def _build_diagnostics_tab(self) -> "QtWidgets.QWidget":
        tab = QWidget(self.container)
        layout = QVBoxLayout(tab)

        self._diag_text = QPlainTextEdit(tab)
        self._diag_text.setReadOnly(True)
        self._diag_text.setStyleSheet("font-family: monospace;")
        layout.addWidget(self._diag_text, 1)

        buttons = QHBoxLayout()
        refresh_btn = QPushButton("Refresh", tab)
        refresh_btn.clicked.connect(self._refresh_diagnostics)
        copy_btn = QPushButton("Copy", tab)
        copy_btn.clicked.connect(self._copy_diagnostics)
        buttons.addWidget(refresh_btn)
        buttons.addWidget(copy_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return tab

    def _refresh_diagnostics(self) -> None:
        if self._diag_text is None:
            return
        report = collect_dock_report(self, dock_key=_DOCK_KEY)
        self._diag_text.setPlainText(report)

    def _copy_diagnostics(self) -> None:
        if self._diag_text is None:
            return
        QtWidgets.QApplication.clipboard().setText(self._diag_text.toPlainText())

    def reset_state(self) -> None:
        self._diag_counters["reset_state"] += 1
        super().reset_state()
        self.setup_ui()

    def on_close(self) -> None:
        filter_text = self._browse_bar.search_text if self._browse_bar else ""
        save_json(self._config_path, {"filter_text": filter_text})

    # ------------------------------------------------------------------
    # Demo behaviour
    # ------------------------------------------------------------------

    def _on_filter_changed(self, text: str) -> None:
        self._populate_list(text)
        if self._status is not None:
            self._status.set_status(f"Showing matches for '{text}'" if text else "Ready")

    def _populate_list(self, filter_text: str) -> None:
        if self._list_widget is None:
            return
        self._list_widget.clear()
        needle = (filter_text or "").lower()
        for item in DEMO_ITEMS:
            if needle in item.lower():
                self._list_widget.addItem(item)

    def _on_info_clicked(self) -> None:
        from .info_dialog import InfoDialog  # lazy: keeps module import Qt-safe

        dialog = InfoDialog(_DOC_PATH, self.windowTitle(), parent=self)
        dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
