from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .capabilities import CAPABILITY_SKILLS, canonical_skill_for_capability
from .contracts import validate_active_context_envelope
from .knowledge_packs import resolve_knowledge_selection
from .reference_packs import validate_reference_pack
from .runtime import runtime_path
from .vcycle import check_v_cycle_current_stage, load_v_cycle_state
from .workflow import check_current_step

# ---------------------------------------------------------------------------
# Envelope-purpose reconciliation (WI-03, Phase 1.5 Testudo Gateway mission).
#
# Two distinct shapes are both informally called "the envelope" in this
# codebase and share one example filename (examples/testudo-context-envelope.json),
# but they serve different purposes and are NOT merged into one flat shape:
#
#   1. The routing-instruction shape this module has always consumed:
#      top-level `intent` (user_text/requested_capability/target_repository/...)
#      and `execution_policy` (consent_required/max_risk_level/gate_policy/...).
#      This is a modeller-agents-internal routing/dispatch concept with no
#      counterpart in testudo-backend's documented contracts. It is generated
#      internally by planning.draft_intent().to_envelope() for the common
#      (orchestrator/planning) call path, and supplied externally via the CLI
#      `route --envelope` fixture for the testudo-facing call path.
#
#   2. testudo-backend's ActiveContextEnvelope contract (schema_version,
#      active_context_revision_id, project_id, principal_id, created_at,
#      context_digest, ...) -- a context/permission snapshot, not a routing
#      instruction. It has no target_repository, intent, or execution_policy
#      fields at all (see contracts/active-context-envelope.schema.json).
#
# Reconciliation choice (option ii from the Phase 1.5 plan): route_payload's
# accepted payload is a modeller-agents-internal envelope that MAY embed a
# validated ActiveContextEnvelope as an optional sibling field named
# `active_context`. When present, it is schema-validated up front (before
# intent/policy extraction) via validate_active_context_envelope(); when
# absent (the existing internal orchestrator/planning call path, which never
# populates it), validation is skipped entirely and prior behavior is
# unchanged. The two shapes are never merged into one flat object. This is
# flagged in gap-analysis.md as a genuine envelope-purpose mismatch
# discovered during WI-03 implementation, not silently absorbed.
# ---------------------------------------------------------------------------


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
    return route_payload(root, envelope, run_id=run_id)


def route_payload(root: Path, envelope: dict, run_id: str | None = None) -> RouteDecision:
    active_context = envelope.get("active_context")
    if active_context is not None:
        context_check = validate_active_context_envelope(root, active_context)
        if not context_check.ok:
            decision = RouteDecision(target_repository="", skill="workflow", bundle=None)
            decision.errors.extend(
                f"active_context: {error}" for error in context_check.errors
            )
            return decision

    intent = envelope.get("intent", {})
    policy = envelope.get("execution_policy", {})
    target_repository = intent.get("target_repository") or ""
    requested_capability = intent.get("requested_capability") or "workflow"

    requested_capability = str(requested_capability)
    skill = canonical_skill_for_capability(requested_capability)
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

    bundle_path = runtime_path(root, "bundles", f"{target_repository}.bundle.json")
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
    workflow_family = str(policy.get("workflow_family") or intent.get("workflow_family") or "")
    gate_policy = str(policy.get("gate_policy") or "check-current-gate")
    if gate_policy not in {"bind-run", "check-current-gate"}:
        decision.errors.append(f"unknown execution_policy.gate_policy {gate_policy!r}")
        return decision
    requires_workflow = (
        bool(policy["requires_workflow"])
        if "requires_workflow" in policy
        else skill in {"orchestrate", "v-cycle"} or workflow_family == "v-cycle"
    )
    requested_stage = str(intent.get("v_cycle_stage") or policy.get("v_cycle_stage") or "")
    if requires_workflow:
        if not run_id:
            decision.errors.append(
                "orchestration requires execution_policy.run_id naming an active workflow run"
            )
        else:
            run_id = str(run_id)
            try:
                if workflow_family == "v-cycle" or skill == "v-cycle":
                    _validate_v_cycle_stage(root, run_id, requested_stage, decision)
                if gate_policy == "bind-run":
                    decision.run_id = run_id
                    return decision
                gate = (
                    check_v_cycle_current_stage(root, run_id)
                    if workflow_family == "v-cycle" or skill == "v-cycle"
                    else check_current_step(root, run_id)
                )
            except Exception:
                decision.errors.append(
                    f"workflow run {run_id!r} not found or not initialized; "
                    f"run `modeller.cli workflow init --run-id {run_id}` first"
                )
            else:
                decision.run_id = run_id
                if not gate.ok:
                    decision.errors.append(
                        f"workflow gate not satisfied for run {run_id!r}: {gate.errors}"
                    )
    return decision


def _validate_v_cycle_stage(root: Path, run_id: str, requested_stage: str, decision: RouteDecision) -> None:
    if not requested_stage:
        return
    state = load_v_cycle_state(root, run_id)
    current_index = int(state.get("current_stage_index", 0))
    stages = state.get("stages", [])
    if not isinstance(stages, list) or current_index >= len(stages):
        decision.errors.append(f"workflow run {run_id!r} has no current V-cycle stage")
        return
    current = stages[current_index]
    current_stage = str(current.get("id", ""))
    if requested_stage != current_stage:
        decision.errors.append(
            f"workflow run {run_id!r} current V-cycle stage {current_stage!r} "
            f"does not match requested stage {requested_stage!r}"
        )
