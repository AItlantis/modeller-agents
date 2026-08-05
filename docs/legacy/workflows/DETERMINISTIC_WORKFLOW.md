# Deterministic Workflow

`modeller-agents` workflows are artifact-gated. A step cannot advance because an agent says it is done; it advances only when the workflow state and required artifacts prove that it is done.

Use this runbook when operating a workflow. The deterministic record is the artifact set plus the workflow state after `workflow advance`; chat messages, subagent summaries, and tool output are working notes until their relevant facts are incorporated into a completed artifact and the gate advances.

Workflow definitions, artifact templates, and required-term policy are central method runtime assets in `method/` under the `modeller-agents` repository passed as `--root`. In an installed target, `--include-runtime-assets` snapshots those assets under `.modeller/runtime/method/`.

`run_id` is path-safe by design. It must be 1-64 characters, start with a letter or number, use only letters, numbers, dot, underscore, or dash, and must not contain `..`.

## Artifact Contract

Each required artifact is a Markdown file with front matter:

```yaml
workflow_id: modeller-agents-build
run_id: <run id>
artifact: brief
step: intake
status: draft | complete
updated_by: <agent or human>
updated_at: <timestamp>
```

To pass a gate, the artifact must:

- exist;
- have `status: complete`;
- have `updated_by` matching the current step owner;
- have `updated_at`;
- contain non-placeholder content under `## Evidence`;
- contain non-placeholder content under `## Decisions Or Outputs`;
- contain non-placeholder content under `## Verification`;
- contain every artifact-specific required term configured in `method/workflows/modeller-agents-build.workflow.json`.

Subagent output is raw evidence only. It becomes gate evidence only after the operator or orchestrator incorporates the relevant facts into the required artifact and marks that artifact complete. A subagent saying "done" is not a gate pass.

## Required Artifacts

- `brief`
- `prd`
- `backlog`
- `decisions`
- `skills`
- `agents`
- `memory`
- `implementation`
- `documentation`
- `handoff`

## Owners And Required Terms

`complete-artifact` and `check` enforce the current step owner from the workflow JSON. Use the owner as `--updated-by`, and include the required terms in the artifact's evidence, decisions/output, or verification sections.

| Step | Owner | Artifacts | Required terms |
| --- | --- | --- | --- |
| `intake` | `orchestrator` | `brief` | `outcome`, `scope`, `source-of-truth`, `source-boundary`, `constraints`, `acceptance evidence` |
| `requirements` | `planner` | `prd` | `requirements`, `acceptance`, `non-goals` |
| `requirements` | `planner` | `decisions` | `accepted`, `rejected`, `pending`, `boundary` |
| `planning` | `planner` | `backlog` | `priority`, `story`, `verification` |
| `orchestration-design` | `architect` | `skills` | `skill`, `trigger`, `verification` |
| `orchestration-design` | `architect` | `agents` | `agent`, `authority`, `scope` |
| `orchestration-design` | `architect` | `memory` | `memory`, `source`, `retrieval` |
| `implementation` | `executor` | `implementation` | `changed files`, `commands run`, `unresolved gaps` |
| `documentation` | `documenter` | `documentation` | `updated docs`, `runbook` |
| `handoff` | `orchestrator` | `handoff` | `final state`, `verification`, `residual risks`, `next actions`, `subagent findings` |

## Operator Runbook

