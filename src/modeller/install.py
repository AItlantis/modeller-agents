from __future__ import annotations

import json
import shutil
import subprocess
import site
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .runtime import DEFAULT_RUNTIME_RELATIVE_PATH, MANIFEST_RELATIVE_PATH, load_install_manifest


@dataclass
class InstallResult:
    target: Path
    dry_run: bool
    actions: list[str] = field(default_factory=list)

    def format(self) -> str:
        mode = "DRY-RUN" if self.dry_run else "APPLIED"
        lines = [f"modeller install: {mode}", f"target: {self.target}"]
        lines.extend(f"  - {action}" for action in self.actions)
        return "\n".join(lines)


RUNTIME_DIRS = ["method", "reference-packs", "bundles", "schemas"]
RUNTIME_FILES = ["backends.toml", "vendors.toml"]
PACKAGED_RUNTIME_ROOT = Path(__file__).resolve().parent / "runtime"
PYTHON_BOOTSTRAP_RELATIVE_PATH = "sitecustomize.py"
PYTHON_BOOTSTRAP_MARKER = "# managed-by: modeller-agents install"
USER_SITE_PTH = "modeller-agents.pth"


def install_plugin(
    root: Path,
    target: Path,
    dry_run: bool = True,
    include_runtime_assets: bool = False,
    install_python_path: bool = False,
) -> InstallResult:
    target = target.resolve()
    root = root.resolve()
    source_root = _resolve_install_source(root)
    result = InstallResult(target=target, dry_run=dry_run)
    plugin_src = source_root / ".claude/plugins/modeller"
    plugin_dst = target / ".claude/plugins/modeller"
    settings_src = source_root / ".claude/settings.json"
    settings_dst = target / ".claude/settings.json"
    mcp_src = source_root / ".mcp.json.example"
    mcp_dst = target / ".mcp.json"
    runtime_dst = target / DEFAULT_RUNTIME_RELATIVE_PATH
    legacy_runtime_assets = _legacy_runtime_assets_to_remove(target) if include_runtime_assets else []

    result.actions.append(f"copy plugin {plugin_src} -> {plugin_dst}")
    result.actions.append(f"merge settings from {settings_src} -> {settings_dst}")
    result.actions.append(f"create or reconcile MCP config from {mcp_src} -> {mcp_dst}")
    if include_runtime_assets:
        for rel in legacy_runtime_assets:
            result.actions.append(f"remove legacy root runtime asset {target / rel}")
        for rel in RUNTIME_DIRS:
            result.actions.append(f"copy runtime directory {source_root / rel} -> {runtime_dst / rel}")
        for rel in RUNTIME_FILES:
            result.actions.append(f"copy runtime file {source_root / rel} -> {runtime_dst / rel}")
    result.actions.append(f"write Python import bootstrap {target / PYTHON_BOOTSTRAP_RELATIVE_PATH}")
    if install_python_path:
        result.actions.append(f"write user-site Python path file {Path(site.getusersitepackages()) / USER_SITE_PTH}")
    result.actions.append(f"write install manifest {target / MANIFEST_RELATIVE_PATH}")
    if dry_run:
        return result

    plugin_dst.parent.mkdir(parents=True, exist_ok=True)
    if plugin_dst.exists():
        shutil.rmtree(plugin_dst)
    shutil.copytree(plugin_src, plugin_dst)
    _merge_settings(settings_src, settings_dst)
    _reconcile_mcp_config(mcp_src, mcp_dst)
    if include_runtime_assets:
        _remove_legacy_runtime_assets(target, legacy_runtime_assets)
        for rel in RUNTIME_DIRS:
            _copytree_replace(source_root / rel, runtime_dst / rel)
        for rel in RUNTIME_FILES:
            _copy_file(source_root / rel, runtime_dst / rel)
    _write_python_bootstrap(source_root, target)
    python_path_file = _write_user_site_python_path(source_root) if install_python_path else None
    _write_install_manifest(source_root, target, include_runtime_assets, python_path_file=python_path_file)
    return result


def _resolve_install_source(root: Path) -> Path:
    if _has_runtime_assets(root):
        return root.resolve()
    if _has_runtime_assets(PACKAGED_RUNTIME_ROOT):
        return PACKAGED_RUNTIME_ROOT.resolve()
    raise FileNotFoundError(
        "could not find modeller runtime assets in the requested root or packaged runtime; "
        "pass --root pointing at a modeller-agents checkout"
    )


def _has_runtime_assets(root: Path) -> bool:
    required = [
        root / ".claude/plugins/modeller",
        root / ".claude/settings.json",
        root / ".mcp.json.example",
        *(root / rel for rel in RUNTIME_DIRS),
        *(root / rel for rel in RUNTIME_FILES),
    ]
    return all(path.exists() for path in required)


