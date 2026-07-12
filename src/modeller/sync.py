from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .toml_compat import load_toml


@dataclass
class SyncPlan:
    vendor: str
    command: list[str]
    warnings: list[str] = field(default_factory=list)

    def format(self) -> str:
        lines = [f"vendor {self.vendor}", "command: " + " ".join(self.command)]
        lines.extend(f"warning: {warning}" for warning in self.warnings)
        return "\n".join(lines)


def plan_sync(root: Path, vendor: str) -> SyncPlan:
    vendors = load_toml(root / "vendors.toml").get("vendor", {})
    if vendor not in vendors:
        raise KeyError(f"unknown vendor {vendor!r}")
    cfg = vendors[vendor]
    command = [
        "git",
        "subtree",
        "pull",
        f"--prefix={cfg['prefix']}",
        str(cfg["remote"]),
        str(cfg["ref"]),
    ]
    if cfg.get("squash"):
        command.append("--squash")
    plan = SyncPlan(vendor=vendor, command=command)
    if cfg.get("status") == "planned":
        plan.warnings.append("vendor is planned; confirm remote/ref before executing sync")
    if cfg.get("writable") is not False:
        plan.warnings.append("vendor writable flag is not false")
    return plan


def list_vendors(root: Path) -> list[str]:
    return sorted(load_toml(root / "vendors.toml").get("vendor", {}).keys())

