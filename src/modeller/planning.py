from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .capabilities import CAPABILITY_SKILLS, canonical_skill_for_capability
from .intents import IntentClassification, classify_intent
from .route import RouteDecision, route_payload
from .runtime import discover_workspace_source_root, runtime_path, runtime_relative_path, runtime_root
from .toml_compat import load_toml
from .vcycle import list_v_cycle_workflows
from .workflow import DEFAULT_WORKFLOW, load_workflow


@dataclass
class IntentDraft:
    prompt: str
    target_repository: str = ""
    requested_capability: str = "workflow"
    domains: list[str] = field(default_factory=list)
    run_id: str | None = None
    requires_workflow: bool | None = None
    workflow_family: str | None = None
    v_cycle_stage: str | None = None
    target_path: str | None = None
    gate_policy: str | None = None
    mutation_scope: str | None = None
    intent_classification: IntentClassification | None = None
    consent_required: bool = True
    max_risk_level: str = "low"
    status: str = "draft"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_envelope(self) -> dict:
        intent = {
            "user_text": self.prompt,
            "target_repository": self.target_repository,
            "requested_capability": self.requested_capability,
        }
        if self.domains:
            intent["domains"] = list(self.domains)
        if self.run_id:
            intent["run_id"] = self.run_id
        if self.workflow_family:
            intent["workflow_family"] = self.workflow_family
        if self.v_cycle_stage:
            intent["v_cycle_stage"] = self.v_cycle_stage
        if self.target_path:
            intent["target_path"] = self.target_path
        if self.mutation_scope:
            intent["mutation_scope"] = self.mutation_scope
        if self.intent_classification is not None:
            intent["classification"] = self.intent_classification.to_dict()
        policy = {
            "consent_required": self.consent_required,
            "max_risk_level": self.max_risk_level,
        }
        if self.requires_workflow is not None:
            policy["requires_workflow"] = self.requires_workflow
        if self.run_id:
            policy["run_id"] = self.run_id
        if self.workflow_family:
            policy["workflow_family"] = self.workflow_family
        if self.gate_policy:
            policy["gate_policy"] = self.gate_policy
        return {"intent": intent, "execution_policy": policy}

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "target_repository": self.target_repository,
            "requested_capability": self.requested_capability,
            "domains": self.domains,
            "run_id": self.run_id,
            "requires_workflow": self.requires_workflow,
            "workflow_family": self.workflow_family,
            "v_cycle_stage": self.v_cycle_stage,
            "target_path": self.target_path,
            "gate_policy": self.gate_policy,
            "mutation_scope": self.mutation_scope,
            "intent_classification": (
                self.intent_classification.to_dict() if self.intent_classification is not None else None
            ),
            "consent_required": self.consent_required,
            "max_risk_level": self.max_risk_level,
            "status": self.status,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class AlignmentContract:
    target_repository: str
    source_root: str
    allowed_runtime_root: str
    consent_required: bool
    max_risk_level: str
    approval_state: str
    status: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_repository": self.target_repository,
            "source_root": self.source_root,
            "allowed_runtime_root": self.allowed_runtime_root,
            "consent_required": self.consent_required,
            "max_risk_level": self.max_risk_level,
            "approval_state": self.approval_state,
            "status": self.status,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class WorkflowCatalog:
    workflows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"workflows": self.workflows, "errors": self.errors}


@dataclass
class SkillPlan:
    requested_capability: str
    skill: str
    bundle: str | None
    reference_packs: list[str]
    knowledge_domains: list[dict]
    knowledge_packs: list[str]
    status: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_route(cls, requested_capability: str, decision: RouteDecision) -> SkillPlan:
        return cls(
            requested_capability=requested_capability,
            skill=decision.skill,
            bundle=decision.bundle,
            reference_packs=decision.reference_packs,
            knowledge_domains=decision.knowledge_domains,
            knowledge_packs=decision.knowledge_packs,
            status="ready" if decision.ok else "blocked",
            warnings=decision.warnings,
            errors=decision.errors,
        )

    def to_dict(self) -> dict:
        return {
            "requested_capability": self.requested_capability,
            "skill": self.skill,
            "bundle": self.bundle,
            "reference_packs": self.reference_packs,
            "knowledge_domains": self.knowledge_domains,
            "knowledge_packs": self.knowledge_packs,
            "status": self.status,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class ToolPlan:
    status: str
    commands: list[list[str]] = field(default_factory=list)
    approval_steps: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "commands": self.commands,
            "approval_steps": self.approval_steps,
            "blocked_by": self.blocked_by,
        }


@dataclass
class RepositoryCapabilityManifest:
    root: str
    capabilities: dict[str, str]
    bundles: list[dict] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    backends: list[dict] = field(default_factory=list)
    workflows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "capabilities": self.capabilities,
            "bundles": self.bundles,
            "skills": self.skills,
            "backends": self.backends,
            "workflows": self.workflows,
            "errors": self.errors,
        }


