# Memory schemas

JSON Schemas backing the contracts in `../docs/contracts/`. **Status:** the
`memory-candidate.schema.json` contract is implemented for the Phase 1 classify runtime; the
other schemas remain planned M0 deliverables from the revised build sequence
(`../docs/INTEGRATION_PLAN.md` §7).

| Schema | Backs | Plan section |
|---|---|---|
| `memory-manifest.schema.json` | `memory-manifest.json` (version, generated_at, repo_commit, index paths, sources) | §5, §6a |
| `memory-record.schema.json` | Multi-axis companion record (kind × scope × durability × authority × status × provenance × sensitivity × temporal) | §6.1 |
| `memory-candidate.schema.json` | `MemoryCandidate` transport contract (the propose→transport seam) | §3.1a, ADR-0004 |
| `memory-health.schema.json` | `memory_state` freshness block + doctor/readiness output | §6a, §6d |
| `index-scope.schema.json` | `index-scope.yml` include/exclude/subtree-roles | §6c |

Note: the multi-axis `memory-record` model replaces the earlier flat
`decision / project / calibration-fact / reference` list (antagonist finding AM-09).
