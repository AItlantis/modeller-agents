---
title: Agent Instructions
status: active
type: context
owner: modeller-agents
authority_level: supporting
---

# Agent Instructions

## What This Is

This repository owns central reusable skills and runtime orchestration for the modelling ecosystem.

## Boundary

Allowed:

- create and maintain central reusable skills;
- define runtime workflows, routing checks, and backend invocation policy;
- maintain reference packs consumed by central skills;
- maintain plugin metadata, bundle manifests, and tooling gates.

Forbidden:

- move repository-local agents into this repository;
- copy backend implementation from `aimsun-psp`;
- copy Testudo product UI/runtime logic;
- define pipeline schemas owned by `modeller-pipelines`;
- store generated memory indexes as authority;
- edit vendored subtrees by hand.

## Start Here

1. Read `README.md`.
2. Read `docs/architecture/BOUNDARIES.md`.
3. Read `modeller-modules.yaml`.
4. Read `docs/vision/Vision.md`, `docs/vision/Business-need-design-brief.md`, and `docs/vision/Product-requirements-document.md` for strategic direction.
5. Run `python -m modeller.cli doctor --root .` before and after structural changes.

## Skill Rules

Every skill under `.claude/plugins/modeller/skills/*/SKILL.md` must have front matter with:

- `name`;
- `description`;
- `metadata.version`;
- `metadata.author`.

Repository-specific constraints belong in `reference-packs/` or `skills/*/references/`, not in generic skill bodies.

## Routing Table

| Need | Go to |
|---|---|
| Strategic direction | `docs/vision/Vision.md`, `docs/vision/Business-need-design-brief.md`, `docs/vision/Product-requirements-document.md` |
| Source-boundary and gate authority | `docs/architecture/BOUNDARIES.md` |
| Backend registration | `backends.toml` (declares each backend's contract version and status) |
| Vendored contract/memory subtrees | `vendors.toml`, `vendor/` (read-only, pinned; do not edit by hand) |
| Local repo health, release-readiness | `python -m modeller.cli doctor --root .` / `readiness` |
| Reference packs authorizing a skill | `reference-packs/` |

## Repository Layout

- `docs/vision/` - strategic vision, business-need, and PRD documents.
- `docs/architecture/` - `BOUNDARIES.md` and other architecture authority.
- `method/` - reusable method: agents, skills, workflows, tasks, templates, checklists.
- `reference-packs/` - repository-specific constraints and authorizing packs consumed by central skills.
- `bundles/` - bundle manifests routing a request to a skill and its authorizing packs.
- `backends.toml`, `backends.local.toml.example` - backend registry (contract version, status per backend).
- `vendors.toml`, `vendor/` - pinned, read-only vendored subtrees (`modeller-memory`, `modeller-pipelines`).
- `schemas/` - machine-readable schemas for envelopes, manifests, and workflow artifacts.
- `tools/` - the `modeller` CLI (`doctor`, `readiness`, `route`, `workflow`, ...).

Not owned here: repository-local agents (belong in the source repositories they operate on);
backend implementation (belongs to `aimsun-psp`); pipeline schemas (belong to `modeller-pipelines`);
generated memory indexes stored as authority (never — see Boundary above).

