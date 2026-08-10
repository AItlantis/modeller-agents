# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# Line budget: 110 lines (CI-enforced).
"""status_bar — DockStatusBarController: a status QLabel + QProgressBar pair
wrapped into one reusable controller.

    self._status = DockStatusBarController(self._status_label, self._progress_bar)

    with self._status.task("Scanning...") as task:
        task.step(50, "Halfway there...")
    # exit hides the progress bar; on exception sets a red error message
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from .qt_compat import QtWidgets

QLabel = QtWidgets.QLabel
QProgressBar = QtWidgets.QProgressBar


class _Task:
    """Lightweight handle returned by DockStatusBarController.task()."""

    def __init__(self, controller: "DockStatusBarController") -> None:
        self._controller = controller

    def step(self, pct: int, message: Optional[str] = None) -> None:
        if message is not None:
            self._controller.set_status(message)
        self._controller.show_progress(pct)

    def update_loop(self, current: int, total: int, message: Optional[str] = None) -> None:
        safe_total = max(1, int(total))
        pct = int((100 * int(current)) / safe_total)
        self.step(pct, message)

    def error(self, message: str) -> None:
        self._controller.set_status(message, color="red")
        self._controller.show_progress(-1)


class DockStatusBarController:
    """Reusable controller for a dock's status label + progress bar.

    Methods are safe to call when the underlying widgets are None.
    """

    def __init__(self, label: "QLabel", progress_bar: "QProgressBar"):
        self._label = label
        self._progress_bar = progress_bar

    def set_status(self, message: str, *, color: str = "") -> None:
        if self._label is None:
            return
        self._label.setText(message)
        self._label.setStyleSheet(f"color: {color};" if color else "")

    def show_progress(self, pct: int) -> None:
        if self._progress_bar is None:
            return
        if pct < 0:
            self._progress_bar.setVisible(False)
            self._progress_bar.setValue(0)
        else:
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(int(min(100, max(0, pct))))

    @contextmanager
    def task(self, start_message: str = "", *, final_message: Optional[str] = None) -> Iterator[_Task]:
        """Context manager for a multi-step operation with a progress bar."""
        if start_message:
            self.set_status(start_message)
        self.show_progress(0)
        handle = _Task(self)
        try:
            yield handle
        except Exception as exc:
            self.set_status(f"Error: {type(exc).__name__}: {exc}", color="red")
            self.show_progress(-1)
            raise
        else:
            if final_message is not None:
                self.set_status(final_message)
            self.show_progress(-1)


__all__ = ["DockStatusBarController"]
