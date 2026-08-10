"""Static conformance tests for declared docks — no backend runtime, no Qt.

Validates backend.json's docks[] entries against dock.schema.json and checks
structural consistency (unique ids, resolvable paths, non-empty doc files).
Backends with no docks[] (pipeline-only, 1.0-era) pass trivially — see the
``backend_docks`` fixture in conftest.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from .helpers import load_schema, validate_json


def test_dock_entries_validate_schema(backend_docks: list) -> None:
    schema = load_schema("dock.schema.json")
    for dock in backend_docks:
        validate_json(dock, schema)


def test_dock_ids_unique(backend_docks: list) -> None:
    ids = [d["dock_id"] for d in backend_docks]
    assert len(ids) == len(set(ids)), f"Duplicate dock_id values: {ids}"


def test_dock_key_matches_versioned_pattern(backend_docks: list) -> None:
    import re

    pattern = re.compile(r"^[a-z0-9]([a-z0-9_.-]*[a-z0-9])?\.v[0-9]+$")
    for dock in backend_docks:
        key = dock["dock_key"]
        assert pattern.match(key), f"dock_key '{key}' does not match the versioned pattern"


def test_dock_area_in_enum(backend_docks: list) -> None:
    for dock in backend_docks:
        area = dock.get("area", "right")
        assert area in {"left", "right", "top", "bottom"}, \
            f"dock '{dock['dock_id']}' has invalid area: {area}"


def test_dock_entry_module_exists(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        entry_path = backend_root / dock["entry_module"]
        assert entry_path.exists(), \
            f"dock '{dock['dock_id']}' entry_module not found: {entry_path}"


def test_dock_doc_exists_and_nonempty(backend_root: Path, backend_docks: list) -> None:
    for dock in backend_docks:
        doc_path = backend_root / dock["doc"]
        assert doc_path.exists(), f"dock '{dock['dock_id']}' doc not found: {doc_path}"
        assert doc_path.read_text(encoding="utf-8").strip(), \
            f"dock '{dock['dock_id']}' doc is empty: {doc_path}"


def test_bad_dock_manifest_rejected() -> None:
    """The bundled bad-manifest fixture (missing dock_id/dock_key) must fail schema validation."""
    import json

    fixture = Path(__file__).parent / "fixtures" / "bad_dock_manifest.json"
    data = json.loads(fixture.read_text())
    schema = load_schema("dock.schema.json")
    with pytest.raises(AssertionError):
        validate_json(data, schema)
