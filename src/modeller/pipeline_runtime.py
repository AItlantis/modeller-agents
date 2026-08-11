"""Execute an accepted Testudo pipeline dispatch through the backend seam.

This module is deliberately provider-agnostic.  Testudo decides whether a
dispatch is accepted; modeller-agents only consumes that accepted envelope,
invokes the declared ``aimsun-psp`` backend, and emits portable evidence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import RuntimeEvent, RuntimeReceipt, validate_runtime_event, validate_runtime_receipt
from .run import RunResult, run_backend_pipeline


class PipelineRuntimeError(ValueError):
    """Raised when an accepted dispatch or its backend result is invalid."""


@dataclass(frozen=True)
class PipelineRuntimeExecution:
    """Portable result of one governed backend execution."""

    run_result: RunResult
    result: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    receipt: dict[str, Any]
    testudo_events: tuple[dict[str, Any], ...] = ()
    testudo_receipt: dict[str, Any] | None = None


def execute_accepted_pipeline_dispatch(
    response: Mapping[str, Any],
    *,
    root: Path,
    backend_root: Path,
    config: Path,
    run_dir: Path,
    timeout_s: int = 3600,
) -> PipelineRuntimeExecution:
    """Run the declared aimsun-psp pipeline from an accepted Testudo response.

    ``backend_root``, ``config`` and ``run_dir`` are explicit on purpose: no
    local backend configuration, credentials, network client, or provider
    discovery is performed here.
    """

    dispatch = _accepted_dispatch(response)
    identity = _dispatch_identity(dispatch)
    backend_id = _required_string(dispatch, "backend_id")
    if backend_id != "aimsun-psp":
        raise PipelineRuntimeError(f"accepted dispatch backend_id must be 'aimsun-psp', got {backend_id!r}")
    pipeline_id = _required_string(dispatch, "pipeline_id")

    run_result = run_backend_pipeline(
        root=Path(root),
        backend_id=backend_id,
        pipeline_id=pipeline_id,
        config=Path(config),
        run_dir=Path(run_dir),
        backend_root=Path(backend_root),
        timeout_s=timeout_s,
    )
    if run_result.result_json is None or run_result.validation is None or not run_result.validation.ok:
        errors = list(run_result.errors)
        if run_result.validation is not None:
            errors.extend(run_result.validation.errors)
        raise PipelineRuntimeError("backend result.json failed validation: " + "; ".join(errors))

    result_path = Path(run_result.result_json).resolve()
    execution_root = Path(run_dir).resolve()
    if not _is_relative_to(result_path, execution_root):
        raise PipelineRuntimeError("backend result.json must be inside the explicit run_dir")
    result = _read_result(result_path)
    if result.get("backend_id") != backend_id or result.get("pipeline_id") != pipeline_id:
        raise PipelineRuntimeError("validated result identity does not match the accepted dispatch")
    declared_version = dispatch.get("pipeline_version")
    if declared_version is not None and result.get("pipeline_version") != declared_version:
        raise PipelineRuntimeError("result pipeline_version does not match the accepted dispatch")

    artifact_refs = _artifact_refs(result, execution_root)
    result_ref = _relative_ref(result_path, execution_root)
    evidence_refs = _unique([result_ref, *artifact_refs])
    timestamps = result.get("timestamps")
    if not isinstance(timestamps, Mapping):
        raise PipelineRuntimeError("validated result is missing timestamps")
    started_at = _required_string(timestamps, "started_at")
    completed_at = _required_string(timestamps, "completed_at")
    terminal_status = _receipt_status(str(result["status"]))
    pipeline_execution_id = identity["pipeline_execution_id"]
    correlation_id = str(dispatch.get("correlation_id") or pipeline_execution_id)
    attempt_id = dispatch.get("attempt_id")

    events = (
        RuntimeEvent(
            runtime_event_id=f"runtime-event-{pipeline_execution_id}-started",
            event_type="pipeline.execution_started",
            task_id=identity["task_id"],
            mission_id=identity["mission_id"],
            pipeline_execution_id=pipeline_execution_id,
            dispatch_attempt_id=attempt_id,
            correlation_id=correlation_id,
            sequence=1,
            occurred_at=started_at,
            payload={
                "backend_id": backend_id,
                "pipeline_id": pipeline_id,
                "pipeline_version": result.get("pipeline_version"),
                "run_id": result.get("run_id"),
                "status": "running",
            },
        ).to_dict(),
        RuntimeEvent(
            runtime_event_id=f"runtime-event-{pipeline_execution_id}-terminal",
            event_type="pipeline.execution_terminal",
            task_id=identity["task_id"],
            mission_id=identity["mission_id"],
            pipeline_execution_id=pipeline_execution_id,
            dispatch_attempt_id=attempt_id,
            correlation_id=correlation_id,
            sequence=2,
            occurred_at=completed_at,
            payload={
                "backend_id": backend_id,
                "pipeline_id": pipeline_id,
                "pipeline_version": result.get("pipeline_version"),
                "run_id": result.get("run_id"),
                "status": result["status"],
                "result_ref": result_ref,
                "artifact_refs": artifact_refs,
            },
            evidence_refs=evidence_refs,
        ).to_dict(),
    )
    receipt = RuntimeReceipt(
        receipt_id=f"runtime-receipt-{pipeline_execution_id}",
        task_id=identity["task_id"],
        mission_id=identity["mission_id"],
        pipeline_execution_id=pipeline_execution_id,
        status=terminal_status,
        created_at=completed_at,
        stage_status=list(result.get("steps", [])),
        outputs=[dict(artifact) for artifact in result.get("artifacts", [])],
        evidence=evidence_refs,
        error=result.get("error"),
    ).to_dict()

    _validate_emissions(Path(root), events, receipt)
    if dispatch.get("runtime_correlation") is not None:
        testudo_events, testudo_receipt = _testudo_emissions(
            dispatch=dispatch,
            events=events,
            receipt=receipt,
            artifact_refs=artifact_refs,
        )
    else:
        testudo_events, testudo_receipt = (), None
    return PipelineRuntimeExecution(
        run_result=run_result,
        result=result,
        events=events,
        receipt=receipt,
        testudo_events=testudo_events,
        testudo_receipt=testudo_receipt,
    )


def _testudo_emissions(
    *,
    dispatch: Mapping[str, Any],
    events: tuple[dict[str, Any], ...],
    receipt: Mapping[str, Any],
    artifact_refs: list[str],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    """Translate the backend-owned evidence contract to Testudo's envelope.

    The modeller-agents contract remains stable for local runtime consumers;
    this explicit projection is the only bridge to Testudo's GeoLibre Notebook
    runtime ingress.  No backend command or credential is added to the envelope.
    """
    correlation = dispatch.get("runtime_correlation")
    if not isinstance(correlation, Mapping):
        raise PipelineRuntimeError("accepted dispatch is missing runtime_correlation")
    required = ("mission_id", "task_id", "attempt_id", "pipeline_execution_id", "principal")
    missing = [key for key in required if not correlation.get(key)]
    if missing:
        raise PipelineRuntimeError("runtime_correlation is missing: " + ", ".join(missing))
    testudo_events = tuple(
        {
            "schema_version": "1.0",
            "event_id": event["runtime_event_id"],
            "event_type": event["event_type"],
            "correlation": dict(correlation),
            "sequence": event["sequence"],
            "payload": {
                **dict(event.get("payload", {})),
                "evidence_refs": list(event.get("evidence_refs", [])),
            },
        }
        for event in events
    )
    refs = [{"logical_path": ref, "source": "aimsun-psp"} for ref in artifact_refs]
    terminal_sequence = max((event["sequence"] for event in testudo_events), default=0) + 1
    testudo_receipt = {
        "schema_version": "1.0",
        "receipt_id": receipt["receipt_id"],
        "status": receipt["status"],
        "correlation": dict(correlation),
        "event_id": testudo_events[-1]["event_id"] if testudo_events else None,
        "sequence": terminal_sequence,
        "artifact_refs": refs,
        "error": receipt.get("error"),
    }
    return testudo_events, testudo_receipt


def _accepted_dispatch(response: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(response, Mapping):
        raise PipelineRuntimeError("Testudo dispatch response must be an object")
    if response.get("accepted") is not True and response.get("status") != "accepted":
        raise PipelineRuntimeError("Testudo pipeline dispatch was not accepted")
    dispatch = response.get("dispatch", response)
    if not isinstance(dispatch, Mapping):
        raise PipelineRuntimeError("accepted Testudo dispatch must contain an object dispatch")
    return dispatch


def _dispatch_identity(dispatch: Mapping[str, Any]) -> dict[str, str]:
    return {key: _required_string(dispatch, key) for key in ("mission_id", "task_id", "pipeline_execution_id")}


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PipelineRuntimeError(f"accepted dispatch is missing {key}")
    return value


def _read_result(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineRuntimeError(f"cannot read validated result.json: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineRuntimeError("result.json must contain an object")
    return value


def _artifact_refs(result: Mapping[str, Any], run_dir: Path) -> list[str]:
    refs: list[str] = []
    for artifact in result.get("artifacts", []):
        if not isinstance(artifact, Mapping) or "path" not in artifact:
            raise PipelineRuntimeError("result artifact must contain a path")
        refs.append(_relative_ref(Path(str(artifact["path"])), run_dir))
    for step in result.get("steps", []):
        for artifact in step.get("artifacts", []) if isinstance(step, Mapping) else []:
            if not isinstance(artifact, Mapping) or "path" not in artifact:
                raise PipelineRuntimeError("step artifact must contain a path")
            refs.append(_relative_ref(Path(str(artifact["path"])), run_dir))
    return _unique(refs)


def _relative_ref(value: Path, run_dir: Path) -> str:
    if value.is_absolute():
        candidate = value.resolve()
        if not _is_relative_to(candidate, run_dir):
            raise PipelineRuntimeError(f"artifact path escapes run_dir: {value}")
        value = candidate.relative_to(run_dir)
    ref = PurePosixPath(value.as_posix())
    if not ref.parts or ".." in ref.parts or ref.is_absolute():
        raise PipelineRuntimeError(f"artifact path must be relative to run_dir: {value}")
    return ref.as_posix()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _receipt_status(status: str) -> str:
    return {"success": "completed", "partial": "partial", "failed": "failed"}[status]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _validate_emissions(root: Path, events: tuple[dict[str, Any], ...], receipt: dict[str, Any]) -> None:
    for event in events:
        validation = validate_runtime_event(root, event)
        if not validation.ok:
            raise PipelineRuntimeError("runtime event contract failed: " + "; ".join(validation.errors))
    validation = validate_runtime_receipt(root, receipt)
    if not validation.ok:
        raise PipelineRuntimeError("runtime receipt contract failed: " + "; ".join(validation.errors))
