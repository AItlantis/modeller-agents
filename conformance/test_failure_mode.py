"""Failure mode conformance tests.

Verifies that a bad/missing config causes a non-zero exit AND a valid
failed result.json — never a crash with no output.
"""
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


def _run_bad(
    backend_cmd: list[str], backend_root: Path, smoke_pipeline: str, tmp_path: Path
) -> tuple[subprocess.CompletedProcess, Path]:
    run_dir = tmp_path / "failure_run"
    run_dir.mkdir()
    bad_config = tmp_path / "bad_config.yml"
    bad_config.write_text(
        "# Deliberately invalid config for the selected smoke pipeline.\n"
        f"pipeline_id: {smoke_pipeline}\n"
        "bogus_field: this_should_not_exist\n"
        "params: {}\n",
    )
    result = subprocess.run(
        backend_cmd + [
            "run", smoke_pipeline,
            "--config", str(bad_config),
            "--run-dir", str(run_dir),
        ],
        capture_output=True, text=True, cwd=str(backend_root),
    )
    return result, run_dir


def test_bad_config_exits_nonzero(
    backend_cmd, backend_root, smoke_pipeline, tmp_path
) -> None:
    result, _ = _run_bad(backend_cmd, backend_root, smoke_pipeline, tmp_path)
    assert result.returncode != 0, \
        "Expected non-zero exit for bad config, but got 0"


def test_bad_config_still_writes_result_json(
    backend_cmd, backend_root, smoke_pipeline, tmp_path
) -> None:
    _, run_dir = _run_bad(backend_cmd, backend_root, smoke_pipeline, tmp_path)
    assert (run_dir / "result.json").exists(), \
        "result.json must be written even on failure"


def test_bad_config_result_status_failed(
    backend_cmd, backend_root, smoke_pipeline, tmp_path
) -> None:
    _, run_dir = _run_bad(backend_cmd, backend_root, smoke_pipeline, tmp_path)
    data = json.loads((run_dir / "result.json").read_text())
    assert data.get("status") == "failed", \
        f"Expected status=failed, got: {data.get('status')}"


def test_bad_config_result_json_valid(
    backend_cmd, backend_root, smoke_pipeline, tmp_path
) -> None:
    _, run_dir = _run_bad(backend_cmd, backend_root, smoke_pipeline, tmp_path)
    data = json.loads((run_dir / "result.json").read_text())
    schema = load_schema("result.schema.json")
    validate_json(data, schema)
