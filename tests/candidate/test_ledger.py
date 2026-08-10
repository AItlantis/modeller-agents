from __future__ import annotations

import json

import pytest

from modeller_memory import (
    CandidateEventLedger,
    ClassificationResult,
    MemoryCandidate,
    event_from_dict,
    event_from_json_line,
    event_to_dict,
    event_to_json_line,
    record_candidate_transition,
    validate_event_chain,
)


def _candidate(**overrides: object) -> MemoryCandidate:
    values = {
        "candidate_id": "memcand-20260714-001",
        "claim": "Durable modelling observation",
        "provenance": {
            "origin_run": "run-20260714-001",
            "source_repository": "modeller-memory",
            "evidence_refs": ["docs/dev/N2-C1-classify-runtime-plan.md"],
            "durability": "promotion_candidate",
        },
        "sensitivity": "internal",
        "related_decisions": ("0007-memory-promotion-coordination",),
        "origin_run": "run-20260714-001",
        "confidence": 0.84,
    }
    values.update(overrides)
    return MemoryCandidate(**values)


def _classified_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    return candidate.with_result(
        ClassificationResult(
            classification="durable-candidate",
            target="vault-inbox",
            confidence=0.84,
            reason_codes=("durable", "passes-rewrite-test"),
        ),
        authority_context_refs=("decisions/0007-memory-promotion-coordination",),
    )


def test_record_transition_captures_candidate_state_and_refs() -> None:
    before = _candidate()
    after = _classified_candidate(before)

    event = record_candidate_transition(
        before,
        after,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
        reason="classification completed",
    )

    assert event.candidate_id == before.candidate_id
    assert event.transition == "unclassified:flag->durable-candidate:vault-inbox"
    assert event.state == "durable-candidate:vault-inbox"
    assert event.target == "vault-inbox"
    assert event.classification == "durable-candidate"
    assert event.reason_codes == ("durable", "passes-rewrite-test")
    assert event.evidence_refs == ("docs/dev/N2-C1-classify-runtime-plan.md",)
    assert event.authority_context_refs == (
        "decisions/0007-memory-promotion-coordination",
    )
    assert event.previous_digest is None
    assert event.digest.startswith("sha256:")


def test_ledger_append_is_immutable_and_chained() -> None:
    before = _candidate()
    after = _classified_candidate(before)

    ledger = CandidateEventLedger()
    updated = ledger.append_transition(
        before,
        after,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
    )
    second = updated.append_transition(
        after,
        after.with_result(
            ClassificationResult(
                classification="contradiction",
                target="flag",
                confidence=0.5,
                reason_codes=("contradiction",),
                conflicting_ref="decisions/0007-memory-promotion-coordination",
            )
        ),
        timestamp="2026-07-14T09:16:00+04:00",
        actor="tests/candidate",
        source="unit-test",
        evidence_refs=("decisions/0007-memory-promotion-coordination",),
    )

    assert ledger.events == ()
    assert len(updated.events) == 1
    assert len(second.events) == 2
    assert second.events[1].previous_digest == updated.events[0].digest
    assert validate_event_chain(second.events) == ()


def test_event_dict_and_json_line_round_trip() -> None:
    before = _candidate()
    after = _classified_candidate(before)
    event = record_candidate_transition(
        before,
        after,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
    )

    data = event_to_dict(event)
    from_dict = event_from_dict(data)
    line = event_to_json_line(from_dict)
    from_line = event_from_json_line(line)

    assert json.loads(line) == data
    assert from_dict == event
    assert from_line == event


def test_event_from_dict_rejects_digest_tampering() -> None:
    before = _candidate()
    after = _classified_candidate(before)
    event = record_candidate_transition(
        before,
        after,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
    )
    data = event_to_dict(event)
    data["target"] = "discard"

    with pytest.raises(ValueError, match="digest"):
        event_from_dict(data)


def test_append_rejects_broken_chain() -> None:
    before = _candidate()
    after = _classified_candidate(before)
    ledger = CandidateEventLedger().append_transition(
        before,
        after,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
    )
    broken_event = record_candidate_transition(
        after,
        after,
        timestamp="2026-07-14T09:16:00+04:00",
        actor="tests/candidate",
        source="unit-test",
        previous_digest="sha256:not-the-latest",
    )

    with pytest.raises(ValueError, match="previous_digest"):
        ledger.append(broken_event)


def test_runtime_ledger_rejects_candidate_id_changes() -> None:
    before = _candidate(candidate_id="memcand-20260714-001")
    after = _classified_candidate(_candidate(candidate_id="memcand-20260714-002"))

    with pytest.raises(ValueError, match="candidate_id"):
        record_candidate_transition(
            before,
            after,
            timestamp="2026-07-14T09:15:00+04:00",
            actor="tests/candidate",
            source="unit-test",
        )
