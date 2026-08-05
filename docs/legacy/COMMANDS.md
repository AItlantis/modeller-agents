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
- `schemas/` RunManifest, ContextReceipt, human-review, V-cycle trace, and subagent JSON Schemas;
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

When the resolved skill is `orchestrate`, `v-cycle`, or the envelope sets `execution_policy.requires_workflow: true`, routing additionally requires an active workflow run unless the policy explicitly disables workflow binding. Supply the run either as `execution_policy.run_id` (or `intent.run_id`) in the envelope, or with the `--run-id` CLI flag (the flag takes precedence over the envelope value).

`execution_policy.gate_policy` controls what route proves:

- `bind-run` validates that the run exists and that the requested V-cycle stage matches the current run stage. It does not require generated artifacts or human review to be complete. Use this at the start of orchestrated work, before subagents have produced evidence.
- `check-current-gate` validates the current workflow exit gate. It fails while placeholders, missing evidence, failed checks, or missing human-review receipts remain. Use this before advancing or closing work.

The route returns `ok: false` with an explanatory error when:

- no `run_id` is supplied for an orchestration route;
- the named run is not initialized;
- the run's current artifact gate does not pass and `gate_policy` is `check-current-gate`.

`RouteDecision` includes a `run_id` field so callers can see which workflow run gated the route. Non-orchestration routes that do not set `requires_workflow` are unchanged and need no `run_id`.

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

`--target-repository` and `--requested-capability` can be supplied explicitly, or inferred when the prompt mentions exactly one known bundle id and exactly one known capability. Natural wording for common intents such as documentation lookup, brief/recon creation, code edits, test repair, validation, and deployment is classified before envelope creation. `--envelope-output` writes the drafted context envelope so the next `route` command does not require hand-written JSON. The command is scaffold-only: it never executes a backend, workflow advance, or target-repository edit.

For V-cycle natural-language work, `plan` writes `execution_policy.gate_policy: bind-run` by default. That allows the orchestrator to initialize a run, bind to the selected stage, report status, and ask the human before subagents start work. Use `--gate-policy check-current-gate` when you want the route to require the current stage exit gate to pass.

When `plan` or `orchestrate` is run from a parent workspace with `--target-repository <repo>`, the CLI
first checks the supplied root for that bundle. If absent, it searches only `<root>\<repo>` and
`<root>\*\<repo>` for an installed modeller runtime containing `.modeller/install-manifest.json` and
`.modeller/runtime/bundles/<repo>.bundle.json`. A single match becomes the command root; zero or
multiple matches fail closed with the inspected root, searched bundle path, child patterns, matching
candidates, and rerun advice.

Typical orchestrator loop:

```powershell
python -m modeller.cli --root . orchestrate --prompt "Create a brief.md and recon.md about rendering_geh pipeline" --target-repository aimsun-psp --run-id rendering-geh-brief-recon-20260715 --json
python -m modeller.cli --root . orchestrate --prompt "Create a functional specification for aimsun-psp rendering_geh pipeline" --target-repository aimsun-psp --run-id functional-spec-review-20260715 --mode paired-review --json
python -m modeller.cli --root . orchestrate --prompt "Create a brief.md and recon.md about rendering_geh pipeline" --target-repository aimsun-psp --run-id rendering-geh-brief-recon-20260715 --chat-output .modeller\runs\rendering-geh-brief-recon-20260715\chat-handoff.md
python -m modeller.cli --root . orchestrate --prompt "Create a brief.md and recon.md about rendering_geh pipeline" --target-repository aimsun-psp --run-id rendering-geh-brief-recon-20260715 --launch-chat codex
python -m modeller.cli --root . orchestrate --prompt "Create a brief.md and recon.md about rendering_geh pipeline" --target-repository aimsun-psp --run-id rendering-geh-brief-recon-20260715 --launch-chat claude
```

The `orchestrate` command is the deterministic front door for a chat orchestrator. With `--json` it
prints setup/status for automation; it does not start a Codex or Claude chat. With `--chat-output` it
writes a markdown handoff prompt containing the envelope path, work-order path, current run status,
gate blockers, and required human-approval loop. With `--launch-chat codex` or `--launch-chat claude`
it writes that handoff and starts the selected chat client with an initial prompt telling it to read
the handoff and continue as `modeller:orchestrator`.

