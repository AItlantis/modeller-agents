# Memory contracts

`modeller-memory` owns *what memory operations mean and how they execute*. The executable skills
that call these contracts are owned by `modeller-agents` (see `docs/ADR/ADR-0002-skill-ownership.md`).

**Status:** `candidate-contract.md` is implemented for the Phase 1 classify runtime.
`companion-contract.md` is implemented only as a scoped in-memory scaffold; persistent
storage and standing recall remain deferred. The other contracts remain planned M0
deliverables from the revised build sequence (`docs/INTEGRATION_PLAN.md` section 7).

| Contract | Defines | Plan section |
|---|---|---|
| `query-contract.md` | Structural retrieval over the code graph; every result stamped with a freshness state | section 5, section 6a |
| `candidate-contract.md` | `classify(candidate, authority_context) -> MemoryCandidate`; candidate ledger evidence | section 3.1a, section 3.2 |
| `companion-contract.md` | Explicitly scoped, non-authoritative companion provider scaffold | section 6.1, section 6.2 |
| `health-contract.md` | Health/readiness levels (`HEALTHY...UNSAFE`); `safe_to_query` / `safe_to_write` | section 6d |
| `manifest-contract.md` | `memory-manifest.json` shape; staleness = repo-commit SHA; re-index modes | section 5, section 6a |
| `index-scope-contract.md` | Include/exclude policy, subtree roles, project-id derivation, rename detection | section 6c |

The matching JSON schemas live under `../../schemas/`.
