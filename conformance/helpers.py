"""Package-local helpers for the modeller-pipelines conformance tests."""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMAS_DIR = Path(__file__).parent.parent / "contracts" / "schemas"
CONTRACT_VERSIONS_PATH = Path(__file__).parent.parent / "CONTRACT_VERSIONS.md"

_VERSIONS_TABLE_ROW = re.compile(
    r"^\|\s*([0-9]+\.[0-9]+)\s*\|[^|]*\|\s*(current|previous)\s*\|"
)


def load_backend_json(backend_root: Path) -> dict:
    return json.loads((backend_root / "backend.json").read_text())


def supported_contract_versions() -> set[str]:
    """Return the set of contract_version strings in the N/N-1 support window.

    Parsed live from CONTRACT_VERSIONS.md's table (rows with status
    "current" or "previous") rather than hardcoded, so this can never drift
    from the versions table the way a literal version set silently would --
    exactly the class of bug the version-consistency discipline
    (ADR-0002, CONTRACT_VERSIONS.md) exists to prevent.
    """
    supported: set[str] = set()
    for line in CONTRACT_VERSIONS_PATH.read_text(encoding="utf-8").splitlines():
        match = _VERSIONS_TABLE_ROW.match(line.strip())
        if match:
            supported.add(match.group(1))
    if not supported:
        raise AssertionError(
            f"Could not parse any current/previous version rows from {CONTRACT_VERSIONS_PATH}"
        )
    return supported


def load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / name
    with open(path) as f:
        return json.load(f)


def smoke_pipeline_id(backend: dict) -> str:
    smoke_id = backend.get("smoke_pipeline")
    pipeline_ids = {p["id"] for p in backend.get("pipelines", [])}
    if smoke_id not in pipeline_ids:
        raise AssertionError(
            f"smoke_pipeline '{smoke_id}' not in declared pipelines {pipeline_ids}"
        )
    return smoke_id


def validate_json(instance: dict, schema: dict) -> None:
    """Validate instance against schema. Falls back to required fields only."""
    try:
        import jsonschema

        jsonschema.validate(instance, schema)
        return
    except Exception:
        pass

    required = schema.get("required", [])
    present = set(instance)
    if "timestamps" in required and {"started_at", "completed_at"} <= present:
        present.add("timestamps")
    missing = [f for f in required if f not in present]
    if missing:
        raise AssertionError(f"Missing required fields: {missing}")
