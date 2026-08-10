# Candidate Contract

Status: implemented, Phase 1 memory-runtime slice.

`modeller-memory` owns the propose side of memory promotion. It classifies a
caller-supplied observation into a typed `MemoryCandidate` and returns that
object. It does not transport the candidate, validate a destination path, write
an inbox draft, or accept knowledge.

## Runtime Entrypoints

- `validate_authority_context(ctx, *, current_index_digest, current_authority_context_digest=None) -> Result`
- `classify(candidate, authority_context, *, context_receipt=None, current_index_digest, current_authority_context_digest=None) -> MemoryCandidate`
- `classify_with_ledger(candidate, authority_context, *, timestamp, actor, source, ...) -> ClassificationLedgerResult`
- `record_candidate_transition(before, after, *, timestamp, actor, source, ...) -> CandidateLedgerEvent`
- `CandidateEventLedger().append_transition(before, after, *, timestamp, actor, source, ...) -> CandidateEventLedger`

The caller supplies the `AuthorityContext`, its `ContextReceipt` either embedded
in that context or passed as `context_receipt`, and the current digest inputs.
The runtime only compares strings already passed in; it does not read the vault.

## AuthorityContext

Required authority fields:

- `vault`, pinned to `modelling-knowledge`
- `domain_registry`
- `scope_decision`
- `knowledge_seam_decision`
- `coordination_decision`
- `checked_at`
- `source_index_digest`
- `context_receipt`

`accepted_refs` may be empty, but that is low assurance and produces a warning.

## ContextReceipt

The receipt proves selection, not just currency. It records:

- retrieval query
- searched domains
- candidate notes
- selected notes
- excluded notes and reasons
- algorithm version
- budget
- ranking
- permissions
- receipt digest
- optional authority-context digest

If a current authority-context digest is supplied to classification, the receipt
must carry the matching digest. Mismatches are stale context.

## Routing Rules

- Incomplete authority context: `target="flag"`.
- Stale index digest or authority-context digest: `target="flag"`.
- Contradiction evidence: `target="flag"` with `conflicting_ref`; contradictions
  are never auto-discarded.
- Ephemeral or run/session scoped content: `target="companion"`.
- Durable promotion candidates with `passes_rewrite_test=True`: `target="vault-inbox"`.
- Anything else: `target="flag"`.

`target="vault-inbox"` is a recommendation to the transport owner. This repo
stops at returning the candidate object.

## MemoryCandidate

Machine schema: `schemas/memory-candidate.schema.json`.

Required fields:

- `candidate_id`
- `classification`
- `claim`
- `provenance`
- `sensitivity`
- `target`
- `confidence`
- `related_decisions`
- `origin_run`

Optional fields include `conflicting_ref`, `authority_context_refs`,
`reason_codes`, and `contradictions`.

## Candidate Event Ledger

The candidate ledger records append-only `MemoryCandidate` state transitions as
JSONL-friendly value objects. It is an in-memory/runtime contract only: it does
not read or write the vault, open files, or depend on `vault_doctor`.

Each `CandidateLedgerEvent` records:

- `candidate_id`
- `transition` and resulting `state`
- resulting `target` and `classification`
- `timestamp`, `actor`, and `source`
- optional `reason`
- `reason_codes`, `evidence_refs`, and `authority_context_refs`
- `previous_digest` and `digest`

`CandidateEventLedger` is immutable. `append()` and `append_transition()` return
a new ledger and validate that each event's `previous_digest` matches the prior
event digest. `classify_with_ledger()` is the opt-in classify-flow helper for
callers that need this evidence while preserving `classify() -> MemoryCandidate`.
`event_to_json_line()` / `event_from_json_line()` provide the JSONL codec;
persistence belongs to the caller's storage boundary.