@dataclass
class ExecutionPlan:
    ok: bool
    intent_draft: IntentDraft
    alignment_contract: AlignmentContract
    workflow_catalog: WorkflowCatalog
    skill_plan: SkillPlan
    tool_plan: ToolPlan
    capability_manifest: RepositoryCapabilityManifest
    context_envelope: dict

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "intent_draft": self.intent_draft.to_dict(),
            "alignment_contract": self.alignment_contract.to_dict(),
            "workflow_catalog": self.workflow_catalog.to_dict(),
            "skill_plan": self.skill_plan.to_dict(),
            "tool_plan": self.tool_plan.to_dict(),
            "capability_manifest": self.capability_manifest.to_dict(),
            "context_envelope": self.context_envelope,
        }

    def format(self) -> str:
        lines = [f"execution plan: {'OK' if self.ok else 'BLOCKED'}"]
        lines.append(f"target_repository: {self.intent_draft.target_repository or '<missing>'}")
        lines.append(f"requested_capability: {self.intent_draft.requested_capability}")
        lines.append(f"skill: {self.skill_plan.skill}")
        lines.append(f"approval_state: {self.alignment_contract.approval_state}")
        if self.tool_plan.blocked_by:
            lines.append("blocked_by:")
            lines.extend(f"  - {item}" for item in self.tool_plan.blocked_by)
        if self.tool_plan.commands:
            lines.append("suggested_commands:")
            lines.extend("  - " + " ".join(command) for command in self.tool_plan.commands)
        return "\n".join(lines)


def build_execution_plan(
    root: Path,
    prompt: str,
    *,
    target_repository: str | None = None,
    requested_capability: str | None = None,
    domains: list[str] | None = None,
    run_id: str | None = None,
    requires_workflow: bool | None = None,
    consent_required: bool = True,
    max_risk_level: str = "low",
    gate_policy: str | None = None,
    envelope_output: Path | None = None,
) -> ExecutionPlan:
    manifest = discover_repository_capabilities(root)
    catalog = load_workflow_catalog(root)
    draft = draft_intent(
        prompt,
        manifest=manifest,
        target_repository=target_repository,
        requested_capability=requested_capability,
        domains=domains or [],
        run_id=run_id,
        requires_workflow=requires_workflow,
        consent_required=consent_required,
        max_risk_level=max_risk_level,
        gate_policy=gate_policy,
    )
    envelope = draft.to_envelope()
    if draft.errors:
        decision = RouteDecision(
            target_repository=draft.target_repository,
            skill=canonical_skill_for_capability(draft.requested_capability) or "workflow",
            bundle=None,
            errors=list(draft.errors),
        )
    else:
        decision = route_payload(root, envelope, run_id=run_id)
    skill_plan = SkillPlan.from_route(draft.requested_capability, decision)
    alignment = build_alignment_contract(root, draft, skill_plan)
    tool_plan = build_tool_plan(root, draft, skill_plan, envelope_output=envelope_output)
    ok = not draft.errors and skill_plan.status == "ready" and not alignment.errors
    return ExecutionPlan(
        ok=ok,
        intent_draft=draft,
        alignment_contract=alignment,
        workflow_catalog=catalog,
        skill_plan=skill_plan,
        tool_plan=tool_plan,
        capability_manifest=manifest,
        context_envelope=envelope,
    )


