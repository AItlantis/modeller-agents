"""Result builder — backend-LOCAL shared helper.

Builds step-result and run-result dicts that validate against the
modeller-pipelines contract schemas.

IMPORTANT: This file lives inside your backend repo.
Do NOT import it from another repo. If you copy it, you own it.
"""
from __future__ import annotations

from typing import Any, Optional


def build_step_result(
    step_id: int,
    step_name: str,
    status: str,
    message: str,
    artifacts: Optional[list] = None,
    metrics: Optional[dict] = None,
    duration_s: float = 0.0,
    cached: bool = False,
    error: Optional[dict] = None,
) -> dict:
    """Build a step-result dict conforming to step-result.schema.json."""
    assert status in ("success", "failed", "skipped"), f"Invalid status: {status}"
    return {
        "status": status,
        "step_id": step_id,
        "step_name": step_name,
        "message": message,
        "duration_s": round(duration_s, 3),
        "cached": cached,
        "artifacts": artifacts or [],
        "metrics": metrics or {},
        "error": error,
    }


def build_run_result(
    contract_version: str,
    backend_id: str,
    pipeline_id: str,
    pipeline_version: str,
    run_id: str,
    status: str,
    started_at: str,
    completed_at: str,
    config_path: str,
    steps: list,
    artifacts: Optional[list] = None,
    metrics: Optional[dict] = None,
    logs: Optional[list] = None,
    error: Optional[dict] = None,
) -> dict:
    """Build a run-level result dict conforming to result.schema.json."""
    assert status in ("success", "partial", "failed"), f"Invalid status: {status}"
    return {
        "contract_version": contract_version,
        "backend_id": backend_id,
        "pipeline_id": pipeline_id,
        "pipeline_version": pipeline_version,
        "run_id": run_id,
        "status": status,
        "timestamps": {
            "started_at": started_at,
            "completed_at": completed_at,
        },
        "config_path": str(config_path),
        "steps": steps,
        "artifacts": artifacts or [],
        "metrics": metrics or {},
        "logs": logs or [],
        "error": error,
    }


def derive_run_status(step_results: list) -> str:
    """Derive run-level status from step results.

    success  — all steps succeeded (or were skipped as optional).
    partial  — all required steps succeeded; >= 1 optional step failed/skipped.
    failed   — >= 1 required step failed.

    NOTE: This helper does not know which steps are required — the runner
    must pass only the step results it cares about, or extend this function
    with a required_step_ids argument.
    """
    statuses = {r["status"] for r in step_results}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "partial"
    return "success"
