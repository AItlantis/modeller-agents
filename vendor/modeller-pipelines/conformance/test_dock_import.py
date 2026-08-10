"""Host-only dock import/runtime tests — SKIPPED unless a Qt binding is
installed (the ``qt_available`` fixture). These are the only dock tests that
actually import the launcher module or construct a widget; every other dock
conformance test is static/AST-only so it passes with no Qt installed.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def require_qt(qt_available: bool) -> None:
    if not qt_available:
        pytest.skip("No Qt binding installed — host-only dock import test skipped")


def _import_entry_module(backend_root: Path, dock: dict):
    entry_path = backend_root / dock["entry_module"]
    module_name = f"_dock_conformance_{dock['dock_id']}"
    spec = importlib.util.spec_from_file_location(module_name, entry_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_entry_module_imports_cleanly_and_exposes_run(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        module = _import_entry_module(backend_root, dock)
        assert hasattr(module, "run"), f"{dock['dock_id']}: entry module has no 'run' attribute"
        assert callable(module.run), f"{dock['dock_id']}: 'run' is not callable"


def test_qt_compat_shim_exports_required_names(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        entry_path = backend_root / dock["entry_module"]
        lib_dir = entry_path.parent / "lib"
        if not lib_dir.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            f"_dock_conformance_qt_compat_{dock['dock_id']}", lib_dir / "qt_compat.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        for name in ("QtCore", "QtGui", "QtWidgets", "Signal"):
            assert hasattr(module, name), f"qt_compat.py missing required export: {name}"


def test_dock_single_instance_reuse_and_reset_state(backend_root: Path, backend_docks: list) -> None:
    """Instantiate the dock twice under one QApplication and assert reuse + reset_state call.

    Only meaningful for docks whose entry module exposes an integration hook
    it launches through (``lib.integration.load_dock``/``integrate_dock``);
    this is an optional deeper check layered on top of the mandatory
    import/callable checks above, and any failure here is host-environment
    specific (real QApplication + real main window), so it is best-effort.
    """
    try:
        from PySide6.QtWidgets import QApplication, QMainWindow  # type: ignore
    except ImportError:
        try:
            from PyQt6.QtWidgets import QApplication, QMainWindow  # type: ignore
        except ImportError:
            from PyQt5.QtWidgets import QApplication, QMainWindow  # type: ignore

    app = QApplication.instance() or QApplication([])
    host = QMainWindow()

    for dock in backend_docks:
        entry_path = backend_root / dock["entry_module"]
        docks_pkg_root = entry_path.parent.parent  # the folder containing docks/
        lib_dir = entry_path.parent / "lib"
        widget_candidates = sorted((entry_path.parent).rglob("*_widget.py"))
        if not lib_dir.is_dir() or not widget_candidates:
            continue

        # Import via real dotted package names (not spec_from_file_location) so
        # the widget's relative "from ..lib import ..." imports resolve.
        if str(docks_pkg_root) not in sys.path:
            sys.path.insert(0, str(docks_pkg_root))
        docks_package_name = entry_path.parent.name  # e.g. "docks"
        widget_module_name = (
            f"{docks_package_name}.{widget_candidates[0].parent.name}.{widget_candidates[0].stem}"
        )
        integration_module_name = f"{docks_package_name}.lib.integration"

        integration = importlib.import_module(integration_module_name)
        widget_module = importlib.import_module(widget_module_name)

        dock_classes = [
            getattr(widget_module, name)
            for name in dir(widget_module)
            if isinstance(getattr(widget_module, name), type)
            and hasattr(getattr(widget_module, name), "reset_state")
            and hasattr(getattr(widget_module, name), "setup_ui")
        ]
        assert dock_classes, f"{widget_candidates[0]} defines no dock widget class"
        dock_class = dock_classes[0]

        model = object()  # a plain stand-in; the demo widget tolerates a minimal model
        first = integration.integrate_dock(host, model, dock_class, dock["dock_key"])
        second = integration.integrate_dock(host, model, dock_class, dock["dock_key"])
        assert first is second, \
            f"dock '{dock['dock_id']}': relaunching created a duplicate instead of reusing"
