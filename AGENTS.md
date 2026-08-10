---
title: Agent Instructions
status: active
type: context
owner: modeller-pipelines
authority_level: supporting
---

# Agent Instructions

## What This Is

This repository is the **versioned contract surface** for the modeller ecosystem. It defines, in
normative prose and machine-readable JSON Schema, what a pipeline backend must expose and what
`modeller-agents` may expect to consume. It also ships one runnable, copyable template pipeline so
new backend authors have a concrete starting point, and a black-box conformance kit that verifies a
backend's CLI seam without knowing anything about its internals.

## Boundary

Allowed:

- define and version pipeline/step/CLI/result contracts under `contracts/`;
- maintain the copyable `template/` pipeline as an illustrative starting point;
- maintain the `conformance/` black-box test kit.

Forbidden:

- **not a shared runtime framework.** Nothing in the production ecosystem imports this repository at
  runtime — no base classes, no shared runners, no plugin hooks;
- **not a monorepo for backends.** Backend implementations (e.g. `aimsun-psp`) live in their own
  repositories; they reference this repo's schemas via CI fetch or `contract.lock`, not by vendor
  copy;
- **not a Testudo concern.** Testudo is downstream of pipeline outputs; the contracts here define
  what a pipeline runner produces, not how Testudo consumes it;
- treat `template/` as normative — if a template pattern and a contract rule conflict, the contract
  wins, always.

## Start Here

1. Read `README.md`.
2. Read `docs/vision/Vision.md`, `docs/vision/Business-need-design-brief.md`, and `docs/vision/Product-requirements-document.md` for strategic direction.
3. Read the relevant document under `docs/ADR/` before changing contract-shape behavior it governs.
4. Read `docs/HOW_TO_CONFORM.md` before conforming a new backend.
5. Read `docs/CONTRACT_REVISION_PROPOSAL.md` for the current, not-yet-adopted proposal to make the contract more agent-callable and UI-performant, grounded in a real aimsun-psp usage audit.

## Routing Table

| Need | Go to |
|---|---|
| Strategic direction | `docs/vision/Vision.md`, `docs/vision/Business-need-design-brief.md`, `docs/vision/Product-requirements-document.md` |
| Contract schemas and normative prose (the ground truth) | `contracts/` |
| Conform a new or existing backend | `docs/HOW_TO_CONFORM.md` |
| Ratified contract-shape decisions | `docs/ADR/` (ADR-0001 scaffold-not-framework, ADR-0002 contract versioning, ADR-0003 dock artefact seam) |
| Proposed (not yet adopted) contract revisions | `docs/CONTRACT_REVISION_PROPOSAL.md` |
| Version history, support window | `CONTRACT_VERSIONS.md`, `CHANGELOG.md` |
| Cross-repo status, milestones | `docs/INTEGRATION_PLAN.md` |
| Testudo-facing intent | `docs/TESTUDO_INTENT.md` |

## Repository Layout

- `contracts/` - versioned schemas and normative specs (`VERSION`, `PIPELINE_DEFINITION.md`, `STEP_INTERFACE.md`, `CLI_SEAM.md`, `RESULT_CONTRACT.md`, `schemas/`). The ground truth every backend's `contract_version` pins against.
- `template/` - copyable `trip_summary` pipeline. Illustrative only, not normative.
- `conformance/` - black-box conformance kit; verifies a backend's CLI seam, result envelope, and step-result schema without inspecting internals.
- `docs/vision/` - strategic vision, business-need, and PRD documents.
- `docs/ADR/` - ratified contract-shape decisions.
- `docs/CONTRACT_REVISION_PROPOSAL.md` - proposed, not yet adopted, revisions to make the contract more agent-callable and UI-performant.
- `docs/HOW_TO_CONFORM.md` - step-by-step guide for conforming an existing backend.
- `docs/INTEGRATION_PLAN.md` - milestones and cross-repo status.
- `CONTRACT_VERSIONS.md`, `CHANGELOG.md` - version history.

Not owned here: backend implementation (belongs to each backend repo, e.g. `aimsun-psp`); Testudo
consumption logic; anything imported at runtime by a conforming backend (ADR-0001).
