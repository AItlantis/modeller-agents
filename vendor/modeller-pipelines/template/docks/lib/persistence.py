# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# Line budget: 90 lines (CI-enforced).
"""persistence — per-model JSON persistence for dock UI state.

Implements contracts/DOCK_CONTRACT.md §9: persisted state is written to a
per-model location and the dock tolerates its absence (fresh defaults).
build_dock_config_path() is host-generic: it asks the model for a document
directory via getDocumentDirectory() if present, else falls back to a
temp-adjacent dotfile so the demo dock works outside a real host too.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Optional


def get_model_document_directory(model) -> Optional[Path]:
    """Return the model's document directory as a Path, or None if unavailable."""
    if model is None or not hasattr(model, "getDocumentDirectory"):
        return None
    try:
        document_directory = model.getDocumentDirectory()
        if document_directory is None:
            return None
        absolute_path = document_directory.absolutePath()
        if not absolute_path:
            return None
        return Path(str(absolute_path))
    except Exception:
        return None


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_") or "dock"


def build_dock_config_path(model, title: str, config_filename: Optional[str] = None) -> Path:
    """Build a per-model config path for a dock widget.

    Falls back to a dotfile under the system temp directory when the model
    has no document directory (e.g. the model is a plain stand-in in tests).
    """
    if config_filename is None:
        config_filename = f".{_safe_filename(title)}_config.json"

    model_dir = get_model_document_directory(model)
    if model_dir is not None:
        return model_dir / config_filename
    return Path(tempfile.gettempdir()) / config_filename


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON from disk with a safe default fallback."""
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload: Any) -> bool:
    """Save JSON to disk, creating the parent directory if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False
