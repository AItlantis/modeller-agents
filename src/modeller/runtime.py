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


def has_runtime_bundle(root: Path, target_repository: str) -> bool:
    target = str(target_repository or "").strip()
    if not target:
        return False
    return (runtime_root(root) / "bundles" / f"{target}.bundle.json").exists()


def discover_installed_target_roots(root: Path, target_repository: str) -> list[Path]:
    target = str(target_repository or "").strip()
    if not target or has_runtime_bundle(root, target):
        return []
    root = root.resolve()
    if not root.exists():
        return []
    candidates = [root / target]
    candidates.extend(child / target for child in root.iterdir() if child.is_dir())
    resolved = []
    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        manifest = load_install_manifest(candidate)
        if manifest and has_runtime_bundle(candidate, target):
            resolved.append(candidate)
    return resolved


def discover_installed_target_root(root: Path, target_repository: str) -> Path | None:
    matches = discover_installed_target_roots(root, target_repository)
    return matches[0] if len(matches) == 1 else None


def discover_workspace_source_roots(root: Path, target_repository: str) -> list[Path]:
    target = str(target_repository or "").strip()
    if not target:
        return []
    root = root.resolve()
    candidates: list[Path] = []
    for anchor in _bounded_workspace_anchors(root):
        candidates.append(anchor / target)
        if anchor.exists():
            candidates.extend(child / target for child in anchor.iterdir() if child.is_dir())
    resolved = []
    seen = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if _looks_like_source_root(candidate, target):
            resolved.append(candidate)
    return resolved


def discover_workspace_source_root(root: Path, target_repository: str) -> Path | None:
    matches = discover_workspace_source_roots(root, target_repository)
    return matches[0] if len(matches) == 1 else None


def _bounded_workspace_anchors(root: Path) -> list[Path]:
    anchors = []
    current = root
    for _ in range(4):
        if current in anchors:
            break
        anchors.append(current)
        if current.parent == current:
            break
        current = current.parent
    return anchors


def _looks_like_source_root(path: Path, target_repository: str) -> bool:
    if not path.is_dir() or path.name != target_repository:
        return False
    return (path / ".git").exists() or (path / "README.md").exists() or is_installed_runtime(path)
