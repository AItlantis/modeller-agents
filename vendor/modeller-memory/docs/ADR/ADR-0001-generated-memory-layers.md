# ADR-0001 — Generated memory layers, non-authoritative

**Status:** accepted (ports Testudo ADR-0002 into `modeller-memory`)
**Date:** 2026-07-11
**Owner:** `modeller-memory`
**Related:** `docs/INTEGRATION_PLAN.md` §1, §2, §3.2, §6a

## Context

`modeller-memory` packages generated indexes over a host repository. The single most important
operational lesson from Testudo is that a memory layer must never become an authority and must
never make a session fail.

## Decision

1. **Git is the single source of truth.** Every memory layer is a *generated, non-authoritative
   index*. On any graph-vs-repo disagreement, the repository wins and the index is regenerated.
2. **Two layers, not three.** The subsystem provides (a) repository intelligence (code graph) and
   (b) scoped companion recall. Reuse-first guardrails are **not** a memory layer (see ADR-0002).
3. **Authority ladder** (tier order, highest first): source repo/Git → curated knowledge in
   `modelling-knowledge` → generated code graph → companion memory. Query order (efficiency) is a
   separate list from authority order (who wins on disagreement).
4. **Freshness is a gate, not a label.** Graph results are trusted only after a manifest-commit
   freshness check (`fresh | stale | unavailable | incompatible`); stale graphs are advisory and
   a source read is mandatory before any conclusion. The graph is a navigational aid, never final
   authority.
5. **Reachability-first, never-block.** Probe once at session start; degrade cleanly to grep/read;
   distinguish healthy degradation from unsafe degradation (see ADR/plan §6d).

## Consequences

- Companion recall is strictly tier 4 and never truth.
- v1 ships a repository-structural (code-graph) index only; no generated "docs index" (plan §6a,
  AM-07). Markdown/accepted knowledge is read directly through `modeller-agents`.
- The subsystem never writes to `modelling-knowledge` and never holds the memory agent (ADR-0004).
