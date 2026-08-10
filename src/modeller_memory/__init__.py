"""modeller_memory - embeddable memory subsystem for the modelling ecosystem.

The package exposes a small candidate-classification runtime plus separate
host-agnostic tools. Runtime modules must remain independent of the tools
subtree.
"""

from modeller_memory.candidate import (
    AuthorityContext,
    CandidateEventLedger,
    CandidateLedgerEvent,
    ClassificationLedgerResult,
    ClassificationResult,
    ContextReceipt,
    MemoryCandidate,
    Result,
    candidate_to_dict,
    classify,
    classify_with_ledger,
    compute_event_digest,
    event_from_dict,
    event_from_json_line,
    event_to_dict,
    event_to_json_line,
    record_candidate_transition,
    validate_event_chain,
)
from modeller_memory.companion import (
    CompanionRecord,
    InMemoryMemoryProvider,
    MemoryProvider,
    MemoryScope,
)
from modeller_memory.policy import validate_authority_context

__all__ = [
    "AuthorityContext",
    "CandidateEventLedger",
    "CandidateLedgerEvent",
    "ClassificationLedgerResult",
    "ClassificationResult",
    "CompanionRecord",
    "ContextReceipt",
    "InMemoryMemoryProvider",
    "MemoryCandidate",
    "MemoryProvider",
    "MemoryScope",
    "Result",
    "candidate_to_dict",
    "classify",
    "classify_with_ledger",
    "compute_event_digest",
    "event_from_dict",
    "event_from_json_line",
    "event_to_dict",
    "event_to_json_line",
    "record_candidate_transition",
    "validate_authority_context",
    "validate_event_chain",
]
