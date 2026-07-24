from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntentClassification:
    primary_intent: str = "unknown"
    requested_capability: str = "workflow"
    workflow_family: str | None = None
    v_cycle_stage: str | None = None
    target_path: str | None = None
    requires_workflow: bool | None = None
    mutation_scope: str = "unknown"
    risk_level: str = "low"
    confidence: str = "low"
    reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "primary_intent": self.primary_intent,
            "requested_capability": self.requested_capability,
            "workflow_family": self.workflow_family,
            "v_cycle_stage": self.v_cycle_stage,
            "target_path": self.target_path,
            "requires_workflow": self.requires_workflow,
            "mutation_scope": self.mutation_scope,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class _IntentRule:
    intent: str
    capability: str
    phrases: tuple[str, ...]
    workflow_family: str | None
    stage: str | None
    requires_workflow: bool
    mutation_scope: str
    risk_level: str


_RULES = (
    _IntentRule(
        intent="brief-and-recon",
        capability="v-cycle",
        phrases=("brief and recon", "brief.md", "recon.md", "create a brief", "create brief", "create recon"),
        workflow_family="v-cycle",
        stage="project-governance",
        requires_workflow=True,
        mutation_scope="workflow-artifacts",
        risk_level="medium",
    ),
    _IntentRule(
        intent="documentation-lookup",
        capability="review",
        phrases=("find docs", "find documentation", "summarize docs", "summarise docs", "explain", "locate docs"),
        workflow_family=None,
        stage=None,
        requires_workflow=False,
        mutation_scope="none",
        risk_level="low",
    ),
    _IntentRule(
        intent="read-only-analysis",
        capability="review",
        phrases=("analyse", "analyze", "audit", "inspect", "map structure", "review structure", "inventory"),
        workflow_family=None,
        stage=None,
        requires_workflow=False,
        mutation_scope="none",
        risk_level="low",
    ),
    _IntentRule(
        intent="code-edit",
        capability="v-cycle",
        phrases=("refactor", "implement", "edit code", "fix code", "update code", "change code"),
        workflow_family="v-cycle",
        stage="implementation",
        requires_workflow=True,
        mutation_scope="source-code",
        risk_level="medium",
    ),
    _IntentRule(
        intent="functional-specification",
        capability="v-cycle",
        phrases=("functional specification", "functional spec", "requirements specification", "requirement register"),
        workflow_family="v-cycle",
        stage="functional-specification",
        requires_workflow=True,
        mutation_scope="workflow-artifacts",
        risk_level="medium",
    ),
    _IntentRule(
        intent="test-repair",
        capability="v-cycle",
        phrases=("fix e2e", "e2e test", "e2e tests", "unit test", "unit tests", "integration test", "integration tests"),
        workflow_family="v-cycle",
        stage="integration-testing",
        requires_workflow=True,
        mutation_scope="tests",
        risk_level="medium",
    ),
    _IntentRule(
        intent="system-validation",
        capability="v-cycle",
        phrases=("validate behavior", "validate behaviour", "system validation", "expected behavior", "expected behaviour"),
        workflow_family="v-cycle",
        stage="system-validation",
        requires_workflow=True,
        mutation_scope="validation-artifacts",
        risk_level="medium",
    ),
    _IntentRule(
        intent="deployment",
        capability="v-cycle",
        phrases=("install plugin", "deploy", "deployment", "release", "rollback"),
        workflow_family="v-cycle",
        stage="deployment",
        requires_workflow=True,
        mutation_scope="runtime-installation",
        risk_level="high",
    ),
)


def classify_intent(prompt: str) -> IntentClassification:
    text = _normalise(prompt)
    target_path = extract_target_path(prompt)
    matches = [_match_rule(text, rule) for rule in _RULES]
    matches = [match for match in matches if match[0] > 0]
    if not matches:
        return IntentClassification(
            target_path=target_path,
            reasons=["no natural-language intent rule matched"],
        )

    matches.sort(key=lambda item: item[0], reverse=True)
    best_score, best_rule, best_reasons = matches[0]
    tied = [rule for score, rule, _ in matches if score == best_score and rule.intent != best_rule.intent]
    if tied:
        intents = sorted({best_rule.intent, *(rule.intent for rule in tied)})
        return IntentClassification(
            primary_intent="ambiguous",
            requested_capability="workflow",
            target_path=target_path,
            confidence="low",
            reasons=[f"matched multiple intent families: {', '.join(intents)}"],
            errors=[f"ambiguous natural-language intent: {', '.join(intents)}"],
        )

    confidence = "high" if best_score > 1 else "medium"
    return IntentClassification(
        primary_intent=best_rule.intent,
        requested_capability=best_rule.capability,
        workflow_family=best_rule.workflow_family,
        v_cycle_stage=best_rule.stage,
        target_path=target_path,
        requires_workflow=best_rule.requires_workflow,
        mutation_scope=best_rule.mutation_scope,
        risk_level=best_rule.risk_level,
        confidence=confidence,
        reasons=best_reasons,
    )


def _match_rule(text: str, rule: _IntentRule) -> tuple[int, _IntentRule, list[str]]:
    reasons: list[str] = []
    for phrase in rule.phrases:
        if _contains_phrase(text, phrase):
            reasons.append(f"matched phrase {phrase!r}")
    if rule.intent == "documentation-lookup" and _contains_phrase(text, "do not edit"):
        reasons.append("matched explicit read-only constraint")
    return len(reasons), rule, reasons


def _normalise(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.lower()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9_.-])" + re.escape(phrase.lower()) + r"(?![a-z0-9_.-])"
    return bool(re.search(pattern, text))


def extract_target_path(prompt: str) -> str | None:
    patterns = [
        r"(?P<path>domains[\\/][A-Za-z0-9_. -]+[\\/]pipelines[\\/][A-Za-z0-9_.-]+)",
        r"(?P<path>(?:src|tests|docs|method|schemas|bundles|reference-packs)[\\/][A-Za-z0-9_.\\/-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if not match:
            continue
        value = match.group("path").strip().strip("`'\".,;:)")
        value = value.replace("\\", "/")
        value = re.sub(r"/+", "/", value)
        if _is_safe_relative_path(value):
            return value
    return None


def _is_safe_relative_path(value: str) -> bool:
    path = value.replace("\\", "/")
    if not path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return False
    return ".." not in path.split("/")
