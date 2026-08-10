"""Runtime smoke tests — skipped if --skip-runtime is set."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from .helpers import load_schema, validate_json


@pytest.fixture(autouse=True)
def require_runtime(skip_runtime: bool) -> None:
    if skip_runtime:
        pytest.skip("--skip-runtime flag set")


def _run_smoke(
    backend_cmd: list[str],
    backend_root: Path,
    smoke_pipeline: str,
    smoke_config_path: Path | None,
    tmp_path: Path,
) -> tuple[subprocess.CompletedProcess, Path]:
    if smoke_config_path is None:
        pytest.skip("No smoke config available — pass --smoke-config")
    run_dir = tmp_path / "smoke_run"
    run_dir.mkdir()
    result = subprocess.run(
        backend_cmd + [
            "run",
            smoke_pipeline,
            "--config", str(smoke_config_path),
            "--run-dir", str(run_dir),
        ],
        capture_output=True, text=True, cwd=str(backend_root),
    )
    return result, run_dir


def test_smoke_pipeline_declared(describe_output: dict) -> None:
    smoke_id = describe_output.get("smoke_pipeline")
    pipeline_ids = {p["id"] for p in describe_output.get("pipelines", [])}
    assert smoke_id in pipeline_ids, \
        f"smoke_pipeline '{smoke_id}' not in declared pipelines {pipeline_ids}"


def test_run_exits_nonzero_only_on_failure(
    backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
) -> None:
    result, run_dir = _run_smoke(
        backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
    )
    data = json.loads((run_dir / "result.json").read_text())
    assert data["status"] != "failed", \
        f"Smoke run failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
    if data["status"] == "success":
        assert result.returncode == 0, \
            f"Successful smoke run exited {result.returncode}"


def test_run_result_json_written(
    backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
) -> None:
    _, run_dir = _run_smoke(backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path)
    assert (run_dir / "result.json").exists(), "result.json not written to run dir"


def test_run_result_json_valid(
    backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
) -> None:
    _, run_dir = _run_smoke(backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path)
    data = json.loads((run_dir / "result.json").read_text())
    schema = load_schema("result.schema.json")
    validate_json(data, schema)


def test_run_result_status_not_failed(
    backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
) -> None:
    _, run_dir = _run_smoke(backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path)
    data = json.loads((run_dir / "result.json").read_text())
    assert data["status"] in {"success", "partial"}, \
        f"Expected success or partial, got: {data['status']}"


def test_run_artifacts_relative_paths(
    backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
) -> None:
    _, run_dir = _run_smoke(backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path)
    data = json.loads((run_dir / "result.json").read_text())
    all_artifacts = data.get("artifacts", []) + [
        a for s in data.get("steps", []) for a in s.get("artifacts", [])
    ]
    for art in all_artifacts:
        path = art.get("path", "")
        assert not Path(path).is_absolute(), \
            f"Artifact path must be relative, got: {path}"


def test_run_final_stdout_line_is_result_path(
    backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path
) -> None:
    result, run_dir = _run_smoke(backend_cmd, backend_root, smoke_pipeline, smoke_config_path, tmp_path)
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert lines, "No stdout output from run command"
    last_line = lines[-1].strip()
    declared_path = Path(last_line)
    assert declared_path.exists(), \
        f"Last stdout line '{last_line}' is not a path to an existing file"
    assert declared_path.name == "result.json", \
        f"Last stdout line should point to result.json, got: {last_line}"
