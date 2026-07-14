from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .runtime import runtime_path
from .toml_compat import load_toml


@dataclass
class BackendCheck:
    backend_id: str
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest_path: Path | None = None
    schema_path: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def list_backend_ids(root: Path) -> list[str]:
    data = load_toml(runtime_path(root, "backends.toml"))
    return sorted(data.get("backend", {}).keys())


def check_backend(root: Path, backend_id: str) -> BackendCheck:
    registry = load_toml(runtime_path(root, "backends.toml")).get("backend", {})
    if backend_id not in registry:
        return BackendCheck(backend_id=backend_id, status="missing", errors=["backend is not registered"])

    cfg = registry[backend_id]
    check = BackendCheck(backend_id=backend_id, status=str(cfg.get("status", "")))
    if cfg.get("backend_id") != backend_id:
        check.errors.append("registry backend_id does not match table name")
    if cfg.get("status") not in {"planned", "active", "disabled"}:
        check.errors.append("registry status must be planned, active, or disabled")

    local_root = resolve_backend_root(root, backend_id, cfg)
    if cfg.get("status") == "planned":
        check.warnings.append("backend is planned; local manifest check is optional")
        if local_root is None:
            return check
    if local_root is None:
        check.errors.append("backend local root is not configured")
        return check
    if not local_root.exists():
        check.errors.append(f"backend local root does not exist: {local_root}")
        return check

    manifest_path = local_root / "backend.json"
    check.manifest_path = manifest_path
    if not manifest_path.exists():
        check.errors.append(f"backend manifest missing: {manifest_path}")
        return check

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    check_backend_manifest(manifest, check, expected_id=backend_id)
    check_backend_contract(manifest, check, expected_contract=cfg.get("expected_contract"))
    return check


def resolve_backend_root(root: Path, backend_id: str, cfg: dict | None = None) -> Path | None:
    cfg = cfg or load_toml(runtime_path(root, "backends.toml")).get("backend", {}).get(backend_id, {})
    local_path = root / "backends.local.toml"
    if not local_path.exists():
        return None
    local = load_toml(local_path)
    key = str(cfg.get("local_root_key") or backend_id)
    value = local.get("roots", {}).get(key)
    return Path(value).expanduser() if value else None


def check_backend_manifest(manifest: dict, check: BackendCheck, expected_id: str | None = None) -> None:
    required = ["backend_id", "contract_version", "runner", "pipelines"]
    for key in required:
        if key not in manifest:
            check.errors.append(f"backend.json missing {key}")
    if expected_id and manifest.get("backend_id") != expected_id:
        check.errors.append(f"backend.json backend_id {manifest.get('backend_id')!r} != {expected_id!r}")
    runner = manifest.get("runner")
    if not isinstance(runner, dict):
        check.errors.append("backend.json runner must be an object")
    elif not runner.get("command"):
        check.errors.append("backend.json runner.command is required")
    pipelines = manifest.get("pipelines")
    if not isinstance(pipelines, list) or not pipelines:
        check.errors.append("backend.json pipelines must be a non-empty list")


def check_backend_contract(manifest: dict, check: BackendCheck, expected_contract: str | None = None) -> None:
    if not expected_contract:
        return
    actual_contract = manifest.get("contract_version")
    if actual_contract != expected_contract:
        check.errors.append(
            f"contract_version {actual_contract!r} does not match expected {expected_contract!r}"
        )


def format_backend_check(check: BackendCheck) -> str:
    lines = [f"backend {check.backend_id}: {'OK' if check.ok else 'FAIL'} ({check.status})"]
    if check.manifest_path:
        lines.append(f"manifest: {check.manifest_path}")
    if check.schema_path:
        lines.append(f"schema: {check.schema_path}")
    for warning in check.warnings:
        lines.append(f"warning: {warning}")
    for error in check.errors:
        lines.append(f"error: {error}")
    return "\n".join(lines)