The runtime host does not have to be the target source repository. For example, a command launched
from an installed `aimsun-psp` checkout can target `modelling-knowledge`; the planner uses the
installed `.modeller/runtime/` bundle for routing and records the discovered sibling source root in
the handoff. The chat process starts from that `source_root` when `--launch-chat` is used.

The deterministic setup
classifies the natural prompt, initializes or reuses a V-cycle run when required, writes
`.modeller/runs/<run-id>/context-envelope.json`, routes with `bind-run`, reports the current gate, and
writes a stage-bound subagent work order under `.modeller/runs/<run-id>/work-orders/`. It exits `0`
when setup succeeds even if the current V-cycle gate still fails because artifacts contain
placeholders or no human review receipt exists yet; that failure is the expected pause before
subagent evidence and human approval. It does not apply human review, advance the workflow, edit target
source files, or invent a subagent lane receipt.

`--mode paired-review` initializes the requested V-cycle stage plus its paired verification stage when
the classified stage has one. Stage advancement remains gated: if `orchestrate` created a work order,
`workflow check` requires a matching complete lane receipt before `workflow advance` can pass. Human
review receipts are rejected when the reviewer id matches a subagent/work-order agent for that stage.
Closed stages are rechecked before later stages advance so material artifact changes cannot silently
stale an earlier human review.

The equivalent manual sequence remains:

```powershell
python -m modeller.cli --root . plan --prompt "Create a brief.md and recon.md about rendering_geh pipeline" --target-repository aimsun-psp --envelope-output .modeller\runs\rendering-geh-envelope.json
python -m modeller.cli --root . workflow init --run-id rendering-geh-brief-recon-20260715 --family v-cycle --mode stage --stage project-governance
python -m modeller.cli --root . plan --prompt "Create a brief.md and recon.md about rendering_geh pipeline" --target-repository aimsun-psp --run-id rendering-geh-brief-recon-20260715 --envelope-output .modeller\runs\rendering-geh-envelope.json
python -m modeller.cli --root . route --envelope .modeller\runs\rendering-geh-envelope.json
python -m modeller.cli --root . workflow status --run-id rendering-geh-brief-recon-20260715
python -m modeller.cli --root . workflow work-order --run-id rendering-geh-brief-recon-20260715 --target-repository aimsun-psp --target-path domains/_41_MacroscopicResult/pipelines/rendering_geh --task "Create brief and recon evidence." --agent-id recon-agent --output .modeller\runs\rendering-geh-brief-recon-20260715\work-order.json
python -m modeller.cli --root . workflow lane-receipt --work-order .modeller\runs\rendering-geh-brief-recon-20260715\work-order.json --receipt .modeller\runs\rendering-geh-brief-recon-20260715\lane-receipt.json
python -m modeller.cli --root . workflow ingest-lane-receipt --run-id rendering-geh-brief-recon-20260715 --receipt-id lane-test --artifact recon --artifact planning-baseline
```

`workflow work-order` writes a stage-bound subagent contract. It records the active run, current
stage, target repository, optional target path, allowed paths, forbidden actions, required artifacts,
required tests, and the gate command the orchestrator will run later. It does not spawn the subagent
by itself.

`workflow lane-receipt` validates a returned subagent receipt against its work order. It rejects
mismatched run/stage ids, changed files outside `allowed_paths`, missing `no_git_assertion`, attempted
workflow advancement, and forbidden git/workflow commands. A valid lane receipt and its work order are
stored under `.modeller/runs/<run-id>/subagents/<stage-id>/` and become digest-referenced evidence in
`workflow manifest`; the command never advances workflow state by itself.

`workflow ingest-lane-receipt` ingests a persisted lane receipt into named active V-cycle artifacts.
It accepts artifact ids only, not paths. Artifact ids are standard V-cycle artifacts such as `brief`,
`recon`, `workflow-plan`, `machine-evidence`, and `handoff`, plus current-stage artifact ids such as
`planning-baseline`. Ingestion mutates markdown artifacts and updates trace metadata; it does not
apply human review, advance stages, or make `ai_usage.human_review_complete` true.

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

