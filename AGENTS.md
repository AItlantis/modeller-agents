# Agent Instructions

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
4. Run `python -m modeller.cli doctor --root .` before and after structural changes.

## Skill Rules

Every skill under `.claude/plugins/modeller/skills/*/SKILL.md` must have front matter with:

- `name`;
- `description`;
- `metadata.version`;
- `metadata.author`.

Repository-specific constraints belong in `reference-packs/` or `skills/*/references/`, not in generic skill bodies.

