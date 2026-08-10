from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_modules_do_not_import_vault_doctor() -> None:
    offenders: list[str] = []
    src = ROOT / "src" / "modeller_memory"
    for path in src.rglob("*.py"):
        rel = path.relative_to(src).as_posix()
        if rel.startswith("tools/vault_doctor/"):
            continue
        text = path.read_text(encoding="utf-8")
        if "vault_doctor" in text:
            offenders.append(rel)

    assert offenders == []


def test_runtime_modules_do_not_perform_file_io() -> None:
    offenders: list[str] = []
    for path in _runtime_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT / "src" / "modeller_memory").as_posix()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"pathlib", "os", "shutil"}:
                        offenders.append(f"{rel}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in {"pathlib", "os", "shutil"}:
                    offenders.append(f"{rel}: from {node.module} import ...")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    offenders.append(f"{rel}: open()")
                elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "open",
                    "read_text",
                    "read_bytes",
                    "write_text",
                    "write_bytes",
                }:
                    offenders.append(f"{rel}: .{node.func.attr}()")

    assert offenders == []


def _runtime_paths() -> list[Path]:
    src = ROOT / "src" / "modeller_memory"
    paths = [src / "__init__.py"]
    paths.extend((src / "candidate").glob("*.py"))
    paths.extend((src / "companion").glob("*.py"))
    paths.extend((src / "policy").glob("*.py"))
    return sorted(paths)
