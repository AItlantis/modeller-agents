from __future__ import annotations

import json
from pathlib import Path


MANIFEST_RELATIVE_PATH = ".modeller/install-manifest.json"
DEFAULT_RUNTIME_RELATIVE_PATH = ".modeller/runtime"


def load_install_manifest(root: Path) -> dict:
    manifest = root / MANIFEST_RELATIVE_PATH
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if payload.get("installer") != "modeller-agents":
        return {}
    return payload


def is_installed_runtime(root: Path) -> bool:
    return bool(load_install_manifest(root))


def runtime_root(root: Path) -> Path:
    manifest = load_install_manifest(root)
    if not manifest:
        return root
    rel = manifest.get("runtime_root")
    if isinstance(rel, str) and rel.strip():
        return root / rel
    return root


def runtime_path(root: Path, *parts: str) -> Path:
    return runtime_root(root).joinpath(*parts)


def runtime_relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def installed_source_root(root: Path) -> Path | None:
    manifest = load_install_manifest(root)
    source_root = manifest.get("source_root")
    if not isinstance(source_root, str) or not source_root.strip():
        return None
    path = Path(source_root)
    return path if path.exists() else None