### V-Cycle Workflow Family

The V-cycle family is YAML-backed (`method/workflows/v-cycle.family.yaml`,
`method/workflows/v-cycle.stages.yaml`) and uses `method/policies/v-cycle-vigilance.yaml`.
It is exposed through the `v-cycle` skill and copied into target repositories by
`install --include-runtime-assets`.

```powershell
python -m modeller.cli workflows --root AItlantis\modeller-agents list --json
python -m modeller.cli workflow --root AItlantis\modeller-agents recommend --prompt "review system validation against requirements"
python -m modeller.cli workflow --root AItlantis\modeller-agents init --run-id v-001 --family v-cycle --mode stage --stage functional-specification
python -m modeller.cli workflow --root AItlantis\modeller-agents init --run-id v-pair-001 --family v-cycle --mode paired-review --stage functional-specification
python -m modeller.cli workflow --root AItlantis\modeller-agents trace-check --run-id v-001
python -m modeller.cli workflow --root AItlantis\modeller-agents check --run-id v-001
python -m modeller.cli workflow --root AItlantis\modeller-agents review --run-id v-001 --receipt human-review.json
python -m modeller.cli workflow --root AItlantis\modeller-agents request-review --run-id v-001 --provider receipt-file --receipt human-review.json
python -m modeller.cli workflow --root AItlantis\modeller-agents advance --run-id v-001
```

`workflow init --family v-cycle` writes `.modeller/runs/<run-id>/state.json`, common
artifacts (`BRIEF.md`, `RECON.md`, `workflow-plan.md`, `machine-evidence.md`,
`handoff.md`), `v-trace.json`, and only the selected stage artifacts for `stage`
mode. `paired-review` selects the requested stage and its configured paired stage.

`workflow check` blocks while generated markdown still contains placeholders, while
the current stage lacks a human-review receipt, or when a receipt digest no longer
matches the current stage artifacts. Missing prerequisites are surfaced in warnings
so the operator can obtain a baseline or record a confirmed assumption; the runtime
does not invent missing upstream artifacts.

`workflow review` accepts only receipts whose `reviewer.actor_type` is `human`, whose
role matches one of the stage `human_owner_roles`, and whose `artifact_digest` equals
the current stage digest. Receipt schema lives in
`schemas/human-review-receipt.schema.json`; trace schema lives in
`schemas/v-cycle-trace.schema.json`.

`workflow request-review` wraps the same gate with a provider. `--provider receipt-file
--receipt <human-review.json>` applies a user-supplied receipt without normalizing it.
`--provider test-fixture` generates and applies a deterministic test receipt only when
`--allow-test-fixture` is present and `--fixture-metadata` points under
`.modeller/runs/<run-id>/` to JSON with matching `run_id`, `stage_id`,
`provider: "test-fixture"`, and `fixture_run: true`. `test-fixture` is for E2E tests
only. It is not a production approval path.

### RunManifest, ContextReceipt, and Close

`workflow manifest` emits a machine-readable RunManifest for an initialized run. The manifest references the workflow definition, workflow state, every workflow artifact, and any persisted subagent lane receipts by id, repository-relative path, SHA-256 digest, and size. It does not copy artifact bodies. Pass `--envelope` to add a ContextReceipt for the route context; the receipt records the retrieval query, selected bundle, reference packs, knowledge packs, budget, permissions, and hashed context files.

`workflow close` writes `.modeller/runs/<run-id>/run-manifest.json` unless `--manifest-output` is supplied, then prints the close gate status. Close fails unless:

- workflow state is `complete`;
- all workflow artifacts pass their deterministic gates;
- the implementation artifact passes its returned-edits evidence gate, including `changed files`, `commands run`, and `unresolved gaps`;
- workflow definition, state, and artifact references all carry SHA-256 digests.

Schemas live under `schemas/`, including `run-manifest.schema.json`, `context-receipt.schema.json`, `human-review-receipt.schema.json`, `subagent-work-order.schema.json`, and `subagent-lane-receipt.schema.json`. The canonical command remains `python -m modeller.cli` / `modeller`; `python -m modeller_agents.cli` is compatibility only.
