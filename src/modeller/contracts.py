from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .runtime import installed_source_root, runtime_path


IDENTITY_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SHA256_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CURRENT_MISSION_IDENTITY_SCHEMA_VERSION = 1
CURRENT_CHECKPOINT_RECEIPT_SCHEMA_VERSION = 1
VERIFICATION_STATUSES = {"verified", "stale", "incompatible", "malformed", "missing"}
AUTHORIZATION_DECISIONS = {"approved", "approved-with-reservations", "changes-requested", "rejected"}
CURRENT_CAPABILITY_GRANT_SCHEMA_VERSION = 1


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


# ---------------------------------------------------------------------------
# Mission/task identity and checkpoint receipt contracts (modeller-agents-owned).
#
# These bind project/mission/task identity, artifact lineage digests, and
# checkpoint verification/authorization metadata (FR-016, DATA-004, DATA-007).
# They are plain dataclasses validated against modeller-agents' own
# schemas/mission-identity.schema.json and schemas/checkpoint-receipt.schema.json
# and never import or embed any pipeline-owned schema body.
# ---------------------------------------------------------------------------


@dataclass
class ArtifactLineageDigest:
    """A single lineage entry binding a produced artifact to a content digest."""

    artifact_id: str
    digest: str
    produced_at: str
    producer_task_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "digest": self.digest,
            "produced_at": self.produced_at,
            "producer_task_id": self.producer_task_id,
        }


@dataclass
class MissionIdentity:
    """Binds project/mission/task identity plus the artifact lineage produced under it."""

    project_id: str
    mission_id: str
    task_id: str
    created_at: str
    schema_version: int = CURRENT_MISSION_IDENTITY_SCHEMA_VERSION
    parent_mission_id: str | None = None
    binding_scope: str = "task"
    lineage: list[ArtifactLineageDigest] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "parent_mission_id": self.parent_mission_id,
            "created_at": self.created_at,
            "binding_scope": self.binding_scope,
            "lineage": [entry.to_dict() for entry in self.lineage],
        }


@dataclass
class CheckpointAuthorization:
    """The decision/authorization receipt attached to a checkpoint."""

    decision: str
    actor_id: str
    actor_role: str
    actor_type: str = "human"

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "actor_type": self.actor_type,
        }


@dataclass
class CheckpointReceipt:
    """Checkpoint verification metadata: identity binding, digest, and authorization."""

    checkpoint_id: str
    mission_id: str
    task_id: str
    verified_at: str
    verification_status: str
    authorization: CheckpointAuthorization
    subject_digest: str
    schema_version: int = CURRENT_CHECKPOINT_RECEIPT_SCHEMA_VERSION
    expected_schema_version: int | None = None
    observed_schema_version: int | None = None
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = {
            "schema_version": self.schema_version,
            "checkpoint_id": self.checkpoint_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "verified_at": self.verified_at,
            "verification_status": self.verification_status,
            "authorization": self.authorization.to_dict(),
            "subject_digest": self.subject_digest,
            "remediation": list(self.remediation),
        }
        if self.expected_schema_version is not None or self.observed_schema_version is not None:
            payload["schema_compatibility"] = {
                "expected_schema_version": self.expected_schema_version,
                "observed_schema_version": self.observed_schema_version,
                "compatible": self.expected_schema_version == self.observed_schema_version,
            }
        return payload


@dataclass
class IdentityValidation:
    """Validation result carrying typed remediation guidance (DATA-004, DATA-007)."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "remediation": self.remediation,
        }


def own_schema_dir(root: Path) -> Path:
    """Resolve modeller-agents' own schemas/ directory (never a pipeline-owned path)."""

    return runtime_path(root, "schemas")


def _own_schema(root: Path, schema_name: str) -> tuple[dict | None, list[str]]:
    schema_dir = own_schema_dir(root)
    schema_path = schema_dir / schema_name
    if not schema_path.exists():
        return None, [f"schema not found: {schema_path}"]
    try:
        return json.loads(schema_path.read_text(encoding="utf-8-sig")), []
    except json.JSONDecodeError as exc:
        return None, [f"schema is not valid JSON: {exc}"]


