from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    tomllib = None


def load_toml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)
    return parse_minimal_toml(text)


def parse_minimal_toml(text: str) -> dict:
    data: dict = {}
    current = data
    pending_key = ""
    pending_items: list = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if pending_key:
            if line == "]":
                current[pending_key] = pending_items
                pending_key = ""
                pending_items = []
                continue
            pending_items.append(parse_toml_value(line.rstrip(",")))
            continue
        if line.startswith("[[") and line.endswith("]]"):
            section = line[2:-2].strip()
            current = data
            parts = section.split(".")
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            arr = current.setdefault(parts[-1], [])
            if not isinstance(arr, list):
                raise ValueError(f"TOML array table conflicts with scalar/table: {section}")
            item: dict = {}
            arr.append(item)
            current = item
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            current = data
            for part in section.split("."):
                current = current.setdefault(part, {})
            continue
        if "=" not in line:
            raise ValueError(f"unsupported TOML line: {raw_line}")
        key, value = [part.strip() for part in line.split("=", 1)]
        key = unquote_key(key)
        if value == "[":
            pending_key = key
            pending_items = []
            continue
        current[key] = parse_toml_value(value)

    if pending_key:
        raise ValueError(f"unterminated array for {pending_key}")
    return data


def parse_toml_value(value: str):
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [parse_toml_value(part.strip()) for part in body.split(",")]
    if value.startswith("{") and value.endswith("}"):
        body = value[1:-1].strip()
        table: dict = {}
        if not body:
            return table
        for item in body.split(","):
            if "=" not in item:
                raise ValueError(f"unsupported inline table item: {item}")
            key, item_value = [part.strip() for part in item.split("=", 1)]
            table[key] = parse_toml_value(item_value)
        return table
    return value


def unquote_key(key: str) -> str:
    if key.startswith('"') and key.endswith('"'):
        return key[1:-1]
    return key
