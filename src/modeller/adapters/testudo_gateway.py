"""Governed Testudo Gateway boundary for mission and pipeline orchestration.

The adapter owns the boundary shape only.  It does not know a Testudo URL,
credentials, registry client, or database connection.  Production calls use an
explicitly activated HTTP transport; deterministic test doubles are injectable.
"""

# The adapter intentionally keeps one compact boundary module. These limits
# describe the transport/result seam rather than production domain logic.
# pylint: disable=import-error,line-too-long,too-few-public-methods,too-many-arguments,too-many-instance-attributes,too-many-locals,too-many-return-statements,too-many-lines,too-many-branches,too-many-statements

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from modeller.contracts import IDENTITY_TOKEN_RE, validate_with_contract_schema
from modeller.toml_compat import load_toml


EXPECTED_PIPELINES_CONTRACT = "1.2"
PINNED_PIPELINES_CONTRACT_SHA = "dbd00cb1299f3f68add0e5971e6ec808f010059d"
CONTRACT_VERSION_FILE = Path("vendor/modeller-pipelines/contracts/VERSION")
IDENTITY_FIELDS = (
    "task_id",
    "attempt_id",
    "mission_id",
    "correlation_id",
    "pipeline_execution_id",
    "workflow_id",
    "workflow_run_id",
    "principal_id",
    "scope",
    "scope_context",
)
REQUIRED_IDENTITY_FIELDS = ("mission_id", "task_id")
REQUIRED_EXECUTION_IDENTITY_FIELDS = (
    "mission_id",
    "task_id",
    "attempt_id",
    "pipeline_execution_id",
)
NOTEBOOK_OPERATION_FIELDS = ("notebook_session_id", "cell_id", "correlation", "payload")
PIPELINE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
RECEIPT_STATUSES = {"completed", "success", "partial", "failed", "cancelled", "recovery_required"}
CANONICAL_JSON_VERSION = "testudo-canonical-json-v1"
IDEMPOTENCY_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
APPROVED_PLAN_REF_FIELDS = ("approved_plan_ref", "approved_plan_reference", "plan_ref", "plan_reference")
APPROVED_PLAN_DIGEST_FIELDS = ("approved_plan_digest", "plan_digest")
BASELINE_REF_FIELDS = ("baseline_ref", "baseline_reference")
BASELINE_DIGEST_FIELDS = ("baseline_digest",)
ACTIVATION_PREPARATION_BACKEND_ID = "aimsun-psp"
ACTIVATION_PREPARATION_CREDENTIAL_SOURCE = "ephemeral_env_or_secret_injection"
ACTIVATION_PREPARATION_FIELDS = frozenset(
    {
        "backend_id",
        "contract_version",
        "contract_digest",
        "activation",
        "credential_source",
        "network_calls_allowed",
        "transport_calls_allowed",
        "canary_stop_criteria",
        "rollback_steps",
        "activation_owner",
        "abort_authority",
        "evidence_digest",
        "zero_call_assertions",
    }
)
ACTIVATION_PREPARATION_REQUIRED_FIELDS = ACTIVATION_PREPARATION_FIELDS
ACTIVATION_PREPARATION_EVIDENCE_FIELDS = tuple(
    sorted(ACTIVATION_PREPARATION_FIELDS - {"evidence_digest"})
)
ACTIVATION_PREPARATION_PLACEHOLDER_RE = re.compile(
    r"(?:^|[\s_:/.-])(placeholder|tbd|todo|unknown|unset|replace[-_ ]?me|example|changeme|n/?a)(?:$|[\s_:/.-])",
    re.IGNORECASE,
)


class TestudoGatewayError(ValueError):
    """Base error for rejected gateway requests."""


class ContractMismatchError(TestudoGatewayError):
    """Raised by :meth:`require_contract` when the pinned contract is stale."""


class SchemaRejectedError(TestudoGatewayError):
    """Raised by callers that choose exception-based validation."""


class IdempotencyConflictError(TestudoGatewayError):
    """Raised when one idempotency key is reused for a different payload."""


class TransportError(RuntimeError):
    """A retryable failure reported by an injected transport."""


class TransportConfigurationError(TestudoGatewayError):
    """Raised when no explicitly activated Testudo transport is configured."""


class CanonicalizationError(TestudoGatewayError):
    """Raised when a value cannot be represented by Testudo's typed JSON contract."""


@dataclass(frozen=True)
class GatewayIdempotencyPolicy:
    """UTC retention policy for terminal gateway idempotency records."""

    retention_days: int = 30
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def __post_init__(self) -> None:
        if isinstance(self.retention_days, bool) or not isinstance(self.retention_days, int):
            raise ValueError("retention_days must be an integer")
        if not 0 <= self.retention_days <= 3650:
            raise ValueError("retention_days must be between 0 and 3650")
        if not callable(self.clock):
            raise ValueError("clock must be callable")
        observed = self.clock()
        if not isinstance(observed, datetime) or observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("GatewayIdempotencyPolicy clock must return a UTC-aware datetime")

    def utc_now(self) -> datetime:
        """Return the injected clock value normalized to UTC, fail closed."""

        observed = self.clock()
        if not isinstance(observed, datetime) or observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("GatewayIdempotencyPolicy clock must return a UTC-aware datetime")
        return observed.astimezone(timezone.utc)

    def retention_until(self, terminal_completed_at: datetime | None = None) -> datetime:
        """Calculate expiry from terminal completion in UTC."""

        completed = terminal_completed_at or self.utc_now()
        if completed.tzinfo is None or completed.utcoffset() is None:
            raise ValueError("terminal completion must be UTC-aware")
        return completed.astimezone(timezone.utc) + timedelta(days=self.retention_days)


