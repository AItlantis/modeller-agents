from __future__ import annotations

import json
from pathlib import Path

from modeller_memory import (
    AuthorityContext,
    CandidateEventLedger,
    ContextReceipt,
    MemoryCandidate,
    candidate_to_dict,
    classify,
    classify_with_ledger,
)


ROOT = Path(__file__).resolve().parents[2]
INDEX_DIGEST = "sha256:index-current"
CONTEXT_DIGEST = "sha256:context-current"


def _receipt() -> ContextReceipt:
    return ContextReceipt(
        retrieval_query="classify durable modelling observation",
        searched_domains=("transport",),
        candidate_note_refs=("domains/transport/memory-promotion.md",),
        selected_note_refs=("decisions/0007-memory-promotion-coordination",),
        excluded_note_refs={"domains/transport/archive.md": "not current"},
        algorithm_version="context-retrieval/1",
        budget=10,
        ranking=("decisions/0007-memory-promotion-coordination",),
        permissions=("internal",),
        receipt_digest="sha256:receipt",
        authority_context_digest=CONTEXT_DIGEST,
    )


def _authority_context() -> AuthorityContext:
    return AuthorityContext(
        vault="modelling-knowledge",
        domain_registry="registry/knowledge-domains.yml",
        scope_decision="0005-knowledge-vault-domain-scope",
        knowledge_seam_decision="0009-vault-side-knowledge-seam",
        coordination_decision="0007-memory-promotion-coordination",
        checked_at="2026-07-14T09:00:00+04:00",
        source_index_digest=INDEX_DIGEST,
        accepted_refs=("decisions/0007-memory-promotion-coordination",),
        context_receipt=_receipt(),
        authority_context_digest=CONTEXT_DIGEST,
    )


def _candidate(**overrides: object) -> MemoryCandidate:
    values = {
        "candidate_id": "memcand-20260714-001",
        "claim": (
            "The classify runtime returns a typed transport candidate while "
            "leaving the vault inbox write to modeller-agents."
        ),
        "provenance": {
            "origin_run": "run-20260714-001",
            "source_repository": "modeller-memory",
            "source_commit": "abc123",
            "evidence_refs": ["docs/dev/N2-C1-classify-runtime-plan.md"],
            "durability": "promotion_candidate",
            "scope": "ecosystem",
            "passes_rewrite_test": True,
        },
        "sensitivity": "internal",
        "related_decisions": ("0007-memory-promotion-coordination",),
        "origin_run": "run-20260714-001",
        "confidence": 0.84,
    }
    values.update(overrides)
    return MemoryCandidate(**values)


def test_invalid_authority_context_flags_never_inbox() -> None:
    bad_ctx = AuthorityContext(
        vault="modelling-knowledge",
        domain_registry="",
        scope_decision="0005-knowledge-vault-domain-scope",
        knowledge_seam_decision="0009-vault-side-knowledge-seam",
        coordination_decision="0007-memory-promotion-coordination",
        checked_at="2026-07-14T09:00:00+04:00",
        source_index_digest="sha256:old",
        accepted_refs=("decisions/0007-memory-promotion-coordination",),
        context_receipt=None,
    )

    result = classify(_candidate(), bad_ctx, current_index_digest=INDEX_DIGEST)

    assert result.target == "flag"
    assert result.classification == "authority-context-invalid"
    assert result.target != "vault-inbox"
    assert result.provenance["authority_context_errors"]


