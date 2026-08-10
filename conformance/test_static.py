"""Static conformance tests — no backend runtime needed.

These tests validate backend.json and pipeline.yml files against the
contract schemas, and check structural consistency.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from .helpers import load_backend_json, load_schema, supported_contract_versions, validate_json


def test_backend_json_exists(backend_root: Path) -> None:
    assert (backend_root / "backend.json").exists(), \
        f"backend.json not found at {backend_root}"


def test_backend_json_is_valid_json(backend_root: Path) -> None:
    content = (backend_root / "backend.json").read_text()
    json.loads(content)  # raises on invalid JSON


def test_backend_json_validates_schema(backend_root: Path) -> None:
    data = load_backend_json(backend_root)
    schema = load_schema("backend.schema.json")
    validate_json(data, schema)


def test_backend_json_has_required_fields(backend_root: Path) -> None:
    data = load_backend_json(backend_root)
    for field in ("backend_id", "contract_version", "pipelines", "smoke_pipeline"):
        assert field in data, f"backend.json missing field: {field}"


def test_contract_version_supported(backend_root: Path) -> None:
    data = load_backend_json(backend_root)
    version = data.get("contract_version", "")
    supported = supported_contract_versions()  # N and N-1, parsed from CONTRACT_VERSIONS.md
    assert version in supported, \
        f"contract_version '{version}' not in supported window {supported}"


def test_pipeline_ymls_exist(backend_root: Path) -> None:
    data = load_backend_json(backend_root)
    for pipeline in data.get("pipelines", []):
        yml_path = backend_root / pipeline["definition"]
        assert yml_path.exists(), f"Pipeline yml not found: {yml_path}"


def test_pipeline_ymls_are_valid_yaml(backend_root: Path) -> None:
    pytest.importorskip("yaml", reason="PyYAML required for YAML validation")
    import yaml
    data = load_backend_json(backend_root)
    for pipeline in data.get("pipelines", []):
        yml_path = backend_root / pipeline["definition"]
        with open(yml_path) as f:
            content = yaml.safe_load(f)
        assert isinstance(content, dict), f"Pipeline yml is not a dict: {yml_path}"


def test_pipeline_ymls_validate_schema(backend_root: Path) -> None:
    pytest.importorskip("yaml", reason="PyYAML required")
    import yaml
    schema = load_schema("pipeline.schema.json")
    data = load_backend_json(backend_root)
    for pipeline in data.get("pipelines", []):
        yml_path = backend_root / pipeline["definition"]
        with open(yml_path) as f:
            content = yaml.safe_load(f)
        validate_json(content, schema)


def test_pipeline_ids_consistent(backend_root: Path) -> None:
    pytest.importorskip("yaml", reason="PyYAML required")
    import yaml
    data = load_backend_json(backend_root)
    for pipeline in data.get("pipelines", []):
        declared_id = pipeline["id"]
        yml_path = backend_root / pipeline["definition"]
        with open(yml_path) as f:
            content = yaml.safe_load(f)
        yml_id = content.get("pipeline_id")
        assert yml_id == declared_id, \
            f"ID mismatch: backend.json says '{declared_id}', yml says '{yml_id}'"
