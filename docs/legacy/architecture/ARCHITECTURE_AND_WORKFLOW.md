# Modeller-Agents Architecture And Workflow

**Status:** current operational overview
**Date:** 2026-07-11 · **Updated:** 2026-07-14 (added §5a knowledge axis + F-A current state)
**Owner:** `modeller-agents`

This document is the global map for the current `modeller-agents` scaffold. It explains what exists now, what the runtime owns, how work is routed, and which evidence gates must pass before the system is treated as ready.

## 1. Role

`modeller-agents` is the central reusable-skill and routing runtime for the modelling ecosystem.

It owns:

- reusable skills and method workflows;
- central route selection and source-boundary checks;
- bundle and reference-pack validation;
- the committed backend runtime registry;
- backend contract validation and backend invocation policy;
- deterministic workflow gates for brief, PRD, implementation, backlog, documentation, decisions, memory, skills, and handoff artifacts.

It does not own:

- repository-local agents or their write authority;
- Testudo product UI, workspace state, or product permissions;
- accepted durable knowledge in `modelling-knowledge`;
- memory storage internals in `modeller-memory`;
- pipeline or backend contract schemas owned by `modeller-pipelines`;
- concrete backend implementations or their `backend.json` manifest instances.

The boundary follows `modelling-knowledge/decisions/0001-local-agents-central-skills.md`: local agents stay with the repositories they operate on; reusable skills live in `modeller-agents`.

## 2. Repository Shape

```text
src/modeller/                         Python CLI, validators, routing, backend seam
.claude/plugins/modeller/             Claude/Codex plugin surface and central skills
method/                               workflow tasks, templates, checklists, run schema
bundles/                              repository bundles mapping skills to reference packs
reference-packs/                      repository-specific facts consumed as data
docs/                                 architecture, commands, readiness, workflow docs
backends.toml                         committed backend runtime registry
vendors.toml                          planned vendor/subtree registry
pyproject.toml                        package metadata and runtime asset inclusion
```

The CLI validates the same runtime assets used by the plugin surface. That gives operators one deterministic way to inspect health before routing, installing, validating a backend, or closing a workflow gate.

## 3. Install And Packaging Model

The default model is central runtime plus local plugin wiring:

- the source checkout remains the authority for skills, methods, bundles, packs, registries, and docs;
- `modeller install` copies the plugin surface into a target repository, merges `.claude/settings.json`, and creates `.mcp.json` from the example when absent;
- `modeller install --include-runtime-assets` also snapshots `method/`, `reference-packs/`, `bundles/`, `backends.toml`, and `vendors.toml` under `.modeller/runtime/` in the target;
- every applied install writes `.modeller/install-manifest.json` with source git provenance, runtime root, and copied asset inventory;
- wheel builds force-include the plugin and runtime assets under `modeller/runtime`, so installed `modeller` commands can install from packaged assets when a source checkout is not supplied.

Installing runtime assets is a snapshot operation. It does not make draft packs active, sync planned vendors, or prove a backend runtime smoke.

## 4. CLI Surfaces

| Command | Purpose |
|---|---|
| `doctor` | Advisory or strict repository health check for packaging, plugin wiring, skills, bundles, packs, registries, vendors, workflow assets, and schema access |
| `readiness` | Operator-facing strict-readiness blocker report with remediation actions |
| `skills` | Skill catalog inspection and drift checks |
| `backends` | Backend registry inspection and manifest contract checks |
| `sync` | Vendor and registry sync planning/check surface |
| `install` | Install central plugin wiring and optional runtime assets into a target repository |
| `validate` | Validate backend manifests and result envelopes against pipeline contracts |
| `route` | Resolve a context envelope into repository, bundle, skill, and reference packs |
| `run` | Invoke backend tasks through the backend seam after validation and consent gates |
| `workflow` | Deterministic artifact gate for briefs, PRDs, implementation notes, backlog, docs, skills, agents, memory, decisions, and handoff |

See `docs/COMMANDS.md` for command examples.

## 5. Routing Model

Routing is data-backed, not prompt-only.

1. A context envelope declares intent, risk, capabilities, target hints, consent state, and audit context.
2. `route` resolves the target repository or repository class.
3. The selected bundle must declare whether its routing key is a `repository` or `repository-class`.
4. The requested capability must be known.
5. The selected skill must be declared by the target bundle.
6. At least one valid selected reference pack must authorize that skill.
7. Medium and high risk work requires explicit consent before execution.

Reference packs are data. They let central skills remain reusable while carrying repository-specific constraints such as write scopes, verification commands, local invariants, private boundaries, and backend safety rules.

