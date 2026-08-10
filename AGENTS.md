---
title: Agent Instructions
status: active
type: context
owner: modeller-memory
authority_level: supporting
---

# Agent Instructions

## What This Is

`modeller-memory` is the embeddable, **generated, non-authoritative** memory
subsystem for the modelling ecosystem. Today it implements a candidate
classification runtime (propose a `MemoryCandidate` from an observation) and a
scoped in-memory companion-recall scaffold. Repository intelligence (a code
graph) is planned, not built. `modeller-agents` vendors this repo as a pinned,
read-only contract; it does not modify it in place.

**The non-authority principle (ADR-0001).** Git is the single source of truth.
Every layer this repo produces is a generated index sitting at authority tier 4
(source repo/Git, then curated knowledge in `modelling-knowledge`, then the
generated code graph, then companion memory, in that order). On any
disagreement between this repo's output and the repository or the vault, this
repo is wrong: its output is corrected, ignored, or regenerated. Never trust
generated memory over source or over accepted knowledge.

## Boundary (damage-preventing — read before writing runtime code)

Allowed:

- classify an observation into a typed `MemoryCandidate` and return it;
- implement repository intelligence (code graph, freshness) once built;
- implement scoped, explicit-scope companion recall.

Forbidden:

- **No vault I/O, ever.** The runtime under `src/modeller_memory/` (excluding
  `tools/vault_doctor/`) must never read or write the `modelling-knowledge`
  vault. This is machine-enforced: `tests/test_import_guards.py` fails the
  build if any runtime module so much as imports or names `vault_doctor`
  (ADR-0005, cross-repo finding N-3). `vault_doctor` itself is a co-located,
  orthogonal, read-only vault validator/exporter — not a memory layer.
- **Never transport.** This repo classifies an observation and returns a typed
  `MemoryCandidate` (`docs/contracts/candidate-contract.md`). It never writes
  an inbox draft. `modeller-agents` transports (validates the destination,
  performs the write); `modelling-knowledge` governs (accepts or rejects).
  See ADR-0004.
- **Skills are not owned here.** Executable skills for the ecosystem
  (`memory-recon`, `memory-maintain`) live in `modeller-agents`
  (`../modeller-agents/`, ADR-0002). Status: emerging, indexed in that repo's
  `docs/skills/modeller/SKILL_INDEX.md` but not yet installable; distinct from
  `testudo:memory-recon`/`memory-maintain` (Testudo-local) and
  `aimsun-psp-orchestrator:psp-memory-recon`/`psp-memory-maintain` (PSP-scoped),
  which are different plugins sharing similar short names: always qualify.
  The `skills/document-knowledge-acquisition/` folder in this
  repo is local, repo-scoped tooling support (DRIEAT-style document import),
  not a central/shared skill: do not treat it as the memory-recon/maintain
  seam or copy it elsewhere.
- **No unscoped companion recall.** `InMemoryMemoryProvider` retrieval needs
  an explicit `MemoryScope`; a blank scope returns no results, never a global
  search. See `docs/contracts/companion-contract.md` and ADR-0003.

## Start Here

1. Read `README.md`.
2. Read `docs/vision/Vision.md`, `docs/vision/Business-need-design-brief.md`, and `docs/vision/Product-requirements-document.md` for strategic direction.
3. Read the relevant ADR under `docs/ADR/` before changing behavior it governs.
4. Read `docs/contracts/` before changing the runtime API.

## Routing Table

| Need | Go to |
|---|---|
| Strategic direction | `docs/vision/Vision.md`, `docs/vision/Business-need-design-brief.md`, `docs/vision/Product-requirements-document.md` |
| Runtime API authority | `docs/contracts/` (`candidate-contract.md` implemented; `companion-contract.md` covers the in-memory scaffold only) |
| Ratified decisions | `docs/ADR/` (ADR-0001 non-authority, ADR-0002 skill ownership, ADR-0003 companion isolation, ADR-0004 promotion seam, ADR-0005 vault_doctor co-location) |
| Milestones, cross-repo status, product statement | `docs/INTEGRATION_PLAN.md` (M0-M7; treat dated status notes as current truth over older prose in the same file) |
| Historical build record (classify runtime) | `docs/dev/N2-C1-classify-runtime-plan.md` — "why is it built this way," not a live contract |
| Ecosystem-level routing for non-trivial or ambiguous tasks | `modelling-orchestrator:modelling-orchestrator` (`../.skills/modelling-orchestrator`); this repo is consumed by `modeller-agents` as a pinned contract, not dispatched to directly |

## Repository Layout

- `src/modeller_memory/` - runtime (classification, companion recall scaffold); `tools/vault_doctor/` is the sole exception to the no-vault-I/O rule.
- `docs/vision/` - strategic vision, business-need, and PRD documents.
- `docs/contracts/` - runtime API authority (candidate, companion contracts).
- `docs/ADR/` - ratified architectural decisions.
- `docs/INTEGRATION_PLAN.md` - milestones and cross-repo status.
- `schemas/` - machine-readable schemas backing the contracts.
- `skills/document-knowledge-acquisition/` - repo-local document-corpus ingestion helper (DOCX/PDF report sets to Markdown, evidence matrices, discovery drafts staged for `modelling-knowledge`), plus a `drieat_import` CLI it documents. Not an ecosystem-shared skill.
- `tests/` - including `test_import_guards.py`, the machine-enforced vault-I/O boundary.
