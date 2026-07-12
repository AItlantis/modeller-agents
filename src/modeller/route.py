from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .knowledge_packs import resolve_knowledge_selection
from .reference_packs import validate_reference_pack
from .workflow import check_current_step


CAPABILITY_SKILLS = {
    "antagonist-review": "antagonist-review",
    "backend-align": "backend-align",
    "backend-contract-check": "backend-contract-check",
    "backend-scaffold": "backend-scaffold",
    "backend_run": "backend-contract-check",
    "run_backend": "backend-contract-check",
    "memory-recon": "memory-recon",
    "pipeline-fix": "pipeline-fix",
    "pipeline-review": "pipeline-review",
    "pipeline-smoke": "pipeline-smoke",
    "recon": "memory-recon",
    "orchestrate": "orchestrate",
    "review": "review",
    "source-boundary-check": "source-boundary-check",
    "workflow": "workflow",
}


@dataclass
class RouteDecision:
    target_repository: str
    skill: str
    bundle: str | None
    routing_key_kind: str = ""
    reference_packs: list[str] = field(default_factory=list)
    consent_required: bool = True
    max_risk_level: str = "low"
    knowledge_domains: list[dict] = field(default_factory=list)
    knowledge_packs: list[str] = field(default_factory=list)
    knowledge_budget: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    run_id: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "target_repository": self.target_repository,
            "skill": self.skill,
            "bundle": self.bundle,
            "routing_key_kind": self.routing_key_kind,
            "reference_packs": self.reference_packs,
            "knowledge_domains": self.knowledge_domains,
            "knowledge_packs": self.knowledge_packs,
            "knowledge_budget": self.knowledge_budget,
            "consent_required": self.consent_required,
            "max_risk_level": self.max_risk_level,
            "warnings": self.warnings,
            "errors": self.errors,
            "run_id": self.run_id,
        }

    def format(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def route_envelope(root: Path, envelope_path: Path, run_id: str | None = None) -> RouteDecision:
    envelope = json.loads(envelope_path.read_text(encoding="utf-8-sig"))
    intent = envelope.get("intent", {})
    policy = envelope.get("execution_policy", {})
    target_repository = intent.get("target_repository") or ""
    requested_capability = intent.get("requested_capability") or "workflow"

    requested_capability = str(requested_capability)
    skill = CAPABILITY_SKILLS.get(requested_capability)
    decision = RouteDecision(
        target_repository=target_repository,
        skill=skill or "workflow",
        bundle=None,
        consent_required=bool(policy.get("consent_required", True)),
        max_risk_level=str(policy.get("max_risk_level", "low")),
    )
    if skill is None:
        decision.errors.append(f"unknown requested_capability {requested_capability!r}")
        return decision
    if not target_repository:
        decision.errors.append("intent.target_repository is required for deterministic routing")
        return decision

    bundle_path = root / "bundles" / f"{target_repository}.bundle.json"
    if not bundle_path.exists():
        decision.errors.append(f"no bundle found for target repository {target_repository!r}")
        return decision
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    decision.bundle = bundle.get("id")
    decision.routing_key_kind = str(bundle.get("routingKeyKind", ""))
    if decision.routing_key_kind not in {"repository", "repository-class"}:
        decision.errors.append(f"bundle {bundle_path.name} must declare routingKeyKind repository or repository-class")
    decision.reference_packs = list(bundle.get("referencePacks", []))
    if skill not in bundle.get("skills", []):
        decision.errors.append(f"selected skill {skill!r} is not declared by bundle {bundle_path.name}")
    knowledge = resolve_knowledge_selection(
        root,
        requested_domains=intent.get("domains", []),
        default_domains=bundle.get("defaultKnowledge", []),
        skill=skill,
    )
    decision.knowledge_domains = knowledge.domains
    decision.knowledge_packs = knowledge.packs
    decision.knowledge_budget = knowledge.budget
    decision.errors.extend(knowledge.errors)
    decision.warnings.extend(knowledge.warnings)
    authorized_by_pack = False
    if not decision.reference_packs:
        decision.errors.append(f"bundle {bundle_path.name} does not select any reference packs")
    for rel_path in decision.reference_packs:
        pack = validate_reference_pack(root, rel_path)
        decision.errors.extend(pack.errors)
        decision.warnings.extend(pack.warnings)
        if pack.ok and skill in pack.skills:
            authorized_by_pack = True
        elif pack.ok:
            decision.warnings.append(f"selected skill {skill!r} is not declared by reference pack {rel_path}")
    if not authorized_by_pack:
        decision.errors.append(f"selected skill {skill!r} is not authorized by any selected reference pack")
    if decision.max_risk_level in {"medium", "high"} and not decision.consent_required:
        decision.errors.append("medium/high risk envelopes must require consent")

    run_id = run_id or policy.get("run_id") or intent.get("run_id")
    requires_workflow = bool(policy.get("requires_workflow", skill == "orchestrate"))
    if requires_workflow:
        if not run_id:
            decision.errors.append(
                "orchestration requires execution_policy.run_id naming an active deterministic workflow run"
            )
        else:
            run_id = str(run_id)
            try:
                gate = check_current_step(root, run_id)
            except Exception:
                decision.errors.append(
                    f"workflow run {run_id!r} not found or not initialized; "
                    f"run `modeller.cli workflow init --run-id {run_id}` first"
                )
            else:
                decision.run_id = run_id
                if not gate.ok:
                    decision.errors.append(
                        f"deterministic workflow gate not satisfied for run {run_id!r}: {gate.errors}"
                    )
    return decision