def _legacy_runtime_assets_to_remove(target: Path) -> list[str]:
    manifest = load_install_manifest(target)
    copied = manifest.get("copied_runtime_assets", [])
    if not isinstance(copied, list):
        return []
    legacy = set(RUNTIME_DIRS + RUNTIME_FILES)
    return sorted(rel for rel in copied if isinstance(rel, str) and rel in legacy and (target / rel).exists())


def _remove_legacy_runtime_assets(target: Path, rel_paths: list[str]) -> None:
    for rel in rel_paths:
        path = target / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _write_install_manifest(
    root: Path,
    target: Path,
    include_runtime_assets: bool,
    *,
    python_path_file: Path | None = None,
) -> None:
    manifest_path = target / MANIFEST_RELATIVE_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    copied_runtime_assets: list[str] = []
    if include_runtime_assets:
        copied_runtime_assets.extend(f"{DEFAULT_RUNTIME_RELATIVE_PATH}/{rel}" for rel in RUNTIME_DIRS)
        copied_runtime_assets.extend(f"{DEFAULT_RUNTIME_RELATIVE_PATH}/{rel}" for rel in RUNTIME_FILES)
    payload = {
        "schema_version": 1,
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "installer": "modeller-agents",
        "source_root": str(root),
        "source_git": _source_git(root),
        "target_root": str(target),
        "include_runtime_assets": include_runtime_assets,
        "runtime_root": DEFAULT_RUNTIME_RELATIVE_PATH if include_runtime_assets else "",
        "copied_plugin": ".claude/plugins/modeller",
        "merged_settings": ".claude/settings.json",
        "created_mcp_config": ".mcp.json",
        "python_path_bootstrap": PYTHON_BOOTSTRAP_RELATIVE_PATH,
        "python_path_file": str(python_path_file) if python_path_file else "",
        "copied_runtime_assets": copied_runtime_assets,
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_python_bootstrap(root: Path, target: Path) -> None:
    bootstrap_path = target / PYTHON_BOOTSTRAP_RELATIVE_PATH
    if bootstrap_path.exists() and PYTHON_BOOTSTRAP_MARKER not in bootstrap_path.read_text(encoding="utf-8"):
        raise FileExistsError(
            f"{PYTHON_BOOTSTRAP_RELATIVE_PATH} already exists and is not managed by modeller-agents"
        )
    paths = _python_import_paths(root)
    payload = "\n".join(
        [
            PYTHON_BOOTSTRAP_MARKER,
            "from __future__ import annotations",
            "",
            "import sys",
            "",
            f"_MODELLER_AGENT_PATHS = {paths!r}",
            "for _path in reversed(_MODELLER_AGENT_PATHS):",
            "    if _path not in sys.path:",
            "        sys.path.insert(0, _path)",
            "",
        ]
    )
    bootstrap_path.write_text(payload, encoding="utf-8")


def _write_user_site_python_path(root: Path) -> Path:
    user_site = Path(site.getusersitepackages())
    user_site.mkdir(parents=True, exist_ok=True)
    pth_path = user_site / USER_SITE_PTH
    paths = _python_import_paths(root)
    pth_path.write_text("\n".join(paths) + "\n", encoding="utf-8")
    return pth_path


def _python_import_paths(root: Path) -> list[str]:
    candidate_src_roots = [
        root / "src",
        root.parent / "modeller-memory" / "src",
        root.parent / "modeller-pipelines" / "src",
    ]
    return [str(path.resolve()) for path in candidate_src_roots if path.exists()]


def _source_git(root: Path) -> dict[str, str | bool]:
    if not (root / ".git").exists():
        return {"available": False, "status": "not-a-git-worktree"}
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        porcelain = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"available": False, "status": "git-metadata-unavailable"}
    return {
        "available": True,
        "head": head,
        "dirty": bool(porcelain.strip()),
        "status": "dirty-worktree-copy" if porcelain.strip() else "clean-worktree-copy",
    }


def _copytree_replace(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _merge_settings(settings_src: Path, settings_dst: Path) -> None:
    source = json.loads(settings_src.read_text(encoding="utf-8"))
    if settings_dst.exists():
        target = json.loads(settings_dst.read_text(encoding="utf-8"))
    else:
        target = {}
    target.setdefault("extraKnownMarketplaces", {}).update(source.get("extraKnownMarketplaces", {}))
    target.setdefault("enabledPlugins", {}).update(source.get("enabledPlugins", {}))
    target.setdefault("hooks", {}).update(source.get("hooks", {}))
    settings_dst.parent.mkdir(parents=True, exist_ok=True)
    settings_dst.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")


def _reconcile_mcp_config(mcp_src: Path, mcp_dst: Path) -> None:
    if not mcp_dst.exists():
        shutil.copy2(mcp_src, mcp_dst)
        return
    try:
        target = json.loads(mcp_dst.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    servers = target.get("mcpServers")
    if not isinstance(servers, dict):
        return
    memory = servers.get("modeller-memory")
    if isinstance(memory, dict) and memory.get("args") == ["-m", "modeller_memory.mcp"]:
        source = json.loads(mcp_src.read_text(encoding="utf-8"))
        mcp_dst.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
