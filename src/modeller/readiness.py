from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .doctor import DoctorResult, run_doctor
from .sync import plan_sync


@dataclass
class ReadinessAction:
    code: str
    path: str
    summary: str
    commands: list[str] = field(default_factory=list)
    verification: str = "python -m modeller.cli doctor --root <root> --strict"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "path": self.path,
            "summary": self.summary,
            "commands": self.commands,
            "verification": self.verification,
        }


@dataclass
class ReadinessReport:
    root: Path
    doctor: DoctorResult
    actions: list[ReadinessAction]

    @property
    def ok(self) -> bool:
        return self.doctor.ok

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "root": str(self.root),
            "blocker_count": len(self.doctor.readiness_blockers),
            "readiness_blockers": self.doctor.readiness_blockers,
            "actions": [action.to_dict() for action in self.actions],
        }

    def format(self) -> str:
        lines = [f"modeller readiness: {'OK' if self.ok else 'BLOCKED'}", f"root: {self.root}"]
        if not self.actions:
            lines.append("actions: none")
            return "\n".join(lines)
        lines.append("actions:")
        for action in self.actions:
            lines.append(f"  - {action.code} {action.path}")
            lines.append(f"    summary: {action.summary}")
            for command in action.commands:
                lines.append(f"    command: {command}")
            lines.append(f"    verify: {action.verification}")
        return "\n".join(lines)

    def format_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def build_readiness_report(root: Path) -> ReadinessReport:
    root = root.resolve()
    doctor = run_doctor(root, strict=True)
    actions = [_action_for_blocker(root, blocker) for blocker in doctor.readiness_blockers]
    return ReadinessReport(root=root, doctor=doctor, actions=actions)


def _action_for_blocker(root: Path, blocker: dict) -> ReadinessAction:
    code = str(blocker.get("code", ""))
    path = str(blocker.get("path", ""))
    if code == "vendor-not-synced":
        vendor = _vendor_from_path(path)
        commands = [f"python -m modeller.cli sync --root {root} {vendor}"] if vendor else []
        return ReadinessAction(
            code=code,
            path=path,
            summary="Confirm the vendor remote/ref, execute the printed subtree sync, then keep the vendor read-only.",
            commands=commands,
            verification=f"python -m modeller.cli doctor --root {root} --strict --json",
        )
    if code == "vendor-not-pinned":
        vendor = _vendor_from_path(path)
        commands = [f"python -m modeller.cli sync --root {root} {vendor}"] if vendor else []
        return ReadinessAction(
            code=code,
            path=path,
            summary="Record the immutable revision that exactly matches the synced vendor content.",
            commands=commands,
            verification=f"python -m modeller.cli doctor --root {root} --strict --json",
        )
    if code == "schema-sibling-fallback":
        commands = []
        try:
            commands.append(" ".join(plan_sync(root, "modeller-pipelines").command))
        except Exception:
            commands.append(f"python -m modeller.cli sync --root {root} modeller-pipelines")
        return ReadinessAction(
            code=code,
            path=path,
            summary="Vendor modeller-pipelines schemas under vendor/modeller-pipelines and pin the exact revision.",
            commands=commands,
            verification=f"python -m modeller.cli doctor --root {root} --strict --json",
        )
    if code == "backend-not-active":
        return ReadinessAction(
            code=code,
            path=path,
            summary="Verify backend.json and run the real backend smoke through backend.json.runner.command before marking the backend active.",
            commands=[
                f"python -m modeller.cli backends --root {root} --check aimsun-psp",
                f"python -m modeller.cli run --root {root} aimsun-psp <pipeline-id> --config <config.yml> --run-dir <run-dir> --backend-root <backend-root>",
            ],
            verification=f"python -m modeller.cli doctor --root {root} --strict --json",
        )
    if code == "reference-pack-not-active":
        return ReadinessAction(
            code=code,
            path=path,
            summary="Close draft-only decisions, verify selected-pack union authorization, then promote the reference pack to active.",
            commands=[f"python -m modeller.cli doctor --root {root} --json"],
            verification=f"python -m modeller.cli doctor --root {root} --strict --json",
        )
    return ReadinessAction(
        code=code,
        path=path,
        summary=str(blocker.get("remediation", "Inspect and remediate this readiness blocker.")),
        verification=f"python -m modeller.cli doctor --root {root} --strict --json",
    )


def _vendor_from_path(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] == "vendor":
        return parts[1]
    return ""
