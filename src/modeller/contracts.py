from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .runtime import installed_source_root


@dataclass
class SchemaValidation:
    schema_path: Path | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve_schema_dir(root: Path) -> Path | None:
    candidates = [
        root / "vendor/modeller-pipelines/contracts/schemas",
        root.parent / "modeller-pipelines/contracts/schemas",
    ]
    source_root = installed_source_root(root)
    if source_root is not None:
        candidates.extend(
            [
                source_root / "vendor/modeller-pipelines/contracts/schemas",
                source_root.parent / "modeller-pipelines/contracts/schemas",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def validate_with_contract_schema(root: Path, schema_name: str, value) -> SchemaValidation:
    schema_dir = resolve_schema_dir(root)
    if schema_dir is None:
        return SchemaValidation(
            schema_path=None,
            warnings=["modeller-pipelines contract schemas not found; used built-in shape checks only"],
        )
    schema_path = schema_dir / schema_name
    if not schema_path.exists():
        return SchemaValidation(schema_path=schema_path, errors=[f"schema not found: {schema_path}"])
    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    validation = SchemaValidation(schema_path=schema_path)
    _validate_schema_value(value, schema, "$", validation, schema_dir)
    return validation


def _validate_schema_value(value, schema: dict, path: str, validation: SchemaValidation, schema_dir: Path) -> None:
    if "$ref" in schema:
        ref_schema = _resolve_ref(schema["$ref"], schema_dir)
        if ref_schema is None:
            validation.errors.append(f"{path}: unsupported or missing schema ref {schema['$ref']}")
            return
        _validate_schema_value(value, ref_schema, path, validation, schema_dir)
        return

    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(value, expected_type):
        validation.errors.append(f"{path}: expected type {expected_type}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        validation.errors.append(f"{path}: expected one of {schema['enum']}, got {value!r}")
    if "pattern" in schema and isinstance(value, str) and not re.match(schema["pattern"], value):
        validation.errors.append(f"{path}: value {value!r} does not match pattern {schema['pattern']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                validation.errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                _validate_schema_value(value[key], child_schema, f"{path}.{key}", validation, schema_dir)

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < int(min_items):
            validation.errors.append(f"{path}: expected at least {min_items} items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate_schema_value(item, item_schema, f"{path}[{index}]", validation, schema_dir)


def _resolve_ref(ref: str, schema_dir: Path) -> dict | None:
    if ref.startswith("#/$defs/"):
        # Local $defs are handled by resolving through result.schema.json, the only current shared def file.
        schema = json.loads((schema_dir / "result.schema.json").read_text(encoding="utf-8-sig"))
        current = schema
        for part in ref.lstrip("#/").split("/"):
            current = current.get(part)
            if current is None:
                return None
        return current
    if ref.endswith(".schema.json"):
        target = schema_dir / ref
        if target.exists():
            return json.loads(target.read_text(encoding="utf-8-sig"))
    if ".schema.json#/" in ref:
        filename, pointer = ref.split("#/", 1)
        target = schema_dir / filename
        if not target.exists():
            return None
        current = json.loads(target.read_text(encoding="utf-8-sig"))
        for part in pointer.split("/"):
            current = current.get(part)
            if current is None:
                return None
        return current
    return None


def _type_matches(value, expected) -> bool:
    if isinstance(expected, list):
        return any(_type_matches(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True
