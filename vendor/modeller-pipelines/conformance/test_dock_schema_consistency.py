"""Schema-consistency test: the docks[] entry inlined in backend.schema.json
must stay field-for-field identical to the standalone dock.schema.json.

Guards the inline-vs-standalone duplication introduced because the repo's
schemas are deliberately self-contained (no cross-file $ref), per the plan
that added the dock artefact type in contract-v1.1.
"""
from __future__ import annotations

from .helpers import load_schema


def test_inlined_docks_items_matches_standalone_dock_schema() -> None:
    backend_schema = load_schema("backend.schema.json")
    dock_schema = load_schema("dock.schema.json")

    inlined = backend_schema["properties"]["docks"]["items"]

    # Compare the parts that must be identical: required + properties.
    # (The standalone schema carries its own $schema/$id/title; the inlined
    # object intentionally has none of those — only required + properties.)
    assert inlined["type"] == dock_schema["type"]
    assert inlined["required"] == dock_schema["required"]
    assert inlined["properties"] == dock_schema["properties"]
