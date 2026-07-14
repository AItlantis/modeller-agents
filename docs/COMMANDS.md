# Commands

Run commands from the workspace root with `PYTHONPATH` pointed at `src` until the package is installed:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli doctor --root AItlantis\modeller-agents
```

## Doctor

```powershell
python -m modeller.cli doctor --root AItlantis\modeller-agents
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict
python -m modeller.cli doctor --root AItlantis\modeller-agents --strict --json
```

Validates packaging metadata, plugin wiring, seed skills, skill-surface drift across `modeller-modules.yaml`, docs, plugin README, route capabilities, bundles, and reference packs; workflow method assets; bundle and reference-pack references; backend registry shape; vendor manifest shape; contract schema availability; and the docs skill index.

The normal doctor is an advisory operator check. It reports errors and warnings for the central runtime, while allowing planned vendors, draft packs, and sibling schema fallback to remain visible during local development.

Use `--strict` for CI/readiness gates. Strict mode promotes planned vendors, unpinned vendors, draft reference packs, and sibling schema fallback to hard failures.

Use `--json` when an orchestrator or CI job needs a deterministic payload containing `ok`, `skills`, `backends`, `warnings`, and `errors`.

Strict readiness is not complete until those blockers are remediated and the real backend smoke passes through `backend.json.runner.command`. See [readiness/STRICT_READINESS.md](readiness/STRICT_READINESS.md) for the exact blocker text, remediation commands, and pass conditions.

## Readiness

```powershell
python -m modeller.cli readiness --root AItlantis\modeller-agents
python -m modeller.cli readiness --root AItlantis\modeller-agents --json
```

Builds a deterministic strict-readiness remediation plan from the current `doctor --strict` blocker payload. It does not execute vendor syncs, promote reference packs, or mark backends active; it only emits blocker actions, suggested commands, and verification commands. Use `--json` when a workflow artifact, CI job, or orchestrator needs a machine-readable action list.

## Skills

```powershell
python -m modeller.cli skills --root AItlantis\modeller-agents
```

Lists central reusable skills exposed by the `modeller` plugin.

## Backends

```powershell
python -m modeller.cli backends --root AItlantis\modeller-agents
python -m modeller.cli backends --root AItlantis\modeller-agents --check aimsun-psp
```

Lists registered backend ids and checks local backend manifests when a local root is configured.

## Sync

```powershell
python -m modeller.cli sync --root AItlantis\modeller-agents
python -m modeller.cli sync --root AItlantis\modeller-agents modeller-pipelines
```

Lists vendors or prints the exact `git subtree pull` command for a planned vendor sync. It does not execute sync yet.

## Install

```powershell
python -m modeller.cli install --root AItlantis\modeller-agents C:\tmp\modeller-install-smoke
python -m modeller.cli install --root AItlantis\modeller-agents C:\tmp\modeller-install-smoke --apply
python -m modeller.cli install --root AItlantis\modeller-agents C:\tmp\modeller-install-smoke --include-runtime-assets --apply
```

Dry-run is the default. `--apply` copies the plugin, merges `.claude/settings.json`, and creates `.mcp.json` from the example if absent.

The installer copies local plugin wiring only by default. The central runtime remains in this repository unless `--include-runtime-assets` is passed:

- `method/` workflow definitions, templates, tasks, and checklists;
- `reference-packs/` repository facts consumed by central skills;
- `bundles/` mappings from target repositories to skills and reference packs;
- `schemas/` RunManifest and ContextReceipt JSON Schemas;
- `backends.toml`, `vendors.toml`, and contract validation support.

`--include-runtime-assets` copies `method/`, `reference-packs/`, `bundles/`, `schemas/`, `backends.toml`, and `vendors.toml` under `.modeller/runtime/` in the target. It is a snapshot copy for local orchestration. It does not sync vendors, activate draft packs, or prove backend runtime readiness.

When run from a source checkout, `install` reads assets from `--root`. When run from a wheel-installed CLI and `--root` is not a source checkout, it falls back to packaged assets force-included under `modeller/runtime`.

Every applied install writes `.modeller/install-manifest.json` in the target. The manifest records the source root, source git HEAD and worktree status, target root, runtime root, whether runtime assets were copied, and the copied asset list. Treat it as provenance for the snapshot, not as readiness proof.

## Validate

```powershell
python -m modeller.cli validate --root AItlantis\modeller-agents --backend-json AItlantis\modeller-pipelines\template\backend.json --expected-backend-id template
python -m modeller.cli validate --root AItlantis\modeller-agents --result-json C:\tmp\result.json
```

Validates contract-shaped JSON artifacts against `modeller-pipelines/contracts/schemas` when those schemas are available. During local development, `modeller-agents` first looks under `vendor/modeller-pipelines`, then falls back to the sibling `AItlantis/modeller-pipelines` checkout.

## Route

```powershell
python -m modeller.cli route --root AItlantis\modeller-agents --envelope AItlantis\modeller-agents\examples\testudo-context-envelope.json
python -m modeller.cli route --root AItlantis\modeller-agents --envelope path\to\orchestrate-envelope.json --run-id build-001
```

Routes a context envelope to a target repository bundle, central reusable skill, and reference pack set.

Route decisions read bundles and reference packs from the runtime root for `--root`. In a source checkout that is the repository root; in an installed target it is the manifest-declared `.modeller/runtime/` snapshot.

Routing is a hard gate: unknown `intent.requested_capability` values fail, the selected skill must be declared by the target bundle, and at least one selected valid reference pack must authorize the selected skill through `central_skills`.

Bundles must also declare `routingKeyKind` as either `repository` or `repository-class`. This keeps real repository targets such as `testudo` distinct from reusable class bundles such as `pipeline-backend` in machine-readable route output.

### Route requires a workflow for orchestration

When the resolved skill is `orchestrate`, or the envelope sets `execution_policy.requires_workflow: true`, routing additionally requires an active deterministic workflow run. Supply the run either as `execution_policy.run_id` (or `intent.run_id`) in the envelope, or with the `--run-id` CLI flag (the flag takes precedence over the envelope value). The route returns `ok: false` with an explanatory error when:

- no `run_id` is supplied for an orchestration route;
- the named run is not initialized;
- the run's current artifact gate does not pass (from `check_current_step`).

`RouteDecision` now includes a `run_id` field so callers can see which workflow run gated the route. Non-orchestration routes that do not set `requires_workflow` are unchanged and need no `run_id`.

## Plan

```powershell
python -m modeller.cli plan --root AItlantis\modeller-agents --prompt "review testudo" --json --envelope-output C:\tmp\testudo-envelope.json
python -m modeller.cli route --root AItlantis\modeller-agents --envelope C:\tmp\testudo-envelope.json
```

Drafts a deterministic prompt-to-approved-execution scaffold without running the target work. The plan includes:

- `IntentDraft`: prompt, target repository, requested capability, domains, workflow run id, and policy;
- `AlignmentContract`: source boundary, risk, consent, and approval state;
- `WorkflowCatalog`: discovered workflow definitions and step owners;
- `SkillPlan`: the route-resolved skill, bundle, reference packs, and knowledge packs;
- `ToolPlan`: suggested verification/route commands, approval steps, and blockers;
- `capability_manifest`: local bundles, skills, backends, workflows, and capability aliases discovered from the repository.

`--target-repository` and `--requested-capability` can be supplied explicitly, or inferred when the prompt mentions exactly one known bundle id and exactly one known capability. `--envelope-output` writes the drafted context envelope so the next `route` command does not require hand-written JSON. The command is scaffold-only: it never executes a backend, workflow advance, or target-repository edit.

## Run

```powershell
python -m modeller.cli run --root AItlantis\modeller-agents <backend-id> <pipeline-id> --config path\to\config.yml --run-dir C:\tmp\run-dir --backend-root path\to\backend
```

Runs a backend only through its declared `backend.json.runner.command`, then validates the final stdout line as the path to `result.json`. The command does not import backend implementation code.

## Workflow

Workflow commands are deterministic gates over persisted artifacts. Subagent responses, terminal output, and review notes are inputs to the record; they become evidence only after the relevant facts are incorporated into a completed artifact and `workflow advance` succeeds.

Workflow definitions are central method assets loaded from `method/workflows` under `--root`. A target repository install owns a local copy only when installed with `--include-runtime-assets`.

`--run-id` must be path-safe: 1-64 characters, start with a letter or number, use only letters, numbers, dot, underscore, or dash, and never contain `..`.

```powershell
python -m modeller.cli workflow --root AItlantis\modeller-agents init --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents status --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents check --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents complete-artifact --run-id build-001 --artifact brief --updated-by orchestrator --evidence "..." --output "..."
python -m modeller.cli workflow --root AItlantis\modeller-agents advance --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents manifest --run-id build-001 --envelope path\to\envelope.json
python -m modeller.cli workflow --root AItlantis\modeller-agents close --run-id build-001 --envelope path\to\envelope.json
python -m modeller.cli workflow --root AItlantis\modeller-agents status --run-id build-001
```

`complete-artifact` only updates artifacts that belong to the current step. Its `--updated-by` value must match that step's owner in `method/workflows/modeller-agents-build.workflow.json`.

`advance` is blocked until the current step's required artifacts exist, have `status: complete`, name `updated_by` matching the step owner, include `updated_at`, contain evidence plus decisions/output or verification content, and include every artifact-specific required term from the workflow JSON.

Current workflow owners and required terms:

| Artifact | Owner | Required terms |
| --- | --- | --- |
| `brief` | `orchestrator` | `outcome`, `scope`, `source-of-truth`, `source-boundary`, `constraints`, `acceptance evidence` |
| `prd` | `planner` | `requirements`, `acceptance`, `non-goals` |
| `decisions` | `planner` | `accepted`, `rejected`, `pending`, `boundary` |
| `backlog` | `planner` | `priority`, `story`, `verification` |
| `skills` | `architect` | `skill`, `trigger`, `verification` |
| `agents` | `architect` | `agent`, `authority`, `scope` |
| `memory` | `architect` | `memory`, `source`, `retrieval` |
| `implementation` | `executor` | `changed files`, `commands run`, `unresolved gaps` |
| `documentation` | `documenter` | `updated docs`, `runbook` |
| `handoff` | `orchestrator` | `final state`, `verification`, `residual risks`, `next actions`, `subagent findings` |

Recommended operator loop:

1. Run `status` to identify the current step and required artifacts.
2. Complete the step work and collect raw evidence from humans, tools, or subagents.
3. Update each current-step artifact with non-placeholder evidence and decisions/output or verification, including the required terms from the workflow JSON.
4. Run `check`.
5. Fix any artifact failures reported by `check`.
6. Run `advance` once.
7. Run `status` again and use that persisted state as the starting point for the next step.

Do not treat a subagent "complete" message as a gate result or as standalone evidence. The gate result is the combination of completed current-step artifacts, a passing `check`, and a successful `advance`.

### RunManifest, ContextReceipt, and Close

`workflow manifest` emits a machine-readable RunManifest for an initialized run. The manifest references the workflow definition, workflow state, and every workflow artifact by id, repository-relative path, SHA-256 digest, and size. It does not copy artifact bodies. Pass `--envelope` to add a ContextReceipt for the route context; the receipt records the retrieval query, selected bundle, reference packs, knowledge packs, budget, permissions, and hashed context files.

`workflow close` writes `.modeller/runs/<run-id>/run-manifest.json` unless `--manifest-output` is supplied, then prints the close gate status. Close fails unless:

- workflow state is `complete`;
- all workflow artifacts pass their deterministic gates;
- the implementation artifact passes its returned-edits evidence gate, including `changed files`, `commands run`, and `unresolved gaps`;
- workflow definition, state, and artifact references all carry SHA-256 digests.

Schemas live in `schemas/run-manifest.schema.json` and `schemas/context-receipt.schema.json`. The canonical command remains `python -m modeller.cli` / `modeller`; `python -m modeller_agents.cli` is compatibility only.
