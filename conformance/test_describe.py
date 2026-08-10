"""Tests for the `describe` CLI subcommand."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def test_describe_exits_zero(backend_cmd: list[str], backend_root: Path) -> None:
    result = subprocess.run(
        backend_cmd + ["describe", "--json"],
        capture_output=True, text=True, cwd=str(backend_root),
    )
    assert result.returncode == 0, \
        f"`describe --json` exited {result.returncode}\nstderr: {result.stderr}"


def test_describe_emits_json(backend_cmd: list[str], backend_root: Path) -> None:
    result = subprocess.run(
        backend_cmd + ["describe", "--json"],
        capture_output=True, text=True, cwd=str(backend_root),
    )
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"`describe` output is not valid JSON: {e}\nOutput: {result.stdout[:500]}")


def test_describe_matches_backend_json(
    describe_output: dict, backend_root: Path
) -> None:
    on_disk = json.loads((backend_root / "backend.json").read_text())
    assert describe_output["backend_id"] == on_disk["backend_id"]
    assert describe_output["contract_version"] == on_disk["contract_version"]


def test_describe_pipeline_ids_match(
    describe_output: dict, backend_root: Path
) -> None:
    on_disk = json.loads((backend_root / "backend.json").read_text())
    disk_ids = {p["id"] for p in on_disk.get("pipelines", [])}
    live_ids = {p["id"] for p in describe_output.get("pipelines", [])}
    assert live_ids == disk_ids, \
        f"Pipeline ID mismatch: describe={live_ids}, backend.json={disk_ids}"
