# ADR-0004 — Vault promotion seam (propose / transport / govern)

**Status:** accepted
**Date:** 2026-07-11
**Owner:** `modeller-memory` (in coordination with `modeller-agents`, `modelling-knowledge`)
**Related:** `docs/INTEGRATION_PLAN.md` §3.1a, §3.2; antagonist findings AM-01, AM-02;
`modelling-knowledge/decisions/0007-memory-promotion-coordination.md`;
`modelling-knowledge` vault-optimisation-plan Phase H

## Context

The earlier plan contained two contradictions:

- **AM-01:** it said memory has *no write path* to `modelling-knowledge` but then authorised the
  memory subsystem to draft into the vault inbox.
- **AM-02:** it required memory to *discard/flag a candidate that contradicts a vault note* while
  also stating memory has *no read path* to the vault — an impossible operation.

Both stem from conflating the memory *subsystem* with the memory *agent*.

## Decision

1. **Separate subsystem from agent.**
   - `modeller-memory` **proposes**: it classifies a candidate and returns a typed `MemoryCandidate`.
     It reads and writes **nothing** in the vault.
   - `modeller-agents` (the memory agent, owned there per ADR-0002/decision 0001) **transports**: it
     validates the destination and performs the actual inbox write.
   - `modelling-knowledge` **governs**: antagonist review accepts a discovery draft into the inbox
     lifecycle. Acceptance authority is the board's alone.
2. **`MemoryCandidate` transport contract** (`schemas/memory-candidate.schema.json`):
   `candidate_id`, `classification`, `claim`, `provenance` (evidence refs), `sensitivity`, `target`
   (`vault-inbox | companion | discard | flag`), `confidence`, `related_decisions`, `origin_run`.
3. **Conflict detection uses an `authority_context`, not a vault read (AM-02).** The orchestrator
   retrieves accepted knowledge *before* querying memory (baseline-flow step 5 precedes step 6) and
   passes the relevant accepted-knowledge references, source-repository commit, and applicable
   decisions into classification. Memory judges contradiction against that supplied context. A future
   optimisation may allow memory to read the vault's **metadata-only index**, but that is not
   required for v1 and is not a general vault-retrieval capability.
4. **Promotion compacts, does not delete (AM-09).** On acceptance, the companion record becomes a
   lightweight promotion pointer (`status: promoted`, `promoted_to: {note_id, note_path,
   decision_id}`); the accepted vault note is the authority, the pointer preserves the audit trail.
5. **Eligibility inherits accepted decision 0005 (AM-10).** A candidate is vault-eligible only if it
   passes 0005's from-scratch-rewrite test. Content promotion through the memory seam remains gated
   by decision 0007's live `MemoryCandidate` exercise and general N-2 authority-context proof.

## Consequences

- The subsystem's write scope is its own companion store and generated indexes only.
- The rule "memory proposes; modeller-agents transports; modelling-knowledge governs" is the single
  statement of the seam, mirrored in vault decision 0007.
- The impossible conflict operation is removed and replaced by authority-context resolution.