### 5a. Knowledge Axis (implemented, currently deactivated) — added 2026-07-14

Routing also has a second, orthogonal axis: `intent.domains[]` resolve against a data-only domain
registry to select `kind = "knowledge"` packs that reference accepted notes in `modelling-knowledge`
by id. It is additive — envelopes with no `domains[]` route exactly as the repository axis above.

- The route reads the vault's metadata export by shelling out to `modeller-memory`'s
  `vault_doctor export-index` / `export-domains` against the sibling `modelling-knowledge` checkout
  (not the committed JSON), then validates each candidate pack (digest parity, domain
  active/routable, note accepted/exposable).
- Retrieval is **references and metadata only** — note ids, purpose, sensitivity. Note bodies are
  never loaded; the progressive Level 0–3 loading in the vault alignment plan is not implemented.
- **Current state (F-A):** the vault has deactivated all scoped domains (`draft`/`routable:false`),
  so a route requesting a domain fails and selects zero knowledge packs, while normal `doctor`
  reports the mirrored disabled state as a warning. The `accessibility` pilot pack is inert until
  re-activation (decision 0010 accepted at general scope + the vault DR-1 attribution cure). See
  `docs/architecture/BOUNDARIES.md` and `docs/architecture/typed-packs-open-decisions.md`.

## 6. Deterministic Workflow

The workflow gate exists to prevent "agent did work" from being accepted without artifacts.

Each run is stored under `.modeller/runs/<run-id>/`. A run id must be path-safe and predictable. Required artifacts use front matter with at least:

- owner;
- status;
- related task or decision;
- required terms/evidence fields when applicable.

The gate checks that artifacts exist and carry the expected completion state before the workflow advances. Current workflow artifact families include:

- handoff;
- brief;
- PRD;
- implementation;
- backlog;
- documentation;
- skills;
- agents;
- memory;
- decisions.

The current evidence run is `.modeller/runs/orchestration-readiness-001`. It records the readiness hardening work, subagent review evidence, implementation notes, documentation updates, backlog, memory/readiness state, skill and agent notes, and handoff status.

## 7. Backend Contract Seam

`modeller-agents` owns runtime backend selection and invocation policy. It does not own backend schema definitions or backend implementations.

The seam is:

```text
backends.toml
  -> backend manifest instance (`backend.json`)
  -> modeller-pipelines schema validation
  -> consent/risk gate
  -> subprocess or explicit service invocation
  -> result envelope validation
  -> structured result returned to caller
```

Current strict readiness does not allow a backend to be called ready solely because it is listed. A real backend smoke must prove the contract seam before the backend is considered operational.

## 8. Readiness Modes

Normal `doctor` is advisory and useful during development. It verifies that the scaffold is internally coherent.

Strict readiness is a release/operator gate. It promotes these conditions to blockers:

- draft reference packs;
- planned or inactive backends;
- planned, unsynced, or unpinned vendors;
- contract schema fallback to sibling checkouts;
- missing real backend smoke evidence.

As of 2026-07-14, normal doctor passes for the runtime, while strict readiness is intentionally blocked by known setup gaps. That is the correct state until packs, vendors, schema vendoring, and backend smoke evidence are completed.

## 9. Current Evidence Commands

Run from `C:\Users\jean-noel.diltoer\software\sources`:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli doctor --root AItlantis\modeller-agents
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
python -m modeller.cli readiness --root AItlantis\modeller-agents --json
python -m modeller.cli route --root AItlantis\modeller-agents --envelope path\to\context.json
python -m modeller.cli workflow --root AItlantis\modeller-agents status --run-id orchestration-readiness-001
python -m modeller.cli workflow --root AItlantis\modeller-agents check --run-id orchestration-readiness-001
```

Run tests from the source checkouts:

```powershell
cd AItlantis\modeller-agents
python -m pytest -q

cd ..\modeller-pipelines
python -m pytest -q -p no:cacheprovider conformance
python -m pytest template\tests
```

## 10. Residual Risks

The scaffold is useful and deterministic, but it is not strict-ready yet.

Open blockers:

- activate or retire draft reference packs;
- convert planned vendor entries into synced, pinned vendor evidence;
- vendor `modeller-pipelines` schemas instead of relying on sibling fallback;
- prove real backend smoke through the backend seam;
- prove editable and wheel install from built package tooling once build dependencies are present.

## 11. Source Documents

- `README.md`
- `docs/COMMANDS.md`
- `docs/architecture/BOUNDARIES.md`
- `docs/readiness/STRICT_READINESS.md`
- `docs/workflows/DETERMINISTIC_WORKFLOW.md`
- `docs/method/README.md`
