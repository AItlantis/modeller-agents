from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from modeller_memory.candidate.model import Sensitivity


MemoryKind = Literal[
    "decision",
    "observation",
    "assumption",
    "preference",
    "issue",
    "result",
    "reference",
    "candidate",
]
MemoryDurability = Literal[
    "ephemeral",
    "checkpoint",
    "retained",
    "promotion_candidate",
]
MemoryAuthority = Literal[
    "generated",
    "user_asserted",
    "source_verified",
    "accepted_knowledge_reference",
]
MemoryStatus = Literal[
    "active",
    "contradicted",
    "superseded",
    "expired",
    "promoted",
    "rejected",
]


@dataclass(frozen=True)
class MemoryScope:
    """Explicit retrieval boundary for non-authoritative companion memory."""

    tenant_id: str | None = None
    project_id: str | None = None
    repository_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None

    @property
    def is_explicit(self) -> bool:
        return any(
            _has_text(value)
            for value in (
                self.tenant_id,
                self.project_id,
                self.repository_id,
                self.session_id,
                self.run_id,
            )
        )

    def contains(self, other: MemoryScope) -> bool:
        if not self.is_explicit:
            return False
        for field_name in (
            "tenant_id",
            "project_id",
            "repository_id",
            "session_id",
            "run_id",
        ):
            expected = getattr(self, field_name)
            actual = getattr(other, field_name)
            if expected is not None and expected != actual:
                return False
        return True


@dataclass(frozen=True)
class CompanionRecord:
    """Local companion-memory record.

    These records are generated context only. They are never accepted knowledge
    and this provider does not write vault drafts or promote records.
    """

    record_id: str
    text: str
    kind: MemoryKind
    scope: MemoryScope
    durability: MemoryDurability
    authority: MemoryAuthority
    status: MemoryStatus
    provenance: dict[str, Any]
    sensitivity: Sensitivity
    created_at: str
    tags: tuple[str, ...] = ()
    promoted_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("record_id", "text", "kind", "created_at"):
            _require_text(getattr(self, field_name), field_name)
        if not self.scope.is_explicit:
            raise ValueError("scope must include at least one explicit boundary")
        object.__setattr__(self, "tags", _tuple_of_text(self.tags, "tags"))
        if self.promoted_ref is not None:
            _require_text(self.promoted_ref, "promoted_ref")


class MemoryProvider(Protocol):
    """Scoped, non-authoritative companion memory interface."""

    def put(self, record: CompanionRecord) -> CompanionRecord:
        """Store or replace a generated companion record."""

    def get(
        self,
        record_id: str,
        *,
        scope: MemoryScope,
        allowed_sensitivity: tuple[Sensitivity, ...] = ("public", "internal"),
    ) -> CompanionRecord | None:
        """Return one record if it is inside the explicit caller scope."""

    def search(
        self,
        query: str,
        *,
        scope: MemoryScope,
        allowed_sensitivity: tuple[Sensitivity, ...] = ("public", "internal"),
        limit: int = 20,
    ) -> tuple[CompanionRecord, ...]:
        """Return scoped generated-context matches."""


@dataclass
class InMemoryMemoryProvider:
    """Explicitly instantiated, process-local companion memory provider."""

    _records: dict[str, CompanionRecord] = field(default_factory=dict)

    def put(self, record: CompanionRecord) -> CompanionRecord:
        self._records[record.record_id] = record
        return record

    def get(
        self,
        record_id: str,
        *,
        scope: MemoryScope,
        allowed_sensitivity: tuple[Sensitivity, ...] = ("public", "internal"),
    ) -> CompanionRecord | None:
        record = self._records.get(record_id)
        if record is None or not _visible(record, scope, allowed_sensitivity):
            return None
        return record

    def search(
        self,
        query: str,
        *,
        scope: MemoryScope,
        allowed_sensitivity: tuple[Sensitivity, ...] = ("public", "internal"),
        limit: int = 20,
    ) -> tuple[CompanionRecord, ...]:
        if limit <= 0 or not _has_text(query) or not scope.is_explicit:
            return ()
        needle = query.casefold()
        matches: list[CompanionRecord] = []
        for record in self._records.values():
            if not _visible(record, scope, allowed_sensitivity):
                continue
            if needle in record.text.casefold() or any(
                needle in tag.casefold() for tag in record.tags
            ):
                matches.append(record)
                if len(matches) >= limit:
                    break
        return tuple(matches)

    def replace_status(
        self,
        record_id: str,
        *,
        status: MemoryStatus,
        scope: MemoryScope,
    ) -> CompanionRecord | None:
        record = self._records.get(record_id)
        if record is None or not _in_scope(record, scope):
            return None
        updated = replace(record, status=status)
        self._records[record_id] = updated
        return updated


def _visible(
    record: CompanionRecord,
    scope: MemoryScope,
    allowed_sensitivity: tuple[Sensitivity, ...],
) -> bool:
    return (
        _in_scope(record, scope)
        and record.sensitivity in allowed_sensitivity
        and record.status == "active"
    )


def _in_scope(record: CompanionRecord, scope: MemoryScope) -> bool:
    return scope.contains(record.scope)


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _tuple_of_text(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _require_text(value, field_name)
    return result