def draft_intent(
    prompt: str,
    *,
    manifest: RepositoryCapabilityManifest,
    target_repository: str | None = None,
    requested_capability: str | None = None,
    domains: list[str] | None = None,
    run_id: str | None = None,
    requires_workflow: bool | None = None,
    consent_required: bool = True,
    max_risk_level: str = "low",
    gate_policy: str | None = None,
) -> IntentDraft:
    warnings: list[str] = []
    errors: list[str] = []
    target = target_repository or _infer_one(prompt, [bundle["id"] for bundle in manifest.bundles])
    if not target:
        errors.append("target_repository is required or must be mentioned unambiguously in the prompt")
    elif target_repository is None:
        warnings.append(f"inferred target_repository {target!r} from prompt")

    classification = classify_intent(prompt)
    capability = requested_capability or _infer_one(prompt, sorted(manifest.capabilities))
    if not capability:
        if classification.errors:
            capability = "workflow"
            errors.extend(classification.errors)
        elif classification.requested_capability in manifest.capabilities:
            capability = classification.requested_capability
            warnings.append(
                f"inferred requested_capability {capability!r} from natural-language intent "
                f"{classification.primary_intent!r}"
            )
        else:
            capability = "workflow"
            warnings.append("defaulted requested_capability to 'workflow'")
    elif requested_capability is None:
        warnings.append(f"inferred requested_capability {capability!r} from prompt")
    if canonical_skill_for_capability(capability) is None:
        errors.append(f"unknown requested_capability {capability!r}")

    if max_risk_level not in {"low", "medium", "high"}:
        errors.append("max_risk_level must be one of low, medium, or high")
    if max_risk_level in {"medium", "high"} and not consent_required:
        errors.append("medium/high risk plans must require consent")
    if gate_policy is not None and gate_policy not in {"bind-run", "check-current-gate"}:
        errors.append("gate_policy must be bind-run or check-current-gate")

    selected_skill = canonical_skill_for_capability(capability)
    use_classifier_policy = classification.requested_capability == capability and not classification.errors
    use_workflow_metadata = (
        classification.workflow_family is not None
        and selected_skill == "v-cycle"
        and use_classifier_policy
    )
    resolved_requires_workflow = requires_workflow
    if resolved_requires_workflow is None and use_classifier_policy:
        resolved_requires_workflow = classification.requires_workflow
    resolved_risk = max_risk_level
    if use_workflow_metadata and max_risk_level == "low" and classification.risk_level in {"medium", "high"}:
        resolved_risk = classification.risk_level
    resolved_gate_policy = gate_policy
    if resolved_gate_policy is None and use_workflow_metadata:
        resolved_gate_policy = "bind-run"

    status = "blocked" if errors else "draft"
    return IntentDraft(
        prompt=prompt,
        target_repository=target or "",
        requested_capability=capability,
        domains=list(domains or []),
        run_id=run_id,
        requires_workflow=resolved_requires_workflow,
        workflow_family=classification.workflow_family if use_workflow_metadata else None,
        v_cycle_stage=classification.v_cycle_stage if use_workflow_metadata else None,
        target_path=classification.target_path,
        gate_policy=resolved_gate_policy,
        mutation_scope=classification.mutation_scope if use_classifier_policy else None,
        intent_classification=classification,
        consent_required=consent_required,
        max_risk_level=resolved_risk,
        status=status,
        warnings=warnings,
        errors=errors,
    )


def build_alignment_contract(root: Path, draft: IntentDraft, skill_plan: SkillPlan) -> AlignmentContract:
    errors = list(draft.errors)
    if skill_plan.errors:
        errors.extend(skill_plan.errors)
    source_root = root
    if _should_use_external_source_root(root, draft.target_repository):
        source_root = discover_workspace_source_root(root, draft.target_repository) or root
    approval_state = "requires-user-approval" if draft.consent_required else "pre-approved-by-policy"
    return AlignmentContract(
        target_repository=draft.target_repository,
        source_root=str(source_root.resolve()),
        allowed_runtime_root=str(runtime_root(root).resolve()),
        consent_required=draft.consent_required,
        max_risk_level=draft.max_risk_level,
        approval_state=approval_state,
        status="blocked" if errors else "aligned",
        errors=errors,
    )


def _should_use_external_source_root(root: Path, target_repository: str) -> bool:
    target = str(target_repository or "").strip()
    if not target or root.name == target:
        return False
    bundle_dir = runtime_path(root, "bundles")
    if not bundle_dir.exists():
        return False
    known_repository_ids = {path.name.removesuffix(".bundle.json") for path in bundle_dir.glob("*.bundle.json")}
    return root.name in known_repository_ids and target in known_repository_ids


def build_tool_plan(
    root: Path,
    draft: IntentDraft,
    skill_plan: SkillPlan,
    *,
    envelope_output: Path | None = None,
) -> ToolPlan:
    commands = [["python", "-m", "modeller.cli", "doctor", "--root", str(root), "--json"]]
    blocked_by = list(draft.errors) + list(skill_plan.errors)
    if envelope_output is not None:
        route_command = [
            "python",
            "-m",
            "modeller.cli",
            "route",
            "--root",
            str(root),
            "--envelope",
            str(envelope_output),
        ]
        if draft.run_id:
            route_command.extend(["--run-id", draft.run_id])
        commands.append(route_command)
    elif not blocked_by:
        blocked_by.append("no envelope_output was supplied; route command needs a persisted envelope")
    workflow_required = (
        draft.requires_workflow
        if draft.requires_workflow is not None
        else skill_plan.skill in {"orchestrate", "v-cycle"} or draft.workflow_family == "v-cycle"
    )
    if workflow_required:
        if draft.run_id:
            workflow_command = "status" if draft.gate_policy == "bind-run" else "check"
            commands.append(
                ["python", "-m", "modeller.cli", "workflow", "--root", str(root), workflow_command, "--run-id", draft.run_id]
            )
        else:
            if draft.workflow_family == "v-cycle" and draft.v_cycle_stage:
                commands.append(
                    [
                        "python",
                        "-m",
                        "modeller.cli",
                        "workflow",
                        "--root",
                        str(root),
                        "init",
                        "--run-id",
                        "<run-id>",
                        "--family",
                        "v-cycle",
                        "--mode",
                        "stage",
                        "--stage",
                        draft.v_cycle_stage,
                    ]
                )
            blocked_by.append("workflow-gated plans require a run_id before route approval")
    approval_steps = []
    if draft.consent_required:
        approval_steps.append("review the context_envelope and approve before executing route/run commands")
    return ToolPlan(
        status="blocked" if blocked_by else "ready",
        commands=commands,
        approval_steps=approval_steps,
        blocked_by=blocked_by,
    )