def validate_mission_identity(root: Path, payload: dict) -> IdentityValidation:
    """Validate a mission/task identity record; reject missing, stale, or malformed shapes."""

    if not isinstance(payload, dict):
        return IdentityValidation(
            ok=False,
            errors=["mission identity payload must be a JSON object"],
            remediation=["produce a MissionIdentity.to_dict() payload before validating"],
        )
    schema, schema_errors = _own_schema(root, "mission-identity.schema.json")
    if schema is None:
        return IdentityValidation(
            ok=False,
            errors=schema_errors,
            remediation=["ensure schemas/mission-identity.schema.json exists under this repository"],
        )
    validation = SchemaValidation(schema_path=own_schema_dir(root) / "mission-identity.schema.json")
    _validate_schema_value(payload, schema, "$", validation, own_schema_dir(root))
    errors = list(validation.errors)
    remediation: list[str] = []
    warnings: list[str] = list(validation.warnings)

    observed_version = payload.get("schema_version")
    if observed_version is not None and observed_version != CURRENT_MISSION_IDENTITY_SCHEMA_VERSION:
        errors.append(
            f"$.schema_version {observed_version!r} is incompatible with expected "
            f"{CURRENT_MISSION_IDENTITY_SCHEMA_VERSION!r}"
        )
        remediation.append(
            "regenerate the mission identity record with the current schema_version "
            f"({CURRENT_MISSION_IDENTITY_SCHEMA_VERSION})"
        )

    for key in ("project_id", "mission_id", "task_id"):
        value = payload.get(key)
        if isinstance(value, str) and not IDENTITY_TOKEN_RE.fullmatch(value):
            errors.append(f"$.{key} must be a safe identity token")
            remediation.append(f"rename {key} to letters, numbers, dot, underscore, or dash only")

    for index, entry in enumerate(payload.get("lineage", []) if isinstance(payload.get("lineage"), list) else []):
        if not isinstance(entry, dict):
            continue
        digest = entry.get("digest")
        if isinstance(digest, str) and not SHA256_DIGEST_RE.fullmatch(digest):
            errors.append(f"$.lineage[{index}].digest must match sha256:<64 lowercase hex chars>")
            remediation.append(f"recompute the lineage digest for lineage[{index}] before re-submitting")

    if errors and not remediation:
        remediation.append("supply a complete, current-schema mission identity record before proceeding")

    return IdentityValidation(ok=not errors, errors=errors, warnings=warnings, remediation=remediation)


def validate_checkpoint_receipt(
    root: Path,
    payload: dict,
    *,
    mission_identity: dict | None = None,
) -> IdentityValidation:
    """Validate a checkpoint receipt; reject missing, stale, incompatible, or malformed records."""

    if not isinstance(payload, dict):
        return IdentityValidation(
            ok=False,
            errors=["checkpoint receipt payload must be a JSON object"],
            remediation=["produce a CheckpointReceipt.to_dict() payload before validating"],
        )
    schema, schema_errors = _own_schema(root, "checkpoint-receipt.schema.json")
    if schema is None:
        return IdentityValidation(
            ok=False,
            errors=schema_errors,
            remediation=["ensure schemas/checkpoint-receipt.schema.json exists under this repository"],
        )
    validation = SchemaValidation(schema_path=own_schema_dir(root) / "checkpoint-receipt.schema.json")
    _validate_schema_value(payload, schema, "$", validation, own_schema_dir(root))
    errors = list(validation.errors)
    remediation: list[str] = []
    warnings: list[str] = list(validation.warnings)

    observed_version = payload.get("schema_version")
    if observed_version is not None and observed_version != CURRENT_CHECKPOINT_RECEIPT_SCHEMA_VERSION:
        errors.append(
            f"$.schema_version {observed_version!r} is incompatible with expected "
            f"{CURRENT_CHECKPOINT_RECEIPT_SCHEMA_VERSION!r}"
        )
        remediation.append(
            "regenerate the checkpoint receipt with the current schema_version "
            f"({CURRENT_CHECKPOINT_RECEIPT_SCHEMA_VERSION})"
        )

    status = payload.get("verification_status")
    if status is not None and status not in VERIFICATION_STATUSES:
        errors.append(f"$.verification_status must be one of {sorted(VERIFICATION_STATUSES)}")
        remediation.append("re-run checkpoint verification and record a recognised verification_status")
    elif status in {"stale", "incompatible", "malformed", "missing"}:
        errors.append(f"checkpoint receipt verification_status is {status!r}, not verified")
        remediation.append(f"resolve the {status} checkpoint condition and re-verify before authorization is honoured")

    authorization = payload.get("authorization")
    if isinstance(authorization, dict):
        decision = authorization.get("decision")
        if decision is not None and decision not in AUTHORIZATION_DECISIONS:
            errors.append(f"$.authorization.decision must be one of {sorted(AUTHORIZATION_DECISIONS)}")
            remediation.append("obtain a valid authorization decision before treating the checkpoint as passed")

    digest = payload.get("subject_digest")
    if isinstance(digest, str) and not SHA256_DIGEST_RE.fullmatch(digest):
        errors.append("$.subject_digest must match sha256:<64 lowercase hex chars>")
        remediation.append("recompute subject_digest from the checkpoint subject before re-submitting")

    if mission_identity is not None:
        for key in ("mission_id", "task_id"):
            if payload.get(key) != mission_identity.get(key):
                errors.append(f"$.{key} does not match bound mission identity {mission_identity.get(key)!r}")
                remediation.append(f"bind the checkpoint receipt to the correct {key} before re-submitting")

    if errors and not remediation:
        remediation.append("supply a complete, current-schema checkpoint receipt before proceeding")

    return IdentityValidation(ok=not errors, errors=errors, warnings=warnings, remediation=remediation)


