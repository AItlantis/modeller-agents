from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal


Sensitivity = Literal["public", "internal", "restricted"]
CandidateTarget = Literal["vault-inbox", "companion", "discard", "flag"]


@dataclass(frozen=True)
class ContextReceipt:
    """Receipt for the accepted-context retrieval used before classification."""

    retrieval_query: str
    searched_domains: tuple[str, ...]
    candidate_note_refs: tuple[str, ...]
    selected_note_refs: tuple[str, ...]
    excluded_note_refs: dict[str, str]
    algorithm_version: str
    budget: int
    ranking: tuple[str, ...]
    permissions: tuple[str, ...]
    receipt_digest: str
    authority_context_digest: str | None = None


@dataclass(frozen=True)
class AuthorityContext:
    """Authority facts supplied by the caller for conflict and promotion checks."""

    vault: str
    domain_registry: str
    scope_decision: str
    knowledge_seam_decision: str
    coordination_decision: str
    checked_at: str
    source_index_digest: str
    accepted_refs: tuple[str, ...] = ()
    source_commit: str | None = None
    context_receipt: ContextReceipt | None = None
    authority_context_digest: str | None = None


@dataclass(frozen=True)
class Result:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassificationResult:
    classification: str
    target: CandidateTarget
    confidence: float
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    conflicting_ref: str | None = None


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    claim: str
    provenance: dict[str, Any]
    sensitivity: Sensitivity
    related_decisions: tuple[str, ...]
    origin_run: str
    classification: str = "unclassified"
    target: CandidateTarget = "flag"
    confidence: float = 0.0
    conflicting_ref: str | None = None
    authority_context_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()

    def with_result(
        self,
        result: ClassificationResult,
        *,
        authority_context_refs: tuple[str, ...] | None = None,
        provenance_updates: dict[str, Any] | None = None,
    ) -> MemoryCandidate:
        provenance = self.provenance
        if provenance_updates:
            provenance = {**self.provenance, **provenance_updates}
        return replace(
            self,
            classification=result.classification,
            target=result.target,
            confidence=result.confidence,
            conflicting_ref=result.conflicting_ref,
            authority_context_refs=(
                self.authority_context_refs
                if authority_context_refs is None
                else authority_context_refs
            ),
            reason_codes=result.reason_codes,
            provenance=provenance,
        )


def candidate_to_dict(candidate: MemoryCandidate) -> dict[str, Any]:
    """Return the JSON-serialisable MemoryCandidate transport shape."""

    return {
        "candidate_id": candidate.candidate_id,
        "classification": candidate.classification,
        "claim": candidate.claim,
        "provenance": candidate.provenance,
        "sensitivity": candidate.sensitivity,
        "target": candidate.target,
        "confidence": candidate.confidence,
        "related_decisions": list(candidate.related_decisions),
        "origin_run": candidate.origin_run,
        "conflicting_ref": candidate.conflicting_ref,
        "authority_context_refs": list(candidate.authority_context_refs),
        "reason_codes": list(candidate.reason_codes),
        "contradictions": list(candidate.contradictions),
    }
