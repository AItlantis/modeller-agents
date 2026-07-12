# modeller-agents

`modeller-agents` is the central reusable skill and routing runtime for the modelling ecosystem.

It owns:

- reusable skills such as workflow, review, antagonist review, source-boundary checks, memory recon, and backend contract checks;
- central runtime workflows and routing rules;
- the backend runtime registry;
- reference packs used by reusable skills.

It does not own:

- repository-local agents or local write authority;
- product UI or Testudo runtime behavior;
- memory storage internals;
- pipeline contract schemas;
- backend implementation.

The boundary is defined by `modelling-knowledge/decisions/0001-local-agents-central-skills.md`: local agents stay in the source repositories they operate on; reusable skills live here.

## Current Shape

```text
src/modeller/                         Python CLI and structural checks
.claude/plugins/modeller/             Claude/Codex plugin surface for central skills
method/                               method tasks, templates, checklists, workflows
reference-packs/                      repository-specific facts consumed as data
bundles/                              install bundles mapping skills to reference packs
backends.toml                         committed backend registry
vendors.toml                          planned vendor/subtree registry
```

`method/`, `reference-packs/`, and `bundles/` are central repository runtime assets. They are read and validated from this repository by the CLI and central plugin. The installer copies only plugin wiring by default; pass `--include-runtime-assets` when a target project needs a local copy of method assets, reference packs, bundles, and registries.

## Install Model

The current install model is central-runtime plus local plugin wiring:

- this repository remains the source of truth for reusable skills, method workflows, reference packs, bundles, backend registry, vendor registry, and contract validation support;
- `modeller install` copies the Claude/Codex plugin surface into a target project, merges `.claude/settings.json`, and creates `.mcp.json` from the example when absent;
- `modeller install --include-runtime-assets` additionally copies `method/`, `reference-packs/`, `bundles/`, `backends.toml`, and `vendors.toml` into the target;
- every applied install writes `.modeller/install-manifest.json` in the target with source git provenance and copied asset inventory;
- wheel builds force-include the plugin and runtime assets under `modeller/runtime`, so an installed `modeller` command can install from packaged assets when `--root` does not point to a source checkout;
- target repositories keep their local agents, write authority, and product/runtime behavior local.

Runtime-asset installation is an explicit snapshot copy. It does not make planned vendors synced, draft reference packs active, or runtime backends ready.

Route decisions are also gated: requested capabilities must be known, the selected skill must be declared by the target bundle, the bundle must declare whether its routing key is a `repository` or `repository-class`, and at least one selected valid reference pack must authorize that skill.

### Orchestration requires a deterministic workflow

Routing to the `orchestrate` skill — or any envelope that sets `execution_policy.requires_workflow: true` — additionally requires an active deterministic workflow. The envelope (or the `route --run-id` flag) must name an initialized `workflow` run whose current gate passes; otherwise `route` returns `ok: false` and blocks. Concretely, orchestration fails to route when:

- no `run_id` is supplied;
- the named run is not initialized (`workflow init` was never run);
- the run's current artifact gate is not satisfied.

This makes orchestration inseparable from the artifact-gated workflow: an orchestrator cannot proceed until the required artifacts exist and pass. Two workflow steps — `requirements` and `orchestration-design` — further require that their artifacts' `## Evidence` cite subagent/agent-produced provenance, so subagent output must be *incorporated* into a completed artifact, not merely asserted. See [docs/workflows/DETERMINISTIC_WORKFLOW.md](docs/workflows/DETERMINISTIC_WORKFLOW.md).

## First Verification

Run:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli doctor --root AItlantis\modeller-agents
```

After an editable or wheel install, use the console script form instead:

```powershell
modeller doctor --root AItlantis\modeller-agents
```

The normal doctor checks packaging metadata, plugin metadata, enabled marketplace wiring, seed skill front matter, skill-surface drift across module manifests/docs/route maps/bundles/reference packs, workflow method assets, bundle/reference-pack shape, backend registry shape, vendor manifest shape, and contract schema availability. Treat it as an advisory local health check for operators. CI/release readiness should use `doctor --strict`, which promotes planned vendors, unpinned vendors, draft reference packs, and sibling schema fallback to hard failures.

Strict readiness also requires a real backend smoke through the backend contract seam before a runtime backend is called ready. See [docs/readiness/STRICT_READINESS.md](docs/readiness/STRICT_READINESS.md) for the hard blockers and exact remediation commands and conditions.

See [docs/COMMANDS.md](docs/COMMANDS.md) for the current CLI surfaces: `doctor`, `readiness`, `skills`, `backends`, `sync`, `install`, `validate`, `route`, `run`, and deterministic `workflow` gates.

For the global architecture and deterministic workflow overview, see [docs/architecture/ARCHITECTURE_AND_WORKFLOW.md](docs/architecture/ARCHITECTURE_AND_WORKFLOW.md).