# ---------------------------------------------------------------------------
# Mission-scoped capability grants and hard identity binding at role dispatch
# (FR-003 mission-scoped capability grants, FR-004 hard identity binding,
# SEC-001 least privilege, SEC-003 path containment).
#
# A CapabilityGrant is the policy ceiling a mission or provider is willing to
# extend to a dispatched role: which tools it may invoke, which paths it may
# touch, which commands are forbidden, and which write roots are in scope.
# validate_dispatch_request() enforces that a concrete dispatch request never
# exceeds that ceiling. validate_dispatch_identity_binding() enforces that the
# receipt returned by a dispatched role is provably the same role/agent/
# provider that the request was issued to, over the same request digest, so a
# receipt cannot be silently swapped for one produced under a different
# identity or a different request.
#
# This module defines no pipeline-owned shape: it consumes the existing
# source-boundary-check discipline (containment of paths under declared
# roots) as plain dataclasses/functions, not a new pipeline-capability-profile
# schema. It intentionally does not read or reference any
# contracts/*.schema.json file.
# ---------------------------------------------------------------------------


@dataclass
class CapabilityGrant:
    """The policy ceiling a mission/provider extends to a dispatched role (SEC-001)."""

    role: str
    allowed_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    forbidden_commands: list[str] = field(default_factory=list)
    write_scope: list[str] = field(default_factory=list)
    schema_version: int = CURRENT_CAPABILITY_GRANT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "role": self.role,
            "allowed_tools": list(self.allowed_tools),
            "allowed_paths": list(self.allowed_paths),
            "forbidden_commands": list(self.forbidden_commands),
            "write_scope": list(self.write_scope),
        }


def _grant_normalise_path(path: str) -> str:
    value = str(path or "").strip().strip("`'\"")
    value = value.replace("\\", "/")
    value = re.sub(r"/+", "/", value)
    return value.strip("/")


def _grant_path_is_safe(path: str) -> bool:
    value = _grant_normalise_path(path)
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    return ".." not in value.split("/")


def _grant_path_within_roots(path: str, roots: list[str]) -> bool:
    value = _grant_normalise_path(path)
    for root in roots:
        prefix = _grant_normalise_path(root)
        if not prefix:
            continue
        if value == prefix or value.startswith(prefix + "/"):
            return True
    return False


