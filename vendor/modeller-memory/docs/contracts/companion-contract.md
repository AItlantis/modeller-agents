# Companion Memory Contract

Status: scoped scaffold implemented; persistent storage and standing recall deferred.

Companion memory is generated context only. It is not accepted knowledge, cannot
promote itself, and must not write to the vault.

## Runtime Entrypoints

- `MemoryProvider` protocol
- `MemoryScope`
- `CompanionRecord`
- `InMemoryMemoryProvider`

The provider is explicitly caller-instantiated. Importing `modeller_memory` does
not create a store, load records, or enable recall.

## Scope Rules

Retrieval requires an explicit `MemoryScope` containing at least one boundary:
`tenant_id`, `project_id`, `repository_id`, `session_id`, or `run_id`. A blank
scope returns no records. A scoped query only returns records inside the caller's
declared boundary and inside the caller's `allowed_sensitivity` tuple.

## Non-Authority Rules

- Records carry local context fields only: `kind`, `scope`, `durability`,
  `authority`, `status`, `provenance`, `sensitivity`, and timestamps.
- The implemented provider is process-local and in-memory.
- There is no automatic accepted-knowledge promotion.
- There is no vault read/write path and no dependency on `vault_doctor`.
- JSONL or backend adapters are deferred and must keep the same scoped,
  non-authoritative behavior.