@dataclass(frozen=True)
class ContractValidation:
    """Result of checking the local modeller-pipelines contract pin."""

    ok: bool
    expected_version: str
    observed_version: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    contract_sha: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the validation result as a JSON-shaped mapping."""

        return {
            "ok": self.ok,
            "expected_version": self.expected_version,
            "observed_version": self.observed_version,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "contract_sha": self.contract_sha,
        }


@dataclass(frozen=True)
class ActivationPreparationValidation:
    """Result of validating the offline activation-preparation contract."""

    ok: bool
    manifest: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    zero_call_assertions: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the validation result as a JSON-shaped mapping."""

        return {
            "ok": self.ok,
            "manifest": copy.deepcopy(self.manifest),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "zero_call_assertions": dict(self.zero_call_assertions),
        }


@dataclass(frozen=True)
class GatewayResult:
    """Stable result shape returned by every adapter operation."""

    ok: bool
    operation: str
    payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    idempotency_key: str | None = None
    correlation_id: str | None = None
    attempts: int = 0
    duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the gateway result as a JSON-shaped mapping."""

        return {
            "ok": self.ok,
            "operation": self.operation,
            "payload": copy.deepcopy(self.payload),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "attempts": self.attempts,
            "duplicate": self.duplicate,
        }

    def __getitem__(self, key: str) -> Any:
        """Allow callers to inspect results using the established dict style."""

        return self.to_dict()[key]


@runtime_checkable
class TestudoTransport(Protocol):
    """Minimal injectable transport for the Testudo control-plane boundary."""

    def send(self, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        """Send one already-validated request and return a response mapping."""


@dataclass(frozen=True)
class TestudoTransportConfig:
    """Explicit, non-provider configuration for the Testudo HTTP boundary."""

    base_url: str
    capability_token: str | None = None
    timeout_seconds: float = 30.0
    api_prefix: str = "/api/v1"
    activation: bool = False
    notebook_origin: str | None = None
    notebook_relay_token: str | None = None

    def __post_init__(self) -> None:
        base_url = self.base_url.strip().rstrip("/")
        if not base_url or not re.match(r"^https?://", base_url, re.IGNORECASE):
            raise TransportConfigurationError("Testudo base_url must be an explicit http(s) URL")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise TransportConfigurationError("Testudo timeout_seconds must be positive")
        if not self.api_prefix.startswith("/"):
            raise TransportConfigurationError("Testudo api_prefix must start with '/'")
        if self.activation and not self.capability_token:
            raise TransportConfigurationError("activated Testudo transport requires scoped capability material")
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "api_prefix", "/" + self.api_prefix.strip("/"))

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "TestudoTransportConfig":
        """Build configuration from an explicit Testudo config mapping."""

        if not isinstance(config, Mapping):
            raise TransportConfigurationError("Testudo transport config must be an object")
        return cls(
            base_url=str(config.get("base_url", "")),
            capability_token=config.get("capability_token"),
            timeout_seconds=float(config.get("timeout_seconds", 30.0)),
            api_prefix=str(config.get("api_prefix", "/api/v1")),
            activation=bool(config.get("activation", False)),
            notebook_origin=config.get("notebook_origin"),
            notebook_relay_token=config.get("notebook_relay_token"),
        )


class HttpTestudoTransport:
    """Governed HTTP client; it can call only Testudo's control-plane API."""

    def __init__(self, config: TestudoTransportConfig, *, opener: Any = urllib.request.urlopen) -> None:
        if not config.activation:
            raise TransportConfigurationError("HTTP Testudo transport requires explicit activation=true")
        self.config = config
        self._opener = opener

    def send(self, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        """POST a typed command and normalize Testudo's JSON response."""

        task_id = payload.get("task_id")
        if not isinstance(task_id, str):
            raise TransportError("Testudo requests require task_id")
        if operation == "pipeline_call":
            required = ("notebook_session_id", "cell_id", "correlation", "payload")
            missing = [field for field in required if field not in payload]
            if missing:
                raise TransportError(
                    "GeoLibre pipeline_call is missing Notebook fields: " + ", ".join(missing)
                )
            if not isinstance(payload.get("correlation"), Mapping):
                raise TransportError("GeoLibre pipeline_call correlation must be an object")
            suffix = None
            url = f"{self.config.base_url}{self.config.api_prefix}/notebook/operations"
        else:
            suffix = {"create_mission": "plan", "dispatch_plan": "plan", "dispatch_command": "execute",
                      "ingest_receipt": "receipts"}.get(operation)
            url = f"{self.config.base_url}{self.config.api_prefix}/tasks/{task_id}/{suffix}" if suffix else ""
        if suffix is None:
            if operation != "pipeline_call":
                raise TransportError(f"unsupported Testudo operation: {operation}")
        wire_payload = _notebook_wire_payload(payload, idempotency_key) if operation == "pipeline_call" else dict(payload)
        body = json.dumps(wire_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Idempotency-Key": idempotency_key}
        if self.config.capability_token:
            headers["Authorization"] = f"Bearer {self.config.capability_token}"
        if operation == "pipeline_call" and self.config.notebook_origin:
            headers["Origin"] = self.config.notebook_origin
        if operation == "pipeline_call" and self.config.notebook_relay_token:
            headers["X-Testudo-Relay-Token"] = self.config.notebook_relay_token
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise TransportError("Testudo capability rejected or revoked") from exc
            raise TransportError(f"Testudo HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransportError(f"Testudo transport unavailable: {exc}") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("Testudo returned a non-JSON response") from exc
        if not isinstance(decoded, Mapping):
            raise TransportError("Testudo response must be an object")
        return decoded


class UnconfiguredTestudoTransport:
    """Fail-closed default; dry-run must be injected explicitly by tests."""

    def send(self, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        """Fail closed until the caller supplies explicit activation configuration."""
        del operation, payload, idempotency_key
        raise TransportConfigurationError(
            "Testudo transport is not configured; inject DryRunTransport only for tests "
            "or provide an activated TestudoTransportConfig"
        )


def build_testudo_transport(config: Mapping[str, Any] | TestudoTransportConfig) -> HttpTestudoTransport:
    """Construct the real transport from explicit activation configuration."""

    typed = config if isinstance(config, TestudoTransportConfig) else TestudoTransportConfig.from_mapping(config)
    return HttpTestudoTransport(typed)


class DryRunTransport:
    """Explicit in-memory transport for contract and fixture tests."""

    def __init__(self, *, failures_before_success: int = 0, responses: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self.failures_before_success = max(0, int(failures_before_success))
        self.responses = {key: dict(value) for key, value in (responses or {}).items()}
        self.requests: list[dict[str, Any]] = []

    def send(self, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        """Record a request and return a deterministic, non-network response."""

        self.requests.append(
            {
                "operation": operation,
                "payload": copy.deepcopy(dict(payload)),
                "idempotency_key": idempotency_key,
            }
        )
        if self.failures_before_success:
            self.failures_before_success -= 1
            raise TransportError("injected dry-run transport failure")
        response = copy.deepcopy(self.responses.get(operation, {}))
        response.setdefault("accepted", True)
        response.setdefault("dry_run", True)
        response.setdefault("operation", operation)
        response.setdefault("idempotency_key", idempotency_key)
        response.setdefault("contract_version", EXPECTED_PIPELINES_CONTRACT)
        response.setdefault("correlation_id", payload.get("correlation_id"))
        response.setdefault("identity", copy.deepcopy(dict(payload)))
        response.setdefault("request_digest", _request_digest(operation, payload, key=idempotency_key))
        response.setdefault(
            "response_identity",
            {
                "operation": operation,
                "idempotency_key": idempotency_key,
                "correlation_id": payload.get("correlation_id"),
            },
        )
        return response


# A descriptive alias keeps older test doubles readable without adding another
# transport implementation.
InMemoryTestudoTransport = DryRunTransport


@dataclass(frozen=True)
class _StoredRequest:
    digest: str
    result: GatewayResult
    terminal_completed_at: datetime
    retention_until: datetime


class InMemoryGatewayIdempotencyStore:
    """Small durable-store seam; callers can share it across adapter instances."""

    def __init__(self) -> None:
        self.records: dict[str, _StoredRequest] = {}
        self.fail_purge = False

    def get(self, key: str) -> _StoredRequest | None:
        """Return one immutable ledger row."""

        return self.records.get(key)

    def put(self, key: str, row: _StoredRequest) -> None:
        """Persist one terminal ledger row."""

        self.records[key] = row

    def purge_expired(self, policy: GatewayIdempotencyPolicy) -> int:
        """Delete eligible rows atomically and return the deleted-row count."""

        before = dict(self.records)
        try:
            now = policy.utc_now()
            expired = [key for key, row in self.records.items() if row.retention_until <= now]
            for key in expired:
                del self.records[key]
            if self.fail_purge:
                raise RuntimeError("injected purge failure")
            return len(expired)
        except Exception:
            self.records = before
            raise


class TestudoGatewayAdapter:
    """Validate and route messages through an explicit Testudo transport."""

    __test__ = False

    def __init__(
        self,
        root: Path | None = None,
        transport: TestudoTransport | Any | None = None,
        transport_config: Mapping[str, Any] | TestudoTransportConfig | None = None,
        *,
        expected_contract: str = EXPECTED_PIPELINES_CONTRACT,
        max_retries: int = 0,
        policy: GatewayIdempotencyPolicy | None = None,
        store: InMemoryGatewayIdempotencyStore | None = None,
        idempotency_store: InMemoryGatewayIdempotencyStore | None = None,
    ) -> None:
        self.root = (root or Path(__file__).resolve().parents[3]).resolve()
        if transport is not None and transport_config is not None:
            raise TransportConfigurationError("provide transport or transport_config, not both")
        self.transport = (
            transport
            if transport is not None
            else build_testudo_transport(transport_config)
            if transport_config is not None
            else UnconfiguredTestudoTransport()
        )
        self.expected_contract = str(expected_contract)
        self.max_retries = max(0, int(max_retries))
        if store is not None and idempotency_store is not None and store is not idempotency_store:
            raise ValueError("store and idempotency_store must refer to the same seam")
        self.policy = policy or GatewayIdempotencyPolicy()
        self.store = store or idempotency_store or InMemoryGatewayIdempotencyStore()
        self._requests = self.store.records
        self._identity_bindings: dict[str, dict[str, str]] = {}

    def purge_expired(self) -> int:
        """Purge terminal rows only after the caller's transaction succeeds."""

        return self.store.purge_expired(self.policy)

    def validate_contract(self) -> ContractValidation:
        """Validate the local modeller-pipelines contract version and registry pin."""

        version_path = self.root / CONTRACT_VERSION_FILE
        errors: list[str] = []
        warnings: list[str] = []
        observed: str | None = None
        if not version_path.exists():
            errors.append(f"modeller-pipelines contract version file not found: {version_path}")
        else:
            observed = version_path.read_text(encoding="utf-8-sig").strip()
            if observed != self.expected_contract:
                errors.append(
                    f"modeller-pipelines contract {observed!r} does not match expected {self.expected_contract!r}"
                )

        contract_sha: str | None = None
        registry_path = self.root / "backends.toml"
        if registry_path.exists():
            try:
                registry = load_toml(registry_path)
                config = registry.get("backend", {}).get("aimsun-psp", {})
                contract_sha = config.get("contract_sha")
                registry_version = config.get("expected_contract")
                if registry_version and str(registry_version) != self.expected_contract:
                    errors.append(
                        "backends.toml aimsun-psp expected_contract "
                        f"{registry_version!r} does not match {self.expected_contract!r}"
                    )
                if contract_sha and str(contract_sha) != PINNED_PIPELINES_CONTRACT_SHA:
                    errors.append("backends.toml contract_sha does not match the pinned v1.2 checkpoint")
            except (OSError, ValueError) as exc:
                errors.append(f"failed to read backends.toml contract pin: {exc}")
        else:
            warnings.append(f"backend registry not present at {registry_path}; checked vendor contract only")

        return ContractValidation(
            ok=not errors,
            expected_version=self.expected_contract,
            observed_version=observed,
            errors=errors,
            warnings=warnings,
            contract_sha=contract_sha,
        )

    def require_contract(self) -> ContractValidation:
        """Validate the pin and raise a clear error on mismatch."""

        check = self.validate_contract()
        if not check.ok:
            raise ContractMismatchError("; ".join(check.errors))
        return check

    def validate_activation_preparation(
        self,
        manifest: Mapping[str, Any] | None,
    ) -> ActivationPreparationValidation:
        """Validate a strictly offline activation-preparation manifest.

        This method deliberately has no activation, registry, credential, network,
        or transport side effects.  It validates the local pinned contract and the
        canonical manifest/evidence digests before any caller can proceed.
        """

        errors: list[str] = []
        candidate = dict(manifest) if isinstance(manifest, Mapping) else {}
        if not isinstance(manifest, Mapping):
            errors.append("activation-preparation manifest must be an object")
        unknown = sorted(set(candidate) - ACTIVATION_PREPARATION_FIELDS)
        if unknown:
            errors.append(f"activation-preparation manifest has unexpected properties: {unknown}")
        missing = sorted(ACTIVATION_PREPARATION_REQUIRED_FIELDS - set(candidate))
        if missing:
            errors.append(f"activation-preparation manifest is missing required properties: {missing}")

        backend_id = candidate.get("backend_id")
        if backend_id != ACTIVATION_PREPARATION_BACKEND_ID:
            errors.append(
                f"activation-preparation backend_id must be {ACTIVATION_PREPARATION_BACKEND_ID!r}"
            )
        contract_version = candidate.get("contract_version")
        if contract_version != EXPECTED_PIPELINES_CONTRACT:
            errors.append(
                f"activation-preparation contract_version {contract_version!r} "
                f"does not match expected {EXPECTED_PIPELINES_CONTRACT!r}"
            )
        if candidate.get("activation") is not False:
            errors.append("activation-preparation activation must be false")
        if candidate.get("credential_source") != ACTIVATION_PREPARATION_CREDENTIAL_SOURCE:
            errors.append(
                "activation-preparation credential_source must be "
                f"{ACTIVATION_PREPARATION_CREDENTIAL_SOURCE!r}"
            )
        if candidate.get("network_calls_allowed") is not False:
            errors.append("activation-preparation network_calls_allowed must be false")
        if candidate.get("transport_calls_allowed") is not False:
            errors.append("activation-preparation transport_calls_allowed must be false")

        for field_name in ("activation_owner", "abort_authority"):
            if not _is_concrete_activation_text(candidate.get(field_name)):
                errors.append(f"activation-preparation {field_name} must be concrete and non-placeholder")
        for field_name in ("canary_stop_criteria", "rollback_steps"):
            errors.extend(_validate_activation_text_list(candidate.get(field_name), field_name))

        zero_call_assertions = candidate.get("zero_call_assertions")
        if not isinstance(zero_call_assertions, Mapping):
            errors.append("activation-preparation zero_call_assertions must be an object")
            zero_call_counts: dict[str, int] = {}
        else:
            observed_zero_keys = set(zero_call_assertions)
            if observed_zero_keys != {"network_calls", "transport_calls"}:
                errors.append(
                    "activation-preparation zero_call_assertions must contain only "
                    "network_calls and transport_calls"
                )
            zero_call_counts = {}
            for call_type in ("network_calls", "transport_calls"):
                count = zero_call_assertions.get(call_type)
                if isinstance(count, bool) or not isinstance(count, int) or count != 0:
                    errors.append(
                        f"activation-preparation zero_call_assertions.{call_type} must be integer 0"
                    )
                else:
                    zero_call_counts[call_type] = count

        contract = self.validate_contract()
        if not contract.ok:
            errors.extend(f"pinned contract: {error}" for error in contract.errors)

        contract_digest = candidate.get("contract_digest")
        if not isinstance(contract_digest, str) or not IDEMPOTENCY_DIGEST_RE.fullmatch(contract_digest):
            errors.append("activation-preparation contract_digest must be sha256:<64 lowercase hex>")
        elif isinstance(backend_id, str) and isinstance(contract_version, str):
            expected_digest = activation_preparation_contract_digest(backend_id, contract_version)
            if contract_digest != expected_digest:
                errors.append("activation-preparation contract_digest is not canonically compatible")

        evidence_digest = candidate.get("evidence_digest")
        if not isinstance(evidence_digest, str) or not IDEMPOTENCY_DIGEST_RE.fullmatch(evidence_digest):
            errors.append("activation-preparation evidence_digest must be sha256:<64 lowercase hex>")
        elif not errors:
            expected_evidence_digest = activation_preparation_evidence_digest(candidate)
            if evidence_digest != expected_evidence_digest:
                errors.append("activation-preparation evidence_digest is not canonically compatible")
        elif isinstance(evidence_digest, str) and isinstance(candidate, dict):
            # Still report a mismatched canonical evidence digest when the other
            # failures are independent; never let malformed fields raise here.
            try:
                if evidence_digest != activation_preparation_evidence_digest(candidate):
                    errors.append("activation-preparation evidence_digest is not canonically compatible")
            except (CanonicalizationError, TypeError, ValueError):
                pass

        return ActivationPreparationValidation(
            ok=not errors,
            manifest=copy.deepcopy(candidate),
            errors=errors,
            zero_call_assertions=zero_call_counts,
        )

    def validate_activation_preparation_manifest(
        self,
        manifest: Mapping[str, Any] | None,
    ) -> ActivationPreparationValidation:
        """Compatibility alias for callers naming the manifest explicitly."""

        return self.validate_activation_preparation(manifest)

    def prepare_activation(self, manifest: Mapping[str, Any] | None) -> ActivationPreparationValidation:
        """Validate preparation only; no activation action is available here."""

        return self.validate_activation_preparation(manifest)

    def create_mission(
        self,
        mission: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> GatewayResult:
        """Create a mission request linked to its Testudo task identity."""

        payload, error = _merge_payload(mission, fields, "mission")
        if error:
            return self._failure("create_mission", error)
        payload["operation"] = "create_mission"
        return self._submit("create_mission", payload, idempotency_key, REQUIRED_IDENTITY_FIELDS)

    def dispatch_plan(
        self,
        plan: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> GatewayResult:
        """Dispatch an approved plan while retaining mission/task lineage."""

        payload, error = _merge_payload(plan, fields, "plan")
        if error:
            return self._failure("dispatch_plan", error)
        payload["operation"] = "dispatch_plan"
        if "plan" not in payload:
            payload["plan"] = {key: value for key, value in payload.items() if key not in IDENTITY_FIELDS}
        return self._submit(
            "dispatch_plan",
            payload,
            idempotency_key,
            REQUIRED_EXECUTION_IDENTITY_FIELDS,
            execution_identity=True,
        )

    def dispatch_command(
        self,
        command: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> GatewayResult:
        """Dispatch one v1.2 pipeline command through the injectable seam."""

        payload, error = _merge_payload(command, fields, "command")
        if error:
            return self._failure("dispatch_command", error)
        payload["operation"] = "dispatch_command"
        return self._submit(
            "dispatch_command",
            payload,
            idempotency_key,
            REQUIRED_EXECUTION_IDENTITY_FIELDS,
            command=True,
            execution_identity=True,
        )

    def pipeline_call(
        self,
        request: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> GatewayResult:
        """Submit one GeoLibre Notebook ``pipeline_call`` operation.

        The Notebook request fields are passed through unchanged to the existing
        transport.  The adapter adds only its established operation and task
        correlation fields; it does not define a second Notebook protocol.
        """

        payload, error = _merge_payload(request, fields, "pipeline_call")
        if error:
            return self._failure("pipeline_call", error)
        payload["operation"] = "pipeline_call"
        errors = _validate_notebook_operation(payload)
        if errors:
            return self._failure("pipeline_call", errors, payload.get("correlation_id"))
        return self._submit(
            "pipeline_call",
            payload,
            idempotency_key,
            REQUIRED_IDENTITY_FIELDS,
        )

    def ingest_receipt(
        self,
        receipt: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> GatewayResult:
        """Validate and ingest a provider receipt without changing mission state."""

        payload, error = _merge_payload(receipt, fields, "receipt")
        if error:
            return self._failure("ingest_receipt", error)
        payload["operation"] = "ingest_receipt"
        return self._submit(
            "ingest_receipt",
            payload,
            idempotency_key,
            REQUIRED_EXECUTION_IDENTITY_FIELDS,
            receipt=True,
            execution_identity=True,
        )

    def correlation_id(self, mission_id: str, task_id: str) -> str:
        """Return Testudo's stable correlation token for one task."""

        del mission_id  # Retained in the public signature for compatibility.
        return _derive_correlation(task_id)

    def _submit(
        # pylint: disable=too-many-branches
        self,
        operation: str,
        payload: dict[str, Any],
        idempotency_key: str | None,
        required_identity: tuple[str, ...],
        *,
        command: bool = False,
        receipt: bool = False,
        execution_identity: bool = False,
    ) -> GatewayResult:
        contract = self.validate_contract()
        if not contract.ok:
            return self._failure(operation, contract.errors)

        if command or receipt:
            payload.setdefault("contract_version", self.expected_contract)
        errors: list[str] = []
        if execution_identity:
            errors.extend(_project_workflow_identity(payload))
        errors.extend(_validate_identity(payload, required_identity))
        if command:
            errors.extend(self._validate_command(payload))
            errors.extend(_validate_execution_evidence(payload))
        if receipt:
            errors.extend(_validate_receipt(payload, self.expected_contract))
        if errors:
            return self._failure(operation, errors, payload.get("correlation_id"))

        correlation, correlation_error = self._resolve_correlation(payload)
        if correlation_error:
            return self._failure(operation, [correlation_error], correlation)
        payload["correlation_id"] = correlation
        identity_errors = self._validate_identity_binding(payload, correlation)
        if identity_errors:
            return self._failure(operation, identity_errors, correlation)
        try:
            if operation == "pipeline_call" and idempotency_key is None:
                candidate = payload.get("correlation")
                if isinstance(candidate, Mapping) and isinstance(candidate.get("idempotency_key"), str):
                    idempotency_key = candidate["idempotency_key"]
            digest = _request_digest(operation, payload, key=idempotency_key or None)
            terminal_completed_at = self.policy.utc_now()
        except (CanonicalizationError, ValueError) as exc:
            return self._failure(operation, [str(exc)], correlation)
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            return self._failure(operation, ["idempotency_key must be a safe identity token"], correlation)
        key = idempotency_key or digest.split(":", 1)[1]
        if not IDENTITY_TOKEN_RE.fullmatch(key):
            return self._failure(operation, ["idempotency_key must be a safe identity token"], correlation)
        stored = self.store.get(key)
        if stored:
            if stored.digest != digest:
                return self._failure(operation, [f"idempotency key {key!r} conflicts with a different payload"], correlation, key)
            prior = stored.result
            return GatewayResult(
                ok=prior.ok,
                operation=prior.operation,
                payload=copy.deepcopy(prior.payload),
                errors=list(prior.errors),
                warnings=list(prior.warnings),
                idempotency_key=key,
                correlation_id=prior.correlation_id,
                attempts=0,
                duplicate=True,
            )

        result = self._send_with_retry(operation, payload, key, correlation)
        if result.ok:
            self.store.put(
                key,
                _StoredRequest(
                    digest=digest,
                    result=result,
                    terminal_completed_at=terminal_completed_at,
                    retention_until=self.policy.retention_until(terminal_completed_at),
                ),
            )
            self._identity_bindings.setdefault(correlation, {}).update(_identity_projection(payload))
        return result

    def _send_with_retry(
        self,
        operation: str,
        payload: dict[str, Any],
        idempotency_key: str,
        correlation: str,
    ) -> GatewayResult:
        last_error = "transport did not return a response"
        for attempt in range(1, self.max_retries + 2):
            try:
                response = _send(self.transport, operation, payload, idempotency_key)
                if not isinstance(response, Mapping):
                    last_error = "transport response must be an object"
                    continue
                response_payload = copy.deepcopy(dict(response))
                response_errors = _validate_transport_response(
                    response_payload,
                    payload,
                    self.expected_contract,
                    correlation,
                    idempotency_key,
                )
                if response_errors:
                    last_error = "; ".join(response_errors)
                    continue
                return GatewayResult(
                    ok=True,
                    operation=operation,
                    payload=response_payload,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation,
                    attempts=attempt,
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_error = str(exc) or exc.__class__.__name__
                if "revoked" in last_error.lower() or "capability rejected" in last_error.lower():
                    break
        return self._failure(operation, [f"transport failed after {self.max_retries + 1} attempt(s): {last_error}"], correlation, idempotency_key, self.max_retries + 1)

    def _resolve_correlation(self, payload: Mapping[str, Any]) -> tuple[str, str | None]:
        task_id = payload.get("task_id")
        if not isinstance(task_id, str):
            return "", "task_id must be present before deriving correlation_id"
        correlation = _derive_correlation(task_id)
        supplied = payload.get("correlation_id")
        if supplied is not None and supplied != correlation:
            return str(supplied), (
                f"correlation_id {supplied!r} does not match Testudo canonical "
                f"value {correlation!r}"
            )
        return correlation, None

    def _validate_identity_binding(self, payload: Mapping[str, Any], correlation: str) -> list[str]:
        """Reject a request that changes an established task identity."""

        prior = self._identity_bindings.get(correlation)
        if not prior:
            return []
        errors: list[str] = []
        for field_name, value in _identity_projection(payload).items():
            if field_name in prior and prior[field_name] != value:
                errors.append(
                    f"{field_name} {value!r} does not match established "
                    f"identity {prior[field_name]!r}"
                )
        return errors

    def _validate_command(self, payload: Mapping[str, Any]) -> list[str]:
        errors: list[str] = []
        if payload.get("contract_version", self.expected_contract) != self.expected_contract:
            errors.append(
                f"command contract_version {payload.get('contract_version')!r} does not match expected {self.expected_contract!r}"
            )
        pipeline_id = payload.get("pipeline_id")
        if not isinstance(pipeline_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", pipeline_id):
            errors.append("command pipeline_id must be a lowercase pipeline identity")
        pipeline_version = payload.get("pipeline_version")
        if pipeline_version is not None and (not isinstance(pipeline_version, str) or not PIPELINE_VERSION_RE.fullmatch(pipeline_version)):
            errors.append("command pipeline_version must be semantic version text")
        config = payload.get("config")
        if config is not None:
            if not isinstance(config, Mapping):
                errors.append("command config must be an object")
            else:
                validation = validate_with_contract_schema(self.root, "run-config.schema.json", dict(config))
                errors.extend(validation.errors)
        command_body = payload.get("command")
        if command_body is not None and not isinstance(command_body, (Mapping, list, str)):
            errors.append("command body must be an object, list, or string")
        return errors

    def _failure(
        self,
        operation: str,
        errors: str | list[str],
        correlation: str | None = None,
        idempotency_key: str | None = None,
        attempts: int = 0,
    ) -> GatewayResult:
        return GatewayResult(
            ok=False,
            operation=operation,
            errors=[errors] if isinstance(errors, str) else list(errors),
            idempotency_key=idempotency_key,
            correlation_id=correlation,
            attempts=attempts,
        )


def activation_preparation_contract_digest(
    backend_id: str = ACTIVATION_PREPARATION_BACKEND_ID,
    contract_version: str = EXPECTED_PIPELINES_CONTRACT,
    contract_sha: str = PINNED_PIPELINES_CONTRACT_SHA,
) -> str:
    """Return the typed digest binding a backend to its pinned contract."""

    return canonical_digest(
        {
            "backend_id": backend_id,
            "contract_sha": contract_sha,
            "contract_version": contract_version,
        }
    )


def activation_preparation_evidence_digest(manifest: Mapping[str, Any]) -> str:
    """Return the typed digest for manifest evidence, excluding its own digest."""

    projection = {
        field_name: copy.deepcopy(manifest[field_name])
        for field_name in ACTIVATION_PREPARATION_EVIDENCE_FIELDS
        if field_name in manifest
    }
    return canonical_digest(projection)


def _is_concrete_activation_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(text) and len(text) <= 256 and not any(char in text for char in "\r\n\t") and not ACTIVATION_PREPARATION_PLACEHOLDER_RE.search(text)


def _validate_activation_text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"activation-preparation {field_name} must be a non-empty array"]
    errors: list[str] = []
    for index, item in enumerate(value):
        if not _is_concrete_activation_text(item):
            errors.append(
                f"activation-preparation {field_name}[{index}] must be concrete and non-placeholder"
            )
    return errors


def _merge_payload(
    payload: Mapping[str, Any] | None,
    fields: Mapping[str, Any],
    label: str,
) -> tuple[dict[str, Any], str | None]:
    if payload is not None and not isinstance(payload, Mapping):
        return {}, f"{label} payload must be an object"
    result = dict(payload or {})
    for key, value in fields.items():
        if key in result and result[key] != value:
            return {}, f"{label} field {key!r} was supplied twice with different values"
        result[key] = value
    return result, None


def _validate_identity(payload: Mapping[str, Any], required: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    for field_name in required:
        value = payload.get(field_name)
        if not isinstance(value, str) or not IDENTITY_TOKEN_RE.fullmatch(value):
            errors.append(f"{field_name} must be a safe identity token")
    for field_name in IDENTITY_FIELDS:
        if field_name in payload and payload[field_name] is not None:
            value = payload[field_name]
            if not isinstance(value, str) or not IDENTITY_TOKEN_RE.fullmatch(value):
                errors.append(f"{field_name} must be a safe identity token")
    return errors


def _validate_notebook_operation(payload: Mapping[str, Any]) -> list[str]:
    """Validate the fields owned by Testudo's NotebookOperationRequest."""

    errors: list[str] = []
    for field_name in NOTEBOOK_OPERATION_FIELDS:
        if field_name not in payload:
            errors.append(f"pipeline_call {field_name} is required")
    for field_name in ("notebook_session_id", "cell_id"):
        value = payload.get(field_name)
        if field_name in payload and (
            not isinstance(value, str) or not IDENTITY_TOKEN_RE.fullmatch(value)
        ):
            errors.append(f"pipeline_call {field_name} must be a safe identity token")
    correlation = payload.get("correlation")
    if "correlation" in payload and not isinstance(correlation, Mapping):
        errors.append("pipeline_call correlation must be an object")
    notebook_payload = payload.get("payload")
    if "payload" in payload and not isinstance(notebook_payload, Mapping):
        errors.append("pipeline_call payload must be an object")
    return errors


def _project_workflow_identity(payload: dict[str, Any]) -> list[str]:
    """Project the adapter execution identity to Testudo's workflow_id."""

    pipeline_execution_id = payload.get("pipeline_execution_id")
    workflow_id = payload.get("workflow_id")
    if not isinstance(pipeline_execution_id, str) or not IDENTITY_TOKEN_RE.fullmatch(pipeline_execution_id):
        return []
    if workflow_id is None:
        payload["workflow_id"] = pipeline_execution_id
    elif workflow_id != pipeline_execution_id:
        return [
            "workflow_id must match pipeline_execution_id; refusing to alias or overwrite a supplied value"
        ]
    return []


def _validate_receipt(payload: Mapping[str, Any], expected_contract: str) -> list[str]:
    errors: list[str] = []
    receipt_id = payload.get("receipt_id")
    if not isinstance(receipt_id, str) or not IDENTITY_TOKEN_RE.fullmatch(receipt_id):
        errors.append("receipt_id must be a safe identity token")
    status = payload.get("status")
    if status not in RECEIPT_STATUSES:
        errors.append(f"receipt status must be one of {sorted(RECEIPT_STATUSES)}")
    if "contract_version" in payload and payload["contract_version"] != expected_contract:
        errors.append(f"receipt contract_version must be the pinned modeller-pipelines version {expected_contract}")
    return errors


def _validate_execution_evidence(payload: Mapping[str, Any]) -> list[str]:
    """Require immutable plan/baseline evidence for execution only."""

    errors: list[str] = []
    errors.extend(
        _validate_evidence_pair(
            payload,
            "approved-plan",
            APPROVED_PLAN_REF_FIELDS,
            APPROVED_PLAN_DIGEST_FIELDS,
            ("approved_plan_evidence", "approved_plan"),
        )
    )
    errors.extend(
        _validate_evidence_pair(
            payload,
            "baseline",
            BASELINE_REF_FIELDS,
            BASELINE_DIGEST_FIELDS,
            ("baseline_evidence", "baseline"),
        )
    )
    return errors


def _validate_evidence_pair(
    payload: Mapping[str, Any],
    label: str,
    reference_fields: tuple[str, ...],
    digest_fields: tuple[str, ...],
    evidence_fields: tuple[str, ...],
) -> list[str]:
    errors: list[str] = []
    reference = _first_present(payload, reference_fields)
    digest = _first_present(payload, digest_fields)
    if not isinstance(reference, str) or not reference:
        errors.append(f"{label} evidence reference is required for execution")
    if not isinstance(digest, str) or not IDEMPOTENCY_DIGEST_RE.fullmatch(digest):
        errors.append(f"{label} evidence digest must be sha256:<hex>")
    evidence = _first_present(payload, evidence_fields)
    if not isinstance(evidence, Mapping):
        return errors
    evidence_task = evidence.get("task_id", evidence.get("task"))
    if evidence_task is not None and evidence_task != payload.get("task_id"):
        errors.append(f"{label} evidence belongs to a different task")
    if evidence.get("stale") is True or evidence.get("status") in {"stale", "superseded", "expired"}:
        errors.append(f"{label} evidence is stale")
    observed_digest = evidence.get("digest", evidence.get("content_digest"))
    if observed_digest is not None and observed_digest != digest:
        errors.append(f"{label} evidence digest changed")
    observed_reference = evidence.get("ref", evidence.get("reference"))
    if observed_reference is not None and observed_reference != reference:
        errors.append(f"{label} evidence reference changed")
    return errors


def _first_present(payload: Mapping[str, Any], fields: tuple[str, ...]) -> Any:
    for field_name in fields:
        if field_name in payload:
            return payload[field_name]
    return None


def _identity_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key] for key in IDENTITY_FIELDS if key in payload and payload[key] is not None
    }


def _validate_transport_response(
    # pylint: disable=too-many-branches
    response: Mapping[str, Any],
    request: Mapping[str, Any],
    expected_contract: str,
    correlation: str,
    idempotency_key: str,
) -> list[str]:
    """Validate the minimum accepted-response contract before caching it."""

    errors: list[str] = []
    if response.get("accepted") is not True:
        errors.append("transport response must explicitly report accepted=true")
    if response.get("contract_version") != expected_contract:
        errors.append(
            f"transport response contract_version {response.get('contract_version')!r} "
            f"does not match expected {expected_contract!r}"
        )
    if response.get("correlation_id") != correlation:
        errors.append(
            f"transport response correlation_id {response.get('correlation_id')!r} "
            f"does not match expected {correlation!r}"
        )
    if response.get("operation") != request.get("operation"):
        errors.append(
            f"transport response operation {response.get('operation')!r} "
            f"does not match expected {request.get('operation')!r}"
        )
    if response.get("idempotency_key") != idempotency_key:
        errors.append(
            f"transport response idempotency_key {response.get('idempotency_key')!r} "
            f"does not match expected {idempotency_key!r}"
        )
    expected_digest = _request_digest(str(request.get("operation")), request, key=idempotency_key)
    if response.get("request_digest") != expected_digest:
        errors.append(
            f"transport response request_digest {response.get('request_digest')!r} "
            f"does not match expected {expected_digest!r}"
        )

    response_identity = response.get("identity")
    if not isinstance(response_identity, Mapping):
        errors.append("transport response identity must be an object")
    else:
        for field_name, value in _identity_projection(request).items():
            if field_name == "correlation_id" and field_name not in response_identity:
                continue
            observed = response_identity.get(field_name)
            if observed != value:
                errors.append(
                    f"transport response identity {field_name} {observed!r} "
                    f"does not match request {value!r}"
                )
    response_identity = response.get("response_identity")
    if response_identity is not None:
        if not isinstance(response_identity, Mapping):
            errors.append("transport response response_identity must be an object")
        else:
            expected_response_identity = {
                "operation": request.get("operation"),
                "idempotency_key": idempotency_key,
                "correlation_id": correlation,
            }
            for field_name, value in expected_response_identity.items():
                if response_identity.get(field_name) != value:
                    errors.append(
                        f"transport response response_identity {field_name} "
                        f"{response_identity.get(field_name)!r} does not match {value!r}"
                    )
    return errors


def _derive_correlation(task_id: str) -> str:
    return f"task-correlation-{task_id}"


def _canonical_typed_value(value: Any, path: str = "$") -> dict[str, Any]:
    """Encode one value using Testudo's explicit typed canonical JSON contract."""

    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError(f"unsupported non-finite float at {path}")
        return {"type": "float", "value": format(value, ".17g")}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    if isinstance(value, list):
        return {"type": "array", "value": [_canonical_typed_value(item, f"{path}[{index}]") for index, item in enumerate(value)]}
    if isinstance(value, Mapping):
        typed: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"unsupported non-string object key at {path}")
            typed[key] = _canonical_typed_value(item, f"{path}.{key}")
        return {"type": "object", "value": typed}
    raise CanonicalizationError(f"unsupported identity-bearing value at {path}: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return the exact canonical JSON envelope shared with Testudo."""

    envelope = {"version": CANONICAL_JSON_VERSION, "value": _canonical_typed_value(value)}
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    """Return the Testudo-formatted canonical SHA-256 digest."""

    return f"sha256:{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def _digest(operation: str, payload: Mapping[str, Any]) -> str:
    return canonical_digest({"operation": operation, "payload": payload})


def _notebook_wire_payload(payload: Mapping[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
    """Project adapter metadata into GeoLibre/Testudo's typed Notebook body."""
    correlation = dict(payload.get("correlation") or {})
    identity_map = {
        "mission_id": "mission_id", "task_id": "task_id", "attempt_id": "attempt_id", "workflow_run_id": "workflow_run_id",
        "pipeline_execution_id": "pipeline_execution_id", "pipeline_version_id": "pipeline_version_id",
        "project_id": "project_id", "active_context_revision_id": "active_context_revision_id",
        "capability_grant_id": "capability_grant_id", "principal": "principal",
        "required_scopes": "required_scopes", "runtime_endpoint": "runtime_endpoint",
        "runtime_version": "runtime_version",
    }
    for source, target in identity_map.items():
        if target not in correlation and source in payload:
            correlation[target] = payload[source]
    correlation.setdefault("schema_version", "1.0")
    correlation.setdefault("workflow_run_id", None)
    correlation.setdefault("required_scopes", {})
    correlation.setdefault("runtime_endpoint", None)
    correlation.setdefault("runtime_version", None)
    if idempotency_key and "idempotency_key" not in correlation:
        correlation["idempotency_key"] = idempotency_key
    if "sequence" not in correlation:
        correlation["sequence"] = 0
    return {
        "schema_version": "1.0",
        "operation": "pipeline_call",
        "correlation": correlation,
        "notebook_session_id": payload.get("notebook_session_id"),
        "cell_id": payload.get("cell_id"),
        "approval_reference": payload.get("approval_reference"),
        "payload": dict(payload.get("payload") or {}),
    }


def _request_digest(operation: str, payload: Mapping[str, Any], key: str | None = None) -> str:
    if operation == "pipeline_call":
        return canonical_digest(_notebook_wire_payload(payload, key))
    return _digest(operation, payload)


def _send(transport: TestudoTransport | Any, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
    if hasattr(transport, "send"):
        return transport.send(operation, payload, idempotency_key)
    if callable(transport):
        return transport(operation, payload, idempotency_key)
    raise TransportError("injected transport must provide send(operation, payload, idempotency_key)")