def validate_dispatch_request(
    grant: dict,
    request: dict,
) -> IdentityValidation:
    """Reject a dispatch request whose declared tools/paths/commands/write-scope

    exceed the mission/provider capability grant (SEC-001 least privilege,
    SEC-003 path containment). ``grant`` and ``request`` are plain dicts
    (e.g. ``CapabilityGrant.to_dict()``); this performs no pipeline-schema
    lookups.
    """

    errors: list[str] = []
    remediation: list[str] = []
    warnings: list[str] = []

    if not isinstance(grant, dict):
        return IdentityValidation(
            ok=False,
            errors=["capability grant payload must be a JSON object"],
            remediation=["produce a CapabilityGrant.to_dict() payload before dispatch"],
        )
    if not isinstance(request, dict):
        return IdentityValidation(
            ok=False,
            errors=["dispatch request payload must be a JSON object"],
            remediation=["produce a dispatch request payload before validating"],
        )

    if request.get("role") != grant.get("role"):
        errors.append(f"$.role {request.get('role')!r} does not match granted role {grant.get('role')!r}")
        remediation.append("dispatch the request against the capability grant issued for the same role")

    allowed_tools = set(grant.get("allowed_tools", []) or [])
    for tool in request.get("tools", []) or []:
        if tool not in allowed_tools:
            errors.append(f"$.tools requests ungranted tool {tool!r}")
            remediation.append(f"remove {tool!r} from the request or extend the mission capability grant")

    allowed_paths = [str(path) for path in (grant.get("allowed_paths", []) or [])]
    for path in request.get("paths", []) or []:
        path_str = str(path)
        if not _grant_path_is_safe(path_str):
            errors.append(f"$.paths contains unsafe path {path!r}")
            remediation.append(f"use a safe repository-relative path instead of {path!r}")
        elif not _grant_path_within_roots(path_str, allowed_paths):
            errors.append(f"$.paths path {path!r} is outside granted allowed_paths")
            remediation.append(f"request a path under the granted allowed_paths instead of {path!r}")

    forbidden_commands = [str(command).lower() for command in (grant.get("forbidden_commands", []) or [])]
    for command in request.get("commands", []) or []:
        command_text = " ".join(str(part) for part in command) if isinstance(command, list) else str(command)
        command_text = command_text.lower()
        for forbidden in forbidden_commands:
            if forbidden and forbidden in command_text:
                errors.append(f"$.commands contains forbidden command {forbidden!r}")
                remediation.append(f"remove the forbidden command {forbidden!r} from the dispatch request")

    write_scope = [str(path) for path in (grant.get("write_scope", []) or [])]
    for path in request.get("write_scope", []) or []:
        path_str = str(path)
        if not _grant_path_is_safe(path_str):
            errors.append(f"$.write_scope contains unsafe path {path!r}")
            remediation.append(f"use a safe repository-relative write path instead of {path!r}")
        elif not _grant_path_within_roots(path_str, write_scope):
            errors.append(f"$.write_scope path {path!r} exceeds granted write_scope")
            remediation.append(f"request a write path under the granted write_scope instead of {path!r}")

    if errors and not remediation:
        remediation.append("reduce the dispatch request to the mission/provider capability grant before re-submitting")

    return IdentityValidation(ok=not errors, errors=errors, warnings=warnings, remediation=remediation)


def validate_dispatch_identity_binding(
    request: dict,
    receipt: dict,
) -> IdentityValidation:
    """Reject a receipt whose role, agent, provider, or request digest differs

    from the request it was dispatched under (FR-004 hard identity binding).
    A receipt that silently changes role/agent/provider, or whose
    request_digest does not match the digest of the actual request payload,
    is rejected fail-closed rather than accepted with a warning.
    """

    errors: list[str] = []
    remediation: list[str] = []

    if not isinstance(request, dict):
        return IdentityValidation(
            ok=False,
            errors=["dispatch request payload must be a JSON object"],
            remediation=["produce a dispatch request payload before validating the receipt"],
        )
    if not isinstance(receipt, dict):
        return IdentityValidation(
            ok=False,
            errors=["dispatch receipt payload must be a JSON object"],
            remediation=["produce a dispatch receipt payload before validating"],
        )

    for key in ("role", "agent_id", "provider"):
        request_value = request.get(key)
        receipt_value = receipt.get(key)
        if request_value is None:
            continue
        if receipt_value != request_value:
            errors.append(f"$.{key} {receipt_value!r} does not match dispatch request {request_value!r}")
            remediation.append(f"re-dispatch or re-issue the receipt with the correct {key} before accepting it")

    request_digest = request.get("request_digest")
    receipt_digest = receipt.get("request_digest")
    if request_digest is not None:
        if receipt_digest != request_digest:
            errors.append(
                f"$.request_digest {receipt_digest!r} does not match dispatch request digest {request_digest!r}"
            )
            remediation.append("bind the receipt to the exact request_digest of the dispatch request before accepting it")

    if errors and not remediation:
        remediation.append("re-issue a receipt bound to the correct role, agent, provider, and request digest")

    return IdentityValidation(ok=not errors, errors=errors, warnings=[], remediation=remediation)