def discover_repository_capabilities(root: Path) -> RepositoryCapabilityManifest:
    errors: list[str] = []
    bundles: list[dict] = []
    assets = runtime_root(root)
    for bundle_path in sorted((assets / "bundles").glob("*.bundle.json")):
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{runtime_relative_path(root, bundle_path)}: {exc}")
            continue
        bundles.append(
            {
                "id": str(bundle.get("id") or bundle_path.name.removesuffix(".bundle.json")),
                "status": str(bundle.get("status", "")),
                "routing_key_kind": str(bundle.get("routingKeyKind", "")),
                "skills": list(bundle.get("skills", [])) if isinstance(bundle.get("skills"), list) else [],
                "reference_packs": (
                    list(bundle.get("referencePacks", [])) if isinstance(bundle.get("referencePacks"), list) else []
                ),
                "default_knowledge": (
                    list(bundle.get("defaultKnowledge", [])) if isinstance(bundle.get("defaultKnowledge"), list) else []
                ),
            }
        )
    skills = sorted(
        path.name for path in (root / ".claude/plugins/modeller/skills").iterdir() if path.is_dir()
    ) if (root / ".claude/plugins/modeller/skills").exists() else []
    backends = _load_backend_summaries(root, errors)
    workflows = load_workflow_catalog(root).workflows
    return RepositoryCapabilityManifest(
        root=str(root.resolve()),
        capabilities=dict(sorted(CAPABILITY_SKILLS.items())),
        bundles=bundles,
        skills=skills,
        backends=backends,
        workflows=workflows,
        errors=errors,
    )


def load_workflow_catalog(root: Path) -> WorkflowCatalog:
    workflows: list[dict] = []
    errors: list[str] = []
    workflow_dir = runtime_path(root, "method", "workflows")
    for workflow_path in sorted(workflow_dir.glob("*.workflow.json")):
        try:
            workflow = load_workflow(root, workflow_path.name.removesuffix(".workflow.json"))
        except Exception as exc:
            errors.append(f"{runtime_relative_path(root, workflow_path)}: {exc}")
            continue
        workflows.append(
            {
                "workflow_id": str(workflow.get("workflow_id", workflow_path.name.removesuffix(".workflow.json"))),
                "name": str(workflow.get("name", "")),
                "description": str(workflow.get("description", "")),
                "step_count": len(workflow.get("steps", [])) if isinstance(workflow.get("steps"), list) else 0,
                "steps": [
                    {
                        "id": str(step.get("id", "")),
                        "title": str(step.get("title", "")),
                        "owner": str(step.get("owner", "")),
                        "required_artifacts": list(step.get("required_artifacts", [])),
                    }
                    for step in workflow.get("steps", [])
                    if isinstance(step, dict)
                ],
            }
        )
    if not workflows:
        errors.append("no workflow definitions discovered under method/workflows")
    try:
        workflows.extend(list_v_cycle_workflows(root))
    except FileNotFoundError:
        pass
    except Exception as exc:
        errors.append(f"v-cycle workflow assets: {exc}")
    return WorkflowCatalog(workflows=workflows, errors=errors)


def write_context_envelope(path: Path, envelope: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return path


def _load_backend_summaries(root: Path, errors: list[str]) -> list[dict]:
    try:
        data = load_toml(runtime_path(root, "backends.toml"))
    except Exception as exc:
        errors.append(f"backends.toml: {exc}")
        return []
    backends = []
    for backend_id, config in sorted(data.get("backend", {}).items()):
        if not isinstance(config, dict):
            continue
        backends.append(
            {
                "id": str(backend_id),
                "status": str(config.get("status", "")),
                "backend_id": str(config.get("backend_id", "")),
                "expected_contract": str(config.get("expected_contract", "")),
            }
        )
    return backends


def _infer_one(prompt: str, candidates: list[str]) -> str:
    matches = [candidate for candidate in candidates if _contains_token(prompt, candidate)]
    return matches[0] if len(matches) == 1 else ""


def _contains_token(text: str, token: str) -> bool:
    pattern = r"(?<![A-Za-z0-9_.-])" + re.escape(token.lower()) + r"(?![A-Za-z0-9_.-])"
    return bool(re.search(pattern, text.lower()))