Run commands from the workspace root. During local development, set `PYTHONPATH` once before invoking the CLI:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
```

1. Initialize or resume the run with a path-safe `run_id`.

   ```powershell
   python -m modeller.cli workflow --root AItlantis\modeller-agents init --run-id build-001
   python -m modeller.cli workflow --root AItlantis\modeller-agents status --run-id build-001
   ```

2. Identify the current step and its required artifacts from `status`.

3. Do the work for the current step. Treat subagent output, terminal output, review notes, and manual observations as raw inputs only.

4. Write the relevant evidence and decisions into the required artifact files, or use `complete-artifact` for simple updates to an artifact required by the current step only. `--updated-by` must equal the owner of that current step.

   ```powershell
   python -m modeller.cli workflow --root AItlantis\modeller-agents complete-artifact --run-id build-001 --artifact brief --updated-by orchestrator --evidence "Evidence from completed work." --output "Decision or output from the step."
   ```

5. Check the gate before advancing.

   ```powershell
   python -m modeller.cli workflow --root AItlantis\modeller-agents check --run-id build-001
   ```

   If `check` fails, update the named artifacts. Do not advance based on a subagent completion message, terminal output, or review note unless the relevant facts are incorporated into the artifact.

6. Advance exactly one gate.

   ```powershell
   python -m modeller.cli workflow --root AItlantis\modeller-agents advance --run-id build-001
   ```

7. Confirm the new state.

   ```powershell
   python -m modeller.cli workflow --root AItlantis\modeller-agents status --run-id build-001
   ```

Repeat steps 2 through 7 until the workflow reaches the final state. The auditable fact that a step completed is the successful `advance` result and the updated workflow state, not any intermediate agent statement.

8. Close the run by writing a RunManifest and checking the close gate.

   ```powershell
   python -m modeller.cli workflow --root AItlantis\modeller-agents close --run-id build-001 --envelope path\to\envelope.json
   ```

   `close` writes `.modeller/runs/<run_id>/run-manifest.json` and returns non-zero unless the workflow state is `complete`, every artifact gate passes, the implementation artifact proves returned edits and verification evidence, and workflow/state/artifact references all include SHA-256 digests. A subagent completion message is never sufficient for close.

## Orchestration Requires A Workflow (Coupling)

Routing to the `orchestrate` skill — or any envelope whose `execution_policy.requires_workflow` is `true` — now requires a named, initialized deterministic workflow run whose current gate passes. `route_envelope` reads the run id from `execution_policy.run_id` (falling back to `intent.run_id`), or accepts an explicit override.

- No `run_id` present: `route` returns `ok: false` with an error naming `run_id` as required.
- `run_id` present but no matching run initialized: `route` returns `ok: false` with an error naming the run as not found, and points at `workflow init --run-id`.
- `run_id` present and initialized, but the current step's gate does not pass (for example, a required artifact is still a draft): `route` returns `ok: false` with an error naming the workflow gate as not satisfied.
- `run_id` present, initialized, and the current step's gate passes: routing proceeds as normal (subject to the usual bundle/reference-pack authorization checks).

Non-`orchestrate` skills that do not set `execution_policy.requires_workflow: true` are unaffected and route exactly as before, with `run_id` left `null` in the decision.

An operator can supply the run id on the command line instead of editing the envelope JSON:

```powershell
python -m modeller.cli route --root AItlantis\modeller-agents --envelope path\to\envelope.json --run-id build-001
```

`--run-id` on the CLI takes precedence over any `run_id` present in the envelope.

Separately, the `requirements` and `orchestration-design` steps set `"requires_agent_evidence": true` in `method/workflows/modeller-agents-build.workflow.json`. For artifacts in those steps (`prd`, `decisions`, `skills`, `agents`, `memory`), the `## Evidence` section must contain a provenance marker (for example `subagent`, `agent `, `sonnet`, `evidence-source:`, or `produced by`) showing that agent/subagent-produced work was actually incorporated into the artifact. Evidence written entirely in the operator's own words, with no trace of subagent output, fails the gate even if every required term is present — subagent output must be incorporated into the artifact, not merely asserted as done.

## Readiness Modes

The workflow gate is deterministic for a run, but it is not the same thing as repository release readiness. Use the normal `doctor` command as an advisory local health check for the central runtime. Use `doctor --strict` for CI/readiness, so central assets such as method workflows, bundles, reference packs, backend registry entries, vendor state, and schema availability are checked under release policy.

Do not describe a workflow run, a normal doctor pass, or a plugin install as proving full release readiness. They prove only the specific gate or install behavior they executed. Release readiness requires the strict doctor gate and any backend smoke required by the relevant repository.

## Commands

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli workflow --root AItlantis\modeller-agents init --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents status --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents check --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents complete-artifact --run-id build-001 --artifact brief --updated-by orchestrator --evidence "..." --output "..."
python -m modeller.cli workflow --root AItlantis\modeller-agents advance --run-id build-001
python -m modeller.cli workflow --root AItlantis\modeller-agents manifest --run-id build-001 --envelope path\to\envelope.json
python -m modeller.cli workflow --root AItlantis\modeller-agents close --run-id build-001 --envelope path\to\envelope.json
```

`advance` fails until the current step's required artifacts pass the gate. After `advance` succeeds, run `status` before starting the next step so the operator is working from the persisted workflow state.

`manifest` and `close` use `schemas/run-manifest.schema.json` and `schemas/context-receipt.schema.json` as the traceability contract. Both surfaces reference artifacts by id, path, and digest instead of embedding artifact content.
