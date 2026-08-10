from __future__ import annotations

import pytest

from modeller_memory import (
    CompanionRecord,
    InMemoryMemoryProvider,
    MemoryProvider,
    MemoryScope,
)


def _record(**overrides: object) -> CompanionRecord:
    values = {
        "record_id": "memrec-20260714-001",
        "text": "Pipeline import used a temporary lane matching workaround.",
        "kind": "observation",
        "scope": MemoryScope(
            tenant_id="aitlantis",
            project_id="demo-project",
            repository_id="modeller-memory",
            run_id="run-20260714-001",
        ),
        "durability": "checkpoint",
        "authority": "generated",
        "status": "active",
        "provenance": {
            "origin_run": "run-20260714-001",
            "source_repository": "modeller-memory",
        },
        "sensitivity": "internal",
        "created_at": "2026-07-14T09:20:00+04:00",
        "tags": ("lane-matching",),
    }
    values.update(overrides)
    return CompanionRecord(**values)


def test_in_memory_provider_satisfies_memory_provider_protocol() -> None:
    provider: MemoryProvider = InMemoryMemoryProvider()

    record = provider.put(_record())

    assert provider.get(
        record.record_id,
        scope=MemoryScope(project_id="demo-project"),
    ) == record


def test_search_requires_explicit_scope() -> None:
    provider = InMemoryMemoryProvider()
    provider.put(_record())

    assert provider.search("lane", scope=MemoryScope()) == ()
    assert provider.get("memrec-20260714-001", scope=MemoryScope()) is None


def test_search_filters_by_scope_and_sensitivity() -> None:
    provider = InMemoryMemoryProvider()
    internal = provider.put(_record())
    restricted = provider.put(
        _record(
            record_id="memrec-20260714-002",
            text="Restricted calibration token should not leak.",
            sensitivity="restricted",
            tags=("calibration",),
        )
    )
    provider.put(
        _record(
            record_id="memrec-20260714-003",
            text="Different project lane matching note.",
            scope=MemoryScope(
                tenant_id="aitlantis",
                project_id="other-project",
                repository_id="modeller-memory",
            ),
        )
    )

    assert provider.search("lane", scope=MemoryScope(project_id="demo-project")) == (
        internal,
    )
    assert provider.search(
        "calibration",
        scope=MemoryScope(project_id="demo-project"),
    ) == ()
    assert provider.search(
        "calibration",
        scope=MemoryScope(project_id="demo-project"),
        allowed_sensitivity=("public", "internal", "restricted"),
    ) == (restricted,)


def test_records_must_have_explicit_scope() -> None:
    with pytest.raises(ValueError, match="scope"):
        _record(scope=MemoryScope())


def test_provider_does_not_auto_promote_records() -> None:
    provider = InMemoryMemoryProvider()
    record = provider.put(
        _record(durability="promotion_candidate", tags=("promotion",))
    )

    assert record.status == "active"
    assert record.promoted_ref is None
    assert provider.search(
        "promotion",
        scope=MemoryScope(project_id="demo-project"),
    ) == (record,)


def test_replace_status_can_update_inactive_record_within_scope_only() -> None:
    provider = InMemoryMemoryProvider()
    provider.put(_record(status="contradicted"))

    blocked = provider.replace_status(
        "memrec-20260714-001",
        status="rejected",
        scope=MemoryScope(project_id="other-project"),
    )
    updated = provider.replace_status(
        "memrec-20260714-001",
        status="rejected",
        scope=MemoryScope(project_id="demo-project"),
    )

    assert blocked is None
    assert updated is not None
    assert updated.status == "rejected"
    assert provider.get(
        "memrec-20260714-001",
        scope=MemoryScope(project_id="demo-project"),
    ) is None
