from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, get_args

from modeller_memory.candidate.model import CandidateTarget, MemoryCandidate


LEDGER_SCHEMA_VERSION = "candidate-ledger-event/1"


@dataclass(frozen=True)
class CandidateLedgerEvent:
    """Append-only event record for MemoryCandidate state transitions."""

    candidate_id: str
    transition: str
    state: str
    target: CandidateTarget
    classification: str
    timestamp: str
    actor: str
    source: str
    reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    authority_context_refs: tuple[str, ...] = ()
    previous_digest: str | None = None
    digest: str = ""
    schema_version: str = LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_id",
            "transition",
            "state",
            "classification",
            "timestamp",
            "actor",
            "source",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.target not in get_args(CandidateTarget):
            raise ValueError(f"target must be one of {get_args(CandidateTarget)}")
        if self.schema_version != LEDGER_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.reason is not None:
            _require_text(self.reason, "reason")
        if self.previous_digest is not None:
            _require_text(self.previous_digest, "previous_digest")
        object.__setattr__(
            self, "reason_codes", _tuple_of_text(self.reason_codes, "reason_codes")
        )
        object.__setattr__(
            self, "evidence_refs", _tuple_of_text(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "authority_context_refs",
            _tuple_of_text(self.authority_context_refs, "authority_context_refs"),
        )
        if self.digest:
            _require_text(self.digest, "digest")
        else:
            object.__setattr__(self, "digest", compute_event_digest(self))


@dataclass(frozen=True)
class CandidateEventLedger:
    """Immutable in-memory event ledger.

    This class deliberately performs no file I/O. Callers that need persistence can
    serialize each event with ``event_to_json_line`` and append those lines wherever
    their own storage boundary allows.
    """

    events: tuple[CandidateLedgerEvent, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        errors = validate_event_chain(self.events)
        if errors:
            raise ValueError("; ".join(errors))

    @property
    def latest_digest(self) -> str | None:
        if not self.events:
            return None
        return self.events[-1].digest

    def append(self, event: CandidateLedgerEvent) -> CandidateEventLedger:
        if event.previous_digest != self.latest_digest:
            raise ValueError(
                "event.previous_digest must match the ledger latest digest"
            )
        errors = validate_event_chain((*self.events, event))
        if errors:
            raise ValueError("; ".join(errors))
        return CandidateEventLedger((*self.events, event))

    def append_transition(
        self,
        before: MemoryCandidate,
        after: MemoryCandidate,
        *,
        timestamp: str,
        actor: str,
        source: str,
        transition: str | None = None,
        state: str | None = None,
        reason: str | None = None,
        evidence_refs: Iterable[str] | None = None,
    ) -> CandidateEventLedger:
        event = record_candidate_transition(
            before,
            after,
            timestamp=timestamp,
            actor=actor,
            source=source,
            transition=transition,
            state=state,
            reason=reason,
            evidence_refs=evidence_refs,
            previous_digest=self.latest_digest,
        )
        return self.append(event)

    def to_json_lines(self) -> str:
        return "\n".join(event_to_json_line(event) for event in self.events)


def record_candidate_transition(
    before: MemoryCandidate,
    after: MemoryCandidate,
    *,
    timestamp: str,
    actor: str,
    source: str,
    transition: str | None = None,
    state: str | None = None,
    reason: str | None = None,
    evidence_refs: Iterable[str] | None = None,
    previous_digest: str | None = None,
) -> CandidateLedgerEvent:
    """Build a ledger event from a MemoryCandidate state transition."""

    if before.candidate_id != after.candidate_id:
        raise ValueError("candidate_id cannot change across a ledger transition")
    return CandidateLedgerEvent(
        candidate_id=after.candidate_id,
        transition=transition or f"{_candidate_state(before)}->{_candidate_state(after)}",
        state=state or _candidate_state(after),
        target=after.target,
        classification=after.classification,
        timestamp=timestamp,
        actor=actor,
        source=source,
        reason=reason,
        reason_codes=after.reason_codes,
        evidence_refs=(
            _tuple_of_text(evidence_refs, "evidence_refs")
            if evidence_refs is not None
            else _candidate_evidence_refs(after)
        ),
        authority_context_refs=after.authority_context_refs,
        previous_digest=previous_digest,
    )


def event_to_dict(event: CandidateLedgerEvent) -> dict[str, Any]:
    return _event_payload(event, include_digest=True)


def event_from_dict(
    data: Mapping[str, Any],
    *,
    verify_digest: bool = True,
) -> CandidateLedgerEvent:
    event = CandidateLedgerEvent(
        candidate_id=data["candidate_id"],
        transition=data["transition"],
        state=data["state"],
        target=data["target"],
        classification=data["classification"],
        timestamp=data["timestamp"],
        actor=data["actor"],
        source=data["source"],
        reason=data.get("reason"),
        reason_codes=tuple(data.get("reason_codes", ())),
        evidence_refs=tuple(data.get("evidence_refs", ())),
        authority_context_refs=tuple(data.get("authority_context_refs", ())),
        previous_digest=data.get("previous_digest"),
        digest=data.get("digest", ""),
        schema_version=data.get("schema_version", LEDGER_SCHEMA_VERSION),
    )
    if verify_digest and event.digest != compute_event_digest(event):
        raise ValueError("event digest does not match event payload")
    return event


def event_to_json_line(event: CandidateLedgerEvent) -> str:
    return _canonical_json(event_to_dict(event))


def event_from_json_line(line: str, *, verify_digest: bool = True) -> CandidateLedgerEvent:
    return event_from_dict(json.loads(line), verify_digest=verify_digest)


def compute_event_digest(event: CandidateLedgerEvent) -> str:
    payload = _event_payload(event, include_digest=False)
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def validate_event_chain(events: Iterable[CandidateLedgerEvent]) -> tuple[str, ...]:
    errors: list[str] = []
    previous_digest: str | None = None
    for index, event in enumerate(events):
        if event.previous_digest != previous_digest:
            errors.append(
                f"event {index} previous_digest does not match prior event digest"
            )
        if event.digest != compute_event_digest(event):
            errors.append(f"event {index} digest does not match event payload")
        previous_digest = event.digest
    return tuple(errors)


def _candidate_state(candidate: MemoryCandidate) -> str:
    return f"{candidate.classification}:{candidate.target}"


def _candidate_evidence_refs(candidate: MemoryCandidate) -> tuple[str, ...]:
    refs = candidate.provenance.get("evidence_refs", ())
    return _tuple_of_text(refs, "provenance.evidence_refs")


def _event_payload(
    event: CandidateLedgerEvent, *, include_digest: bool
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "actor": event.actor,
        "authority_context_refs": list(event.authority_context_refs),
        "candidate_id": event.candidate_id,
        "classification": event.classification,
        "evidence_refs": list(event.evidence_refs),
        "previous_digest": event.previous_digest,
        "reason": event.reason,
        "reason_codes": list(event.reason_codes),
        "schema_version": event.schema_version,
        "source": event.source,
        "state": event.state,
        "target": event.target,
        "timestamp": event.timestamp,
        "transition": event.transition,
    }
    if include_digest:
        payload["digest"] = event.digest
    return payload


def _canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _tuple_of_text(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ValueError(f"{field_name} must be an iterable of strings, not a string")
    result = tuple(values)
    for value in result:
        _require_text(value, field_name)
    return result
