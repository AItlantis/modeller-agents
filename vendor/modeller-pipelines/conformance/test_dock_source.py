"""AST / static-source conformance tests for docks — parse only, never import.

No Qt binding is required: these tests read dock source files as text/AST,
so they run in an environment with zero Qt bindings installed. This is the
dock analogue of pipeline step static checks (STEP_INTERFACE.md §2.1) —
proving import-safety without ever triggering the import.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_QT_BINDING_NAMES = {"PyQt5", "PyQt6", "PySide2", "PySide6"}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_level_imports(tree: ast.Module) -> list[str]:
    """Return dotted names imported at module scope (not inside any function/class)."""
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _all_imports(tree: ast.Module) -> list[str]:
    """Return dotted names imported anywhere in the module (any nesting depth)."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _defines_function(tree: ast.Module, name: str, *, module_level: bool = False) -> bool:
    nodes = tree.body if module_level else ast.walk(tree)
    return any(isinstance(n, ast.FunctionDef) and n.name == name for n in nodes)


def _first_arg_name(tree: ast.Module, func_name: str) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            args = node.args.args
            return args[0].arg if args else None
    return None


def _class_defines_method(tree: ast.Module, method_name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return True
    return False


def _calls_importlib_reload(tree: ast.Module) -> bool:
    """True if the module contains an actual importlib.reload(...) call site.

    AST-based (not a text/substring search) so mentioning "importlib.reload()"
    in a docstring or comment — as this very rule's own explanation does — is
    never mistaken for the call this rule forbids.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "reload":
            if isinstance(func.value, ast.Name) and func.value.id == "importlib":
                return True
        elif isinstance(func, ast.Name) and func.id == "reload":
            return True
    return False


def test_entry_module_defines_module_level_run(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        path = backend_root / dock["entry_module"]
        tree = _parse(path)
        assert _defines_function(tree, "run", module_level=True), \
            f"{path} does not define a module-level 'run' function"
        first_arg = _first_arg_name(tree, "run")
        assert first_arg == "model", \
            f"{path}: run()'s first parameter must be 'model', got '{first_arg}'"


def test_entry_module_has_no_module_scope_qt_import(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        path = backend_root / dock["entry_module"]
        tree = _parse(path)
        module_imports = _module_level_imports(tree)
        offenders = [n for n in module_imports if n.split(".")[0] in _QT_BINDING_NAMES]
        assert not offenders, \
            f"{path} imports a Qt binding at module scope: {offenders} " \
            "(must be lazy, inside run() — see DOCK_CONTRACT.md §2)"


def test_dock_source_files_never_import_qt_binding_directly(
    backend_root: Path, backend_docks: list
) -> None:
    """No dock source file — launcher or widget — imports a Qt binding directly, anywhere.

    All Qt access must go through the compat shim (DOCK_CONTRACT.md §6). The
    shim module itself (conventionally named ``qt_compat.py``, e.g.
    ``lib/qt_compat.py``) is the one sanctioned exception — it exists
    precisely to be the single place that imports the bindings.
    """
    for dock in backend_docks:
        entry_path = backend_root / dock["entry_module"]
        dock_dir = entry_path.parent
        py_files = [entry_path] + sorted(dock_dir.rglob("*.py"))
        for path in py_files:
            if not path.exists() or path.name == "qt_compat.py":
                continue
            tree = _parse(path)
            imports = _all_imports(tree)
            offenders = [n for n in imports if n.split(".")[0] in _QT_BINDING_NAMES]
            assert not offenders, \
                f"{path} imports a Qt binding directly: {offenders} (route through qt_compat)"


def test_launcher_has_no_reload_of_shared_prefix(backend_root: Path, backend_docks: list) -> None:
    """No importlib.reload(...) call in the launcher, and no sys.modules purge
    targeting a shared/framework prefix (the DSM rule, statically enforced)."""
    for dock in backend_docks:
        path = backend_root / dock["entry_module"]
        tree = _parse(path)
        assert not _calls_importlib_reload(tree), \
            f"{path} calls importlib.reload() — must be purge-based, not reload-in-place " \
            "(DOCK_CONTRACT.md §7)"

        reload_prefixes = dock.get("reload_prefixes", [])
        forbidden_prefixes = {"shared", "aimsun_psp.shared"}
        for prefix in reload_prefixes:
            assert not any(prefix == fp or prefix.startswith(fp + ".") for fp in forbidden_prefixes), \
                f"dock '{dock['dock_id']}' reload_prefixes includes a shared/framework " \
                f"prefix: '{prefix}' (DOCK_CONTRACT.md §7 forbids this)"


def test_dock_widget_defines_reset_state_and_setup_ui(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        entry_path = backend_root / dock["entry_module"]
        dock_dir = entry_path.parent
        found_widget_module = False
        for path in sorted(dock_dir.rglob("*.py")):
            tree = _parse(path)
            has_class = any(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            if not has_class:
                continue
            if _class_defines_method(tree, "setup_ui") and _class_defines_method(tree, "reset_state"):
                found_widget_module = True
                break
        assert found_widget_module, \
            f"dock '{dock['dock_id']}': no class under {dock_dir} defines both " \
            "setup_ui and reset_state (DOCK_INTERFACE.md §2)"


def test_launcher_dock_key_matches_manifest(backend_root: Path, backend_docks: list) -> None:
    """The dock_key string literal in the launcher equals the manifest dock_key.

    Catches manifest/launcher drift — the dock analogue of describe == backend.json.
    """
    for dock in backend_docks:
        path = backend_root / dock["entry_module"]
        source = path.read_text(encoding="utf-8")
        manifest_key = dock["dock_key"]
        assert manifest_key in source, \
            f"{path} does not contain the manifest dock_key literal '{manifest_key}'"
