from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from modeller_memory.candidate.ledger import (
    CandidateEventLedger,
    CandidateLedgerEvent,
    record_candidate_transition,
)
from modeller_memory.candidate.model import (
    AuthorityContext,
    ClassificationResult,
    ContextReceipt,
    MemoryCandidate,
)
from modeller_memory.policy.authority import validate_authority_context
from modeller_memory.policy.classification import classify_target


@dataclass(frozen=True)
class ClassificationLedgerResult:
    """Classified candidate plus append-only evidence for that transition."""

    candidate: MemoryCandidate
    event: CandidateLedgerEvent
    ledger: CandidateEventLedger


def classify(
    candidate: MemoryCandidate,
    authority_context: AuthorityContext,
    *,
    context_receipt: ContextReceipt | None = None,
    current_index_digest: str,
    current_authority_context_digest: str | None = None,
) -> MemoryCandidate:
    """Return the proposed routing decision for a memory candidate."""

    if context_receipt is not None:
        authority_context = replace(authority_context, context_receipt=context_receipt)

    gate = validate_authority_context(
        authority_context,
        current_index_digest=current_index_digest,
        current_authority_context_digest=current_authority_context_digest,
    )
    authority_context_refs = tuple(authority_context.accepted_refs)
    if not gate.ok:
        return candidate.with_result(
            ClassificationResult(
                classification="authority-context-invalid",
                target="flag",
                confidence=min(candidate.confidence or 0.5, 0.5),
                reason_codes=("authority-context-invalid",),
                warnings=gate.warnings,
            ),
            authority_context_refs=authority_context_refs,
            provenance_updates={
                "authority_context_errors": list(gate.errors),
                "authority_context_warnings": list(gate.warnings),
            },
        )

    result = classify_target(candidate, authority_context)
    if gate.warnings:
        result = ClassificationResult(
            classification=result.classification,
            target=result.target,
            confidence=result.confidence,
            reason_codes=result.reason_codes,
            warnings=(*result.warnings, *gate.warnings),
            conflicting_ref=result.conflicting_ref,
        )
    return candidate.with_result(
        result,
        authority_context_refs=authority_context_refs,
        provenance_updates={"authority_context_warnings": list(result.warnings)},
    )


def classify_with_ledger(
    candidate: MemoryCandidate,
    authority_context: AuthorityContext,
    *,
    current_index_digest: str,
    timestamp: str,
    actor: str,
    source: str,
    context_receipt: ContextReceipt | None = None,
    current_authority_context_digest: str | None = None,
    ledger: CandidateEventLedger | None = None,
    reason: str | None = "classification completed",
    evidence_refs: Iterable[str] | None = None,
) -> ClassificationLedgerResult:
    """Classify a candidate and return ledger evidence without changing transport.

    The canonical classify seam still returns only ``MemoryCandidate``. This helper
    is for callers that also need an append-only transition event.
    """

    after = classify(
        candidate,
        authority_context,
        context_receipt=context_receipt,
        current_index_digest=current_index_digest,
        current_authority_context_digest=current_authority_context_digest,
    )
    base_ledger = CandidateEventLedger() if ledger is None else ledger
    event = record_candidate_transition(
        candidate,
        after,
        timestamp=timestamp,
        actor=actor,
        source=source,
        reason=reason,
        evidence_refs=evidence_refs,
        previous_digest=base_ledger.latest_digest,
    )
    return ClassificationLedgerResult(
        candidate=after,
        event=event,
        ledger=base_ledger.append(event),
    )
