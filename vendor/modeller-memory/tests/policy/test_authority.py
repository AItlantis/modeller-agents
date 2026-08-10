from __future__ import annotations

from dataclasses import replace

from modeller_memory import AuthorityContext, ContextReceipt, validate_authority_context


INDEX_DIGEST = "sha256:index-current"
CONTEXT_DIGEST = "sha256:context-current"


def receipt() -> ContextReceipt:
    return ContextReceipt(
        retrieval_query="durable modelling memory promotion",
        searched_domains=("transport",),
        candidate_note_refs=("domains/transport/memory.md",),
        selected_note_refs=("decisions/0007-memory-promotion-coordination",),
        excluded_note_refs={"domains/transport/old.md": "superseded"},
        algorithm_version="context-retrieval/1",
        budget=8,
        ranking=("decisions/0007-memory-promotion-coordination",),
        permissions=("internal",),
        receipt_digest="sha256:receipt",
        authority_context_digest=CONTEXT_DIGEST,
    )


def authority_context() -> AuthorityContext:
    return AuthorityContext(
        vault="modelling-knowledge",
        domain_registry="registry/knowledge-domains.yml",
        scope_decision="0005-knowledge-vault-domain-scope",
        knowledge_seam_decision="0009-vault-side-knowledge-seam",
        coordination_decision="0007-memory-promotion-coordination",
        checked_at="2026-07-14T09:00:00+04:00",
        source_index_digest=INDEX_DIGEST,
        accepted_refs=("decisions/0007-memory-promotion-coordination",),
        source_commit="abc123",
        context_receipt=receipt(),
        authority_context_digest=CONTEXT_DIGEST,
    )


def test_accepts_complete_current_authority_context() -> None:
    result = validate_authority_context(
        authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest=CONTEXT_DIGEST,
    )

    assert result.ok is True
    assert result.errors == ()


def test_rejects_incomplete_authority_context_fields() -> None:
    for field_name in (
        "vault",
        "domain_registry",
        "scope_decision",
        "knowledge_seam_decision",
        "coordination_decision",
        "checked_at",
        "source_index_digest",
    ):
        ctx = replace(authority_context(), **{field_name: ""})

        result = validate_authority_context(
            ctx,
            current_index_digest=INDEX_DIGEST,
            current_authority_context_digest=CONTEXT_DIGEST,
        )

        assert result.ok is False
        assert field_name in " ".join(result.errors)


def test_rejects_missing_receipt() -> None:
    result = validate_authority_context(
        replace(authority_context(), context_receipt=None),
        current_index_digest=INDEX_DIGEST,
    )

    assert result.ok is False
    assert "context_receipt" in " ".join(result.errors)


def test_rejects_wrong_vault_pin() -> None:
    result = validate_authority_context(
        replace(authority_context(), vault="other-vault"),
        current_index_digest=INDEX_DIGEST,
    )

    assert result.ok is False
    assert "modelling-knowledge" in " ".join(result.errors)


def test_rejects_stale_index_digest() -> None:
    result = validate_authority_context(
        replace(authority_context(), source_index_digest="sha256:old"),
        current_index_digest=INDEX_DIGEST,
    )

    assert result.ok is False
    assert "stale" in " ".join(result.errors)


def test_rejects_stale_authority_context_digest() -> None:
    result = validate_authority_context(
        authority_context(),
        current_index_digest=INDEX_DIGEST,
        current_authority_context_digest="sha256:new-context",
    )

    assert result.ok is False
    assert "context digest" in " ".join(result.errors)


def test_rejects_context_and_receipt_digest_mismatch() -> None:
    result = validate_authority_context(
        replace(authority_context(), authority_context_digest="sha256:different"),
        current_index_digest=INDEX_DIGEST,
    )

    assert result.ok is False
    assert "authority_context_digest" in " ".join(result.errors)


def test_rejects_missing_receipt_digest_when_context_digest_is_set() -> None:
    ctx = replace(
        authority_context(),
        context_receipt=replace(receipt(), authority_context_digest=None),
    )

    result = validate_authority_context(ctx, current_index_digest=INDEX_DIGEST)

    assert result.ok is False
    assert "context_receipt.authority_context_digest" in " ".join(result.errors)


def test_empty_accepted_refs_warns_but_passes() -> None:
    empty_receipt = replace(receipt(), selected_note_refs=("note-id",))
    ctx = replace(
        authority_context(),
        accepted_refs=(),
        context_receipt=empty_receipt,
    )

    result = validate_authority_context(ctx, current_index_digest=INDEX_DIGEST)

    assert result.ok is True
    assert result.warnings