def test_missing_context_receipt_flags_never_inbox() -> None:
    ctx = _authority_context()
    result = classify(
        _candidate(),
        AuthorityContext(
            vault=ctx.vault,
            domain_registry=ctx.domain_registry,
            scope_decision=ctx.scope_decision,
            knowledge_seam_decision=ctx.knowledge_seam_decision,
            coordination_decision=ctx.coordination_decision,
            checked_at=ctx.checked_at,
            source_index_digest=ctx.source_index_digest,
            accepted_refs=ctx.accepted_refs,
            authority_context_digest=ctx.authority_context_digest,
        ),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "flag"
    assert result.target != "vault-inbox"
    assert "context_receipt" in " ".join(
        result.provenance["authority_context_errors"]
    )


def test_stale_context_receipt_digest_flags_never_inbox() -> None:
    stale_receipt = ContextReceipt(
        retrieval_query="classify durable modelling observation",
        searched_domains=("transport",),
        candidate_note_refs=("domains/transport/memory-promotion.md",),
        selected_note_refs=("decisions/0007-memory-promotion-coordination",),
        excluded_note_refs={},
        algorithm_version="context-retrieval/1",
        budget=10,
        ranking=("decisions/0007-memory-promotion-coordination",),
        permissions=("internal",),
        receipt_digest="sha256:receipt",
        authority_context_digest="sha256:old-context",
    )
    result = classify(
        _candidate(),
        _authority_context(),
        context_receipt=stale_receipt,
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "flag"
    assert result.target != "vault-inbox"
    assert "stale" in " ".join(result.provenance["authority_context_errors"])


def test_stale_index_digest_flags_never_inbox() -> None:
    result = classify(
        _candidate(),
        _authority_context(),
        current_index_digest="sha256:new-index",
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "flag"
    assert result.target != "vault-inbox"
    assert "source_index_digest" in " ".join(
        result.provenance["authority_context_errors"]
    )


def test_contradiction_flags_with_conflicting_ref() -> None:
    result = classify(
        _candidate(contradictions=("decisions/0007-memory-promotion-coordination",)),
        _authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "flag"
    assert result.classification == "contradiction"
    assert result.conflicting_ref == "decisions/0007-memory-promotion-coordination"


def test_ephemeral_recommends_companion() -> None:
    candidate = _candidate(
        provenance={
            "origin_run": "run-20260714-001",
            "source_repository": "modeller-memory",
            "durability": "ephemeral",
            "scope": "run",
            "passes_rewrite_test": False,
        }
    )

    result = classify(candidate, _authority_context(), current_index_digest=INDEX_DIGEST)

    assert result.target == "companion"
    assert result.classification == "ephemeral"


def test_durable_no_conflict_recommends_vault_inbox() -> None:
    result = classify(
        _candidate(),
        _authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "vault-inbox"
    assert result.classification == "durable-candidate"


def test_context_receipt_can_be_passed_explicitly() -> None:
    ctx = _authority_context()
    ctx_without_receipt = AuthorityContext(
        vault=ctx.vault,
        domain_registry=ctx.domain_registry,
        scope_decision=ctx.scope_decision,
        knowledge_seam_decision=ctx.knowledge_seam_decision,
        coordination_decision=ctx.coordination_decision,
        checked_at=ctx.checked_at,
        source_index_digest=ctx.source_index_digest,
        accepted_refs=ctx.accepted_refs,
        authority_context_digest=ctx.authority_context_digest,
    )

    result = classify(
        _candidate(),
        ctx_without_receipt,
        context_receipt=_receipt(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "vault-inbox"


def test_one_real_candidate_reaches_inbox_valid_draft_without_io() -> None:
    result = classify(
        _candidate(),
        _authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.target == "vault-inbox"
    transport = candidate_to_dict(result)
    _assert_schema_contract(transport)
    assert json.loads(json.dumps(transport, sort_keys=True)) == transport

    draft_front_matter = _to_discovery_draft_front_matter(result)
    required = {
        "title",
        "status",
        "type",
        "owner",
        "source",
        "candidate_id",
        "origin_run",
        "claim",
        "sensitivity",
        "authority_context_refs",
        "related_decisions",
        "captured_from",
    }

    assert required <= draft_front_matter.keys()
    assert draft_front_matter["status"] == "draft"
    assert draft_front_matter["type"] == "discovery-draft"
    assert draft_front_matter["source"] == "modeller-memory"
    assert draft_front_matter["owner"] == "modeller-agents/memory-agent"
    assert "authority_level" not in draft_front_matter


def test_classify_with_ledger_returns_transition_evidence_without_transport_change() -> None:
    candidate = _candidate()

    result = classify_with_ledger(
        candidate,
        _authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
    )

    assert result.candidate.target == "vault-inbox"
    assert result.event.transition == "unclassified:flag->durable-candidate:vault-inbox"
    assert result.event.authority_context_refs == (
        "decisions/0007-memory-promotion-coordination",
    )
    assert result.ledger.events == (result.event,)

    transport = candidate_to_dict(result.candidate)
    assert "ledger" not in transport
    assert "event" not in transport


def test_classify_with_ledger_appends_to_existing_chain() -> None:
    first = classify_with_ledger(
        _candidate(candidate_id="memcand-20260714-001"),
        _authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
        timestamp="2026-07-14T09:15:00+04:00",
        actor="tests/candidate",
        source="unit-test",
    )

    second = classify_with_ledger(
        _candidate(
            candidate_id="memcand-20260714-002",
            provenance={
                "origin_run": "run-20260714-002",
                "source_repository": "modeller-memory",
                "durability": "ephemeral",
                "scope": "run",
                "passes_rewrite_test": False,
            },
        ),
        _authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
        timestamp="2026-07-14T09:16:00+04:00",
        actor="tests/candidate",
        source="unit-test",
        ledger=first.ledger,
    )

    assert isinstance(first.ledger, CandidateEventLedger)
    assert len(second.ledger.events) == 2
    assert second.event.previous_digest == first.event.digest
    assert second.candidate.target == "companion"


def _assert_schema_contract(candidate: dict[str, object]) -> None:
    schema = json.loads((ROOT / "schemas" / "memory-candidate.schema.json").read_text())
    assert set(schema["required"]) <= candidate.keys()
    assert candidate["target"] in schema["properties"]["target"]["enum"]
    assert candidate["sensitivity"] in schema["properties"]["sensitivity"]["enum"]
    assert 0 <= candidate["confidence"] <= 1


def _to_discovery_draft_front_matter(candidate: MemoryCandidate) -> dict[str, object]:
    return {
        "title": candidate.claim[:72],
        "status": "draft",
        "type": "discovery-draft",
        "owner": "modeller-agents/memory-agent",
        "source": "modeller-memory",
        "candidate_id": candidate.candidate_id,
        "origin_run": candidate.origin_run,
        "claim": candidate.claim,
        "sensitivity": candidate.sensitivity,
        "authority_context_refs": list(candidate.authority_context_refs),
        "related_decisions": list(candidate.related_decisions),
        "captured_from": candidate.provenance.get("evidence_refs", []),
    }
