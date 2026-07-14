from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .runtime import runtime_path
from .toml_compat import load_toml


REQUIRED_FIELDS = ["id", "status", "source_repository", "owner", "central_skills", "local_agents_stay_in_source"]
VALID_STATUSES = {"draft", "active", "deprecated"}


@dataclass
class ReferencePackCheck:
    path: Path
    pack_id: str = ""
    skills: list[str] = field(default_factory=list)
    status: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_reference_pack(root: Path, rel_path: str) -> ReferencePackCheck:
    path = runtime_path(root, rel_path)
    check = ReferencePackCheck(path=path)
    try:
        data = load_toml(path)
    except FileNotFoundError:
        check.errors.append(f"reference pack missing: {rel_path}")
        return check
    except Exception as exc:
        check.errors.append(f"reference pack invalid TOML {rel_path}: {exc}")
        return check

    for field_name in REQUIRED_FIELDS:
        if field_name not in data:
            check.errors.append(f"{rel_path}: missing {field_name}")

    check.pack_id = str(data.get("id", ""))
    check.status = str(data.get("status", ""))
    skills = data.get("central_skills", [])
    if not isinstance(skills, list) or not skills or not all(isinstance(item, str) and item for item in skills):
        check.errors.append(f"{rel_path}: central_skills must be a non-empty string array")
    else:
        check.skills = list(skills)
    if check.status and check.status not in VALID_STATUSES:
        check.errors.append(f"{rel_path}: status must be one of {sorted(VALID_STATUSES)}")
    if check.status == "draft":
        check.warnings.append(f"{rel_path}: reference pack is draft")
    if data.get("local_agents_stay_in_source") is not True:
        check.errors.append(f"{rel_path}: local_agents_stay_in_source must be true")

    expected_id = Path(rel_path).stem
    if check.pack_id and check.pack_id != expected_id:
        check.errors.append(f"{rel_path}: id {check.pack_id!r} must match filename stem {expected_id!r}")
    source_repository = data.get("source_repository")
    owner = data.get("owner")
    if source_repository and owner and source_repository != owner:
        check.warnings.append(f"{rel_path}: owner {owner!r} differs from source_repository {source_repository!r}")
    return check
