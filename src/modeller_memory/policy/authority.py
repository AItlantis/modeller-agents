from __future__ import annotations

from collections.abc import Iterable

from modeller_memory.candidate.model import AuthorityContext, ContextReceipt, Result


PINNED_VAULT = "modelling-knowledge"

REQUIRED_AUTHORITY_FIELDS = (
    "vault",
    "domain_registry",
    "scope_decision",
    "knowledge_seam_decision",
    "coordination_decision",
    "checked_at",
    "source_index_digest",
)

REQUIRED_RECEIPT_FIELDS = (
    "retrieval_query",
    "searched_domains",
    "candidate_note_refs",
    "selected_note_refs",
    "algorithm_version",
    "budget",
    "ranking",
    "permissions",
    "receipt_digest",
)


def validate_authority_context(
    ctx: AuthorityContext,
    *,
    current_index_digest: str,
    current_authority_context_digest: str | None = None,
) -> Result:
    """Validate completeness and currency of caller-supplied authority context."""

    errors: list[str] = []
    warnings: list[str] = []

    for field_name in REQUIRED_AUTHORITY_FIELDS:
        value = getattr(ctx, field_name)
        if not _non_empty_string(value):
            errors.append(f"authority_context.{field_name} must be a non-empty string")

    if ctx.vault != PINNED_VAULT:
        errors.append(f"authority_context.vault must be '{PINNED_VAULT}'")

    if not _non_empty_string(current_index_digest):
        errors.append("current_index_digest must be a non-empty string")
    elif ctx.source_index_digest != current_index_digest:
        errors.append(
            "authority_context is stale: source_index_digest does not match "
            "current_index_digest"
        )

    if not isinstance(ctx.accepted_refs, tuple):
        errors.append("authority_context.accepted_refs must be a tuple")
    elif not ctx.accepted_refs:
        warnings.append("conflict check ran against zero accepted references")

    receipt_result = validate_context_receipt(
        ctx.context_receipt,
        current_authority_context_digest=current_authority_context_digest,
        expected_selected_refs=ctx.accepted_refs,
    )
    errors.extend(receipt_result.errors)
    warnings.extend(receipt_result.warnings)

    if (
        ctx.authority_context_digest
        and ctx.context_receipt is not None
        and not ctx.context_receipt.authority_context_digest
    ):
        errors.append(
            "context_receipt.authority_context_digest is required when "
            "authority_context.authority_context_digest is set"
        )
    elif (
        ctx.authority_context_digest
        and ctx.context_receipt is not None
        and ctx.context_receipt.authority_context_digest
        and ctx.authority_context_digest != ctx.context_receipt.authority_context_digest
    ):
        errors.append(
            "authority_context.authority_context_digest must match "
            "context_receipt.authority_context_digest"
        )

    return Result(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def validate_context_receipt(
    receipt: ContextReceipt | None,
    *,
    current_authority_context_digest: str | None = None,
    expected_selected_refs: Iterable[str] = (),
) -> Result:
    """Validate that selected authority context is complete and current."""

    if receipt is None:
        return Result(
            ok=False,
            errors=("authority_context.context_receipt is required",),
        )

    errors: list[str] = []
    warnings: list[str] = []
    for field_name in REQUIRED_RECEIPT_FIELDS:
        value = getattr(receipt, field_name)
        if isinstance(value, str):
            if not value.strip():
                errors.append(f"context_receipt.{field_name} must be non-empty")
        elif isinstance(value, tuple):
            if not value:
                errors.append(f"context_receipt.{field_name} must be non-empty")
        elif isinstance(value, int):
            if value <= 0:
                errors.append(f"context_receipt.{field_name} must be positive")
        else:
            errors.append(f"context_receipt.{field_name} has an invalid type")

    if not isinstance(receipt.excluded_note_refs, dict):
        errors.append("context_receipt.excluded_note_refs must be a dict")

    expected = tuple(expected_selected_refs)
    if expected and set(receipt.selected_note_refs) != set(expected):
        errors.append(
            "context_receipt.selected_note_refs must match "
            "authority_context.accepted_refs"
        )

    if current_authority_context_digest is not None:
        if not receipt.authority_context_digest:
            errors.append("context_receipt.authority_context_digest is required")
        elif receipt.authority_context_digest != current_authority_context_digest:
            errors.append(
                "authority context is stale: context digest does not match current "
                "authority context digest"
            )
    elif not receipt.authority_context_digest:
        warnings.append("context receipt does not carry an authority context digest")

    return Result(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
