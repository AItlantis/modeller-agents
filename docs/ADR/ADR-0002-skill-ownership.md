# ADR-0002 — Skill ownership and guardrail placement

**Status:** accepted
**Date:** 2026-07-11
**Owner:** `modeller-memory` (in coordination with `modeller-agents`)
**Related:** `docs/INTEGRATION_PLAN.md` §3.1a, §5, §6.4; antagonist findings AM-03, AM-04, AM-06;
`modelling-knowledge/decisions/0001-local-agents-central-skills.md`

## Context

The earlier plan created two ownership conflicts: it said `memory-recon`/`memory-maintain` would
become "packaged in this repo" while also stating executable reusable skills are centrally owned by
`modeller-agents`; and it packaged `ponytail`-style reuse guardrails as a memory layer. Both are
ownership errors — two repositories claiming one skill, and an agent-behaviour system mislabelled as
memory storage.

## Decision

1. **Executable skills are owned by `modeller-agents`.** `memory-recon` and `memory-maintain` live
   under `modeller-agents/.claude/plugins/modeller/skills/`. `modeller-memory` ships **no** live
   `SKILL.md`. This is consistent with vault decision 0001 (reusable skills are central).
2. **`modeller-memory` owns the technical API and protocol** those skills call —
   `docs/contracts/`, `src/modeller_memory/`, `schemas/`. It defines *what a memory operation means
   and how it executes*, not *how an agent uses it*.
3. **At most, non-executable examples.** This repo may provide `examples/skills/*.reference.md`,
   clearly labelled as examples, never live skill authority. The same `SKILL.md` is never copied
   into two repositories.
4. **Reuse-first guardrails (`ponytail`) are an agent-method concern**, owned by `modeller-agents`
   (`method/guardrails/` or plugin hooks) — not a memory layer. `modeller-memory` may expose reuse
   *queries* (`find_existing_solution`, `find_related_decisions`, `find_previous_implementation`)
   that the guardrail consumes; the reuse *policy* ("does this need to exist / can we reuse / write
   less code") lives in the agent layer.

## Consequences

- One source of truth per skill; no drift between two copies.
- `modeller-memory`'s scope narrows to two memory capabilities plus classification contracts.
- The dedicated memory agent (ADR-0004) is a `modeller-agents`-owned actor invoking the central
  skill, not an actor in this repo.
