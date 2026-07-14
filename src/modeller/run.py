from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .backend import BackendCheck, check_backend_contract, check_backend_manifest, resolve_backend_root
from .contracts import validate_with_contract_schema
from .runtime import runtime_path
from .toml_compat import load_toml


@dataclass
class ResultCheck:
    path: Path
    schema_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def format(self) -> str:
        lines = [f"result check: {'OK' if self.ok else 'FAIL'}", f"path: {self.path}"]
        if self.schema_path:
            lines.append(f"schema: {self.schema_path}")
        lines.extend(f"warning: {warning}" for warning in self.warnings)
        lines.extend(f"error: {error}" for error in self.errors)
        return "\n".join(lines)


@dataclass
class RunResult:
    backend_id: str
    pipeline_id: str
    command: list[str]
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    result_json: Path | None = None
    validation: ResultCheck | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and self.returncode == 0 and bool(self.validation and self.validation.ok)

    def format(self) -> str:
        lines = [f"backend run: {'OK' if self.ok else 'FAIL'}"]
        lines.append(f"backend: {self.backend_id}")
        lines.append(f"pipeline: {self.pipeline_id}")
        lines.append("command: " + " ".join(self.command))
        if self.returncode is not None:
            lines.append(f"returncode: {self.returncode}")
        if self.result_json:
            lines.append(f"result_json: {self.result_json}")
        if self.validation:
            lines.append(self.validation.format())
        if self.stderr.strip():
            lines.append("stderr:")
            lines.append(self.stderr.strip())
        for error in self.errors:
            lines.append(f"error: {error}")
        return "\n".join(lines)


def validate_result_json(
    path: Path,
    root: Path | None = None,
    expected_backend_id: str | None = None,
    expected_contract: str | None = None,
    expected_pipeline_id: str | None = None,
) -> ResultCheck:
    check = ResultCheck(path=path)
    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        check.errors.append("result.json does not exist")
        return check
    except json.JSONDecodeError as exc:
        check.errors.append(f"invalid JSON: {exc}")
        return check

    if root is not None:
        schema_validation = validate_with_contract_schema(root, "result.schema.json", result)
        check.schema_path = schema_validation.schema_path
        check.errors.extend(f"schema {error}" for error in schema_validation.errors)
        check.warnings.extend(schema_validation.warnings)

    for key in ["contract_version", "backend_id", "status"]:
        if key not in result:
            check.errors.append(f"missing {key}")
    if expected_backend_id and result.get("backend_id") != expected_backend_id:
        check.errors.append(f"backend_id {result.get('backend_id')!r} does not match expected {expected_backend_id!r}")
    if expected_contract and result.get("contract_version") != expected_contract:
        check.errors.append(
            f"contract_version {result.get('contract_version')!r} does not match expected {expected_contract!r}"
        )
    if expected_pipeline_id and result.get("pipeline_id") != expected_pipeline_id:
        check.errors.append(f"pipeline_id {result.get('pipeline_id')!r} does not match expected {expected_pipeline_id!r}")
    if result.get("status") not in {"success", "partial", "failed"}:
        check.errors.append("status must be success, partial, or failed")
    steps = result.get("steps", [])
    if "steps" in result and not isinstance(steps, list):
        check.errors.append("steps must be a list when present")
    artifacts = result.get("artifacts", [])
    if "artifacts" in result and not isinstance(artifacts, list):
        check.errors.append("artifacts must be a list when present")
    if result.get("status") == "success":
        if isinstance(steps, list) and not steps:
            check.errors.append("successful results must include at least one step")
        if isinstance(artifacts, list) and not artifacts:
            check.errors.append("successful results must include at least one artifact")
    if isinstance(steps, list):
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                check.errors.append(f"steps[{index}] must be an object")
                continue
            if step.get("status") not in {"success", "failed", "skipped"}:
                check.errors.append(f"steps[{index}].status must be success, failed, or skipped")
            for key in ["step_id", "step_name"]:
                if key not in step:
                    check.errors.append(f"steps[{index}] missing {key}")
            _check_artifacts_relative(step.get("artifacts", []), check, prefix=f"steps[{index}].artifacts")
    if isinstance(artifacts, list):
        _check_artifacts_relative(artifacts, check, prefix="artifacts")
    return check


