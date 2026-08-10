"""If `describe` output carries docks, it MUST equal on-disk backend.json's
docks — static == dynamic, mirroring test_describe.py's pipeline check.
"""
from __future__ import annotations

from pathlib import Path


def test_describe_docks_match_backend_json(describe_output: dict, backend_root: Path) -> None:
    import json

    on_disk = json.loads((backend_root / "backend.json").read_text())
    on_disk_docks = on_disk.get("docks", [])
    live_docks = describe_output.get("docks", [])
    if not on_disk_docks and not live_docks:
        return  # pipeline-only backend — nothing to compare
    assert live_docks == on_disk_docks, \
        f"docks mismatch: describe={live_docks}, backend.json={on_disk_docks}"


def test_describe_smoke_dock_matches_backend_json(describe_output: dict, backend_root: Path) -> None:
    import json

    on_disk = json.loads((backend_root / "backend.json").read_text())
    assert describe_output.get("smoke_dock") == on_disk.get("smoke_dock")
