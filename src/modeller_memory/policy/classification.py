from __future__ import annotations

from modeller_memory.candidate.model import (
    AuthorityContext,
    ClassificationResult,
    MemoryCandidate,
)


def classify_target(
    candidate: MemoryCandidate,
    authority_context: AuthorityContext,
) -> ClassificationResult:
    """Classify a candidate without reading any external knowledge store."""

    conflicting_ref = _first_conflicting_ref(candidate)
    if conflicting_ref:
        return ClassificationResult(
            classification="contradiction",
            target="flag",
            confidence=min(candidate.confidence or 0.5, 0.6),
            conflicting_ref=conflicting_ref,
            reason_codes=("contradiction",),
        )

    durability = str(candidate.provenance.get("durability", "")).strip()
    scope = str(candidate.provenance.get("scope", "")).strip()
    passes_rewrite_test = candidate.provenance.get("passes_rewrite_test") is True

    if durability == "ephemeral" or scope in {"session", "run"}:
        return ClassificationResult(
            classification="ephemeral",
            target="companion",
            confidence=_bounded_confidence(candidate.confidence, default=0.65),
            reason_codes=("ephemeral",),
        )

    if durability in {"promotion_candidate", "durable"} and passes_rewrite_test:
        return ClassificationResult(
            classification="durable-candidate",
            target="vault-inbox",
            confidence=_bounded_confidence(candidate.confidence, default=0.8),
            reason_codes=("passes-rewrite-test",),
        )

    return ClassificationResult(
        classification="needs-review",
        target="flag",
        confidence=_bounded_confidence(candidate.confidence, default=0.5),
        reason_codes=("insufficient-promotion-evidence",),
        warnings=(
            "candidate did not declare promotion_candidate/durable durability "
            "and passes_rewrite_test=True",
        ),
    )


def _first_conflicting_ref(candidate: MemoryCandidate) -> str | None:
    if candidate.conflicting_ref:
        return candidate.conflicting_ref
    if candidate.contradictions:
        return candidate.contradictions[0]
    provenance_conflicts = candidate.provenance.get("contradictions")
    if isinstance(provenance_conflicts, list) and provenance_conflicts:
        return str(provenance_conflicts[0])
    if isinstance(provenance_conflicts, tuple) and provenance_conflicts:
        return str(provenance_conflicts[0])
    return None


def _bounded_confidence(value: float, *, default: float) -> float:
    confidence = value if value > 0 else default
    return min(max(confidence, 0.0), 1.0)