def validate_backend_json(path: Path, expected_id: str | None = None, root: Path | None = None) -> BackendCheck:
    check = BackendCheck(backend_id=expected_id or path.parent.name, status="manifest")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        check.errors.append("backend.json does not exist")
        return check
    except json.JSONDecodeError as exc:
        check.errors.append(f"invalid JSON: {exc}")
        return check
    check.manifest_path = path
    if root is not None:
        schema_validation = validate_with_contract_schema(root, "backend.schema.json", manifest)
        check.schema_path = schema_validation.schema_path
        check.errors.extend(f"schema {error}" for error in schema_validation.errors)
        check.warnings.extend(schema_validation.warnings)
    check_backend_manifest(manifest, check, expected_id=expected_id)
    return check


def run_backend_pipeline(
    root: Path,
    backend_id: str,
    pipeline_id: str,
    config: Path,
    run_dir: Path,
    backend_root: Path | None = None,
    timeout_s: int = 3600,
) -> RunResult:
    registry = load_toml(runtime_path(root, "backends.toml")).get("backend", {})
    if backend_id not in registry:
        return RunResult(backend_id=backend_id, pipeline_id=pipeline_id, command=[], errors=["backend is not registered"])

    cfg = registry[backend_id]
    backend_root = backend_root or resolve_backend_root(root, backend_id, cfg)
    if backend_root is None:
        return RunResult(
            backend_id=backend_id,
            pipeline_id=pipeline_id,
            command=[],
            errors=["backend root is not configured; pass --backend-root or create backends.local.toml"],
        )
    backend_root = backend_root.resolve()
    manifest_path = backend_root / "backend.json"
    manifest_check = validate_backend_json(
        manifest_path,
        expected_id=backend_id if cfg.get("status") != "planned" else None,
        root=root,
    )
    if not manifest_check.ok:
        return RunResult(
            backend_id=backend_id,
            pipeline_id=pipeline_id,
            command=[],
            errors=manifest_check.errors,
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    check_backend_contract(manifest, manifest_check, expected_contract=cfg.get("expected_contract"))
    if not manifest_check.ok:
        return RunResult(
            backend_id=backend_id,
            pipeline_id=pipeline_id,
            command=[],
            errors=manifest_check.errors,
        )
    if not _pipeline_declared(manifest, pipeline_id):
        return RunResult(
            backend_id=backend_id,
            pipeline_id=pipeline_id,
            command=[],
            errors=[f"pipeline {pipeline_id!r} is not declared in backend.json"],
        )
    runner = manifest["runner"]
    base_command = [str(part) for part in runner["command"]]
    command = base_command + ["run", pipeline_id, "--config", str(config.resolve()), "--run-dir", str(run_dir.resolve())]
    result = RunResult(backend_id=backend_id, pipeline_id=pipeline_id, command=command)
    completed = subprocess.run(
        command,
        cwd=str(backend_root),
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )
    result.returncode = completed.returncode
    result.stdout = completed.stdout
    result.stderr = completed.stderr
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        result.errors.append("backend stdout did not include a result.json path")
        return result
    result.result_json = Path(lines[-1])
    result.validation = validate_result_json(
        result.result_json,
        root=root,
        expected_backend_id=backend_id,
        expected_contract=str(cfg.get("expected_contract") or manifest.get("contract_version") or ""),
        expected_pipeline_id=pipeline_id,
    )
    if completed.returncode != 0:
        result.errors.append("backend command returned non-zero exit code")
    return result


def _pipeline_declared(manifest: dict, pipeline_id: str) -> bool:
    for pipeline in manifest.get("pipelines", []):
        if isinstance(pipeline, dict) and pipeline.get("id") == pipeline_id:
            return True
    return False


def _check_artifacts_relative(artifacts, check: ResultCheck, prefix: str) -> None:
    if not isinstance(artifacts, list):
        check.errors.append(f"{prefix} must be a list when present")
        return
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            check.errors.append(f"{prefix}[{index}] must be an object")
            continue
        path_value = artifact.get("path")
        if path_value is None:
            continue
        artifact_path = Path(str(path_value))
        if artifact_path.is_absolute():
            check.errors.append(f"{prefix}[{index}].path must be relative to run dir")
