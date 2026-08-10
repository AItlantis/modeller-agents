"""Dry-run Testudo Gateway seam for mission and pipeline orchestration.

The adapter owns the boundary shape only.  It does not know a Testudo URL,
credentials, registry client, or database connection.  The default transport
records requests in memory; a deterministic test double can be injected when
an integration test needs to control responses or transient failures.
"""

# The adapter intentionally keeps one compact boundary module. These limits
# describe the transport/result seam rather than production domain logic.
# pylint: disable=import-error,line-too-long,too-few-public-methods,too-many-arguments,too-many-instance-attributes,too-many-locals,too-many-return-statements

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from modeller.contracts import IDENTITY_TOKEN_RE, validate_with_contract_schema
from modeller.toml_compat import load_toml


EXPECTED_PIPELINES_CONTRACT = "1.2"
PINNED_PIPELINES_CONTRACT_SHA = "dbd00cb1299f3f68add0e5971e6ec808f010059d"
CONTRACT_VERSION_FILE = Path("vendor/modeller-pipelines/contracts/VERSION")
IDENTITY_FIELDS = ("task_id", "attempt_id", "mission_id", "correlation_id", "workflow_run_id")
REQUIRED_IDENTITY_FIELDS = ("mission_id", "task_id")
REQUIRED_EXECUTION_IDENTITY_FIELDS = ("mission_id", "task_id", "attempt_id")
PIPELINE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
RECEIPT_STATUSES = {"completed", "success", "partial", "failed", "cancelled", "recovery_required"}


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
    """Minimal injectable transport; no network implementation is provided."""

    def send(self, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        """Send one already-validated request and return a response mapping."""


class DryRunTransport:
    """In-memory transport used by default and by contract/e2e tests."""

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
        return response


# A descriptive alias keeps older test doubles readable without adding another
# transport implementation.
InMemoryTestudoTransport = DryRunTransport


@dataclass(frozen=True)
class _StoredRequest:
    digest: str
    result: GatewayResult


class TestudoGatewayAdapter:
    """Validate and route mission/command/receipt messages through a dry seam."""

    __test__ = False

    def __init__(
        self,
        root: Path | None = None,
        transport: TestudoTransport | Any | None = None,
        *,
        expected_contract: str = EXPECTED_PIPELINES_CONTRACT,
        max_retries: int = 0,
    ) -> None:
        self.root = (root or Path(__file__).resolve().parents[3]).resolve()
        self.transport = transport or DryRunTransport()
        self.expected_contract = str(expected_contract)
        self.max_retries = max(0, int(max_retries))
        self._requests: dict[str, _StoredRequest] = {}
        self._identity_bindings: dict[str, dict[str, str]] = {}

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
        return self._submit("dispatch_plan", payload, idempotency_key, REQUIRED_IDENTITY_FIELDS)

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
        )

    def correlation_id(self, mission_id: str, task_id: str) -> str:
        """Return Testudo's stable correlation token for one task."""

        del mission_id  # Retained in the public signature for compatibility.
        return _derive_correlation(task_id)

    def _submit(
        self,
        operation: str,
        payload: dict[str, Any],
        idempotency_key: str | None,
        required_identity: tuple[str, ...],
        *,
        command: bool = False,
        receipt: bool = False,
    ) -> GatewayResult:
        contract = self.validate_contract()
        if not contract.ok:
            return self._failure(operation, contract.errors)

        if command or receipt:
            payload.setdefault("contract_version", self.expected_contract)
        errors = _validate_identity(payload, required_identity)
        if command:
            errors.extend(self._validate_command(payload))
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
        key = str(idempotency_key or _digest(operation, payload))
        if not IDENTITY_TOKEN_RE.fullmatch(key):
            return self._failure(operation, ["idempotency_key must be a safe identity token"], correlation)
        digest = _digest(operation, payload)
        stored = self._requests.get(key)
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
            self._requests[key] = _StoredRequest(digest=digest, result=result)
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


def _identity_projection(payload: Mapping[str, Any]) -> dict[str, str]:
    return {key: str(payload[key]) for key in IDENTITY_FIELDS if key in payload and payload[key] is not None}


def _validate_transport_response(
    response: Mapping[str, Any],
    request: Mapping[str, Any],
    expected_contract: str,
    correlation: str,
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
    return errors


def _derive_correlation(task_id: str) -> str:
    return f"task-correlation-{task_id}"


def _digest(operation: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps({"operation": operation, "payload": payload}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _send(transport: TestudoTransport | Any, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
    if hasattr(transport, "send"):
        return transport.send(operation, payload, idempotency_key)
    if callable(transport):
        return transport(operation, payload, idempotency_key)
    raise TransportError("injected transport must provide send(operation, payload, idempotency_key)")
