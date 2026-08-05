# Intent-Aware Orchestrator Improvement Plan

Status: in-progress
Date: 2026-07-15

## Target Behavior

A human should be able to type a simple natural-language request in an agent orchestrator chat, for
example:

```text
Create a brief and recon for domains/_41_MacroscopicResult/pipelines/rendering_geh.
```

The orchestrator must then:

- identify the user intent without requiring `--requested-capability`;
- identify the target repository and target project path;
- select the correct capability, V-cycle stage, risk level, workflow family, and gate policy;
- initialize or reuse the required workflow run;
- dispatch subagents only with gate-bound work orders;
- convert subagent outputs into workflow artifacts and evidence;
- run machine gates before every stage transition;
- request human review at human gates;
- continue only after a valid human review receipt and `workflow advance`.

The human can provide approvals during an interactive test. Automated E2E tests may use a test-only
approval fixture, but production runs must still reject AI-issued human review receipts.

## Evidence From Current Behavior

### Chat Transcript

Source:

```text
C:/Users/jean-noel.diltoer/software/sources/aimsun/aimsun-psp/output/chat_modeller_orchestrator.md
```

Observed behavior:

- The chat request was to create a brief and recon for `rendering_geh`.
- The agent loaded PSP-specific `/psp-understand`.
- It drafted an informal brief and asked for confirmation.
- It did not invoke `modeller.cli plan`.
- It did not initialize a `.modeller/runs/<run-id>` workflow.
- It did not issue a stage-bound subagent work order.
- It did not run `workflow check`.
- It did not require a digest-bound human-review receipt.

Expected behavior:

- The chat front door should first call the modeller orchestration planner.
- A brief/recon request should become either read-only review/recon work, or a V-cycle
  governance/needs/specification stage when persisted workflow artifacts are requested.
- The agent should not bypass modeller gates by directly using a PSP skill.

### CLI Transcript

Source:

```text
C:/Users/jean-noel.diltoer/software/sources/aimsun/aimsun-psp/output/cli_modeller_orchestrator.md
```

Observed behavior:

```text
python -m modeller.cli --root . plan ...
execution plan: BLOCKED
blocked_by:
  - no bundle found for target repository 'aimsun-psp'
```

Root cause:

- The command was run from `C:/Users/jean-noel.diltoer/software/sources`.
- The installed `aimsun-psp` runtime lives under
  `C:/Users/jean-noel.diltoer/software/sources/aimsun/aimsun-psp/.modeller/runtime`.
- With the corrected root, explicit `review` routing works.
- With natural wording and no explicit capability, the plan still defaults to `workflow`.

Correct-root probe summary:

| Prompt mode | Root | Capability result | Status |
| --- | --- | --- | --- |
| explicit `--requested-capability review` | `aimsun/aimsun-psp` | `review` | route-ready |
| natural only | `aimsun/aimsun-psp` | `workflow` | generic fallback |

## Current Implementation Gap

The current planner infers capability by exact token matching. It detects a capability only when the
prompt contains one known capability token such as `review` or `v-cycle`. Natural wording such as
"create a brief", "find docs", "audit this pipeline", or "edit code" is not semantically classified.

Subagent discipline is also mostly instructional. The deterministic workflow records artifacts and
checks gates, but there is no machine-checkable subagent lane receipt proving that a spawned worker
was bound to the current run, stage, allowed paths, required tests, and gate commands.

## Design Principles

- Keep `route` deterministic and envelope-driven.
- Put natural-language inference before envelope creation.
- Never let a subagent advance workflow state directly.
- Never treat a subagent completion message as evidence by itself.
- Preserve explicit CLI options as overrides.
- Fail closed on ambiguous or risky intent.
- Allow test-only human approval fixtures only in E2E fixture roots.

## Phase Plan

### Phase 0 - Regression Characterization

Effort: L

Add tests and fixtures that lock down the current bad behavior before changing it.

Deliverables:

- Fixture prompts for docs lookup, brief/recon creation, code edit, E2E test repair, and deployment.
- Tests proving current exact-token inference still works.
- Tests proving natural wording currently falls back to `workflow`.
- A transcript regression note referencing the two output files above.

Acceptance:

- The failing natural-language cases are visible in tests.
- The explicit capability path remains green.

### Phase 1 - Intent Classifier

Effort: M

Add a deterministic intent classifier before `IntentDraft` creation.

Suggested module:

```text
src/modeller/intents.py
```

Classifier output:

```json
{
  "primary_intent": "brief-and-recon",
  "requested_capability": "v-cycle",
  "workflow_family": "v-cycle",
  "v_cycle_stage": "project-governance",
  "requires_workflow": true,
  "mutation_scope": "workflow-artifacts",
  "risk_level": "medium",
  "confidence": "high",
  "reasons": ["brief/recon artifacts requested", "target pipeline path detected"]
}
```

Initial mappings:

| Natural wording | Capability | Stage | Workflow |
| --- | --- | --- | --- |
| find docs, summarize docs, explain | `review` | none or `project-governance` | false by default |
| create brief, create recon, prepare baseline | `v-cycle` | `project-governance` or `needs-analysis` | true |
| audit as-is, document as-is | `review` or `v-cycle` based on artifact mutation | false for summary, true for persisted artifacts |
| implement, edit, refactor, fix code | `v-cycle` | `implementation` | true |
| add tests, run tests, fix E2E | `v-cycle` | `unit-testing` or `integration-testing` | true |
| validate behavior | `v-cycle` | `system-validation` | true |
| install, deploy, release | `v-cycle` | `deployment` | true |

Acceptance:

- `Create a brief.md and recon.md about rendering_geh pipeline` no longer defaults to generic
  `workflow`.
- `Find docs ... do not edit` remains read-only.
- `Refactor code ... update tests` selects `v-cycle` and `implementation`.
- Ambiguous prompts return a clarification blocker with reasons.

### Phase 2 - Plan and Envelope Integration

Effort: M

Wire classifier output into `build_execution_plan`.

Deliverables:

- `IntentDraft` records classifier result, confidence, and reasons.
- Context envelope records `workflow_family`, `v_cycle_stage`, `requires_workflow`,
  `mutation_scope`, and `source_prompt`.
- Explicit CLI arguments still override classifier output.
- `route` uses `workflow_family: v-cycle` to select V-cycle gate checks even when the skill alias is
  indirect.

Acceptance:

- Natural brief/recon prompt writes an envelope that can route to the intended gate.
- Natural docs-only prompt writes an envelope that routes read-only.
- Natural code-edit prompt writes a V-cycle envelope and fails closed until a valid run/gate exists.

### Phase 3 - Installed-Root Discovery

Effort: M

Fix the CLI usability failure shown by `cli_modeller_orchestrator.md`.

Deliverables:

- Root resolver that can detect when the user is in a parent workspace and the target repo is a
  child directory.
- Diagnostic message that says which root was inspected and where bundles were searched.
- Optional `--target-path` or `--project-path` for pipeline folders inside a target repository.

Acceptance:

- Running from `C:/Users/.../sources` with `--target-repository aimsun-psp` either resolves
  `aimsun/aimsun-psp` automatically or fails with a precise instruction to rerun with
  `--root aimsun/aimsun-psp`.
- The error must not say only "no bundle found" when a child install exists.

### Phase 4 - Chat Orchestrator Front Door

Effort: H

Implementation status: CLI slice complete. `python -m modeller.cli orchestrate` classifies a
natural prompt, initializes or reuses a V-cycle run, persists the context envelope, routes with
`bind-run`, reports gate status, and writes a gate-bound subagent work order. It supports `stage` and
`paired-review` invocation modes. It deliberately pauses before subagent execution, human review, or
workflow advance.

Add an executable chat-oriented orchestration command that wraps existing primitives.

Candidate command:

```powershell
python -m modeller.cli orchestrate --root . --prompt "<natural request>" --json
```

Flow:

```text
prompt
  -> classify intent
  -> plan
  -> route
  -> initialize/reuse workflow run
  -> issue subagent work orders
  -> ingest subagent results into artifacts
  -> workflow check
  -> human review request
  -> workflow review
  -> workflow advance
```

Acceptance:

- The chat path cannot directly jump into `/psp-understand` without a modeller plan/route receipt.
- The orchestrator explains selected intent, stage, run id, and gate status before work starts.
- The orchestrator pauses for human approval when a human gate is reached.

### Phase 5 - Subagent Lane Receipts

Effort: H

Add a machine-checkable protocol for subagent work.

Suggested schemas:

```text
schemas/subagent-work-order.schema.json
schemas/subagent-lane-receipt.schema.json
```

Required work-order fields:

- `run_id`
- `workflow_family`
- `stage_id`
- `allowed_paths`
- `forbidden_actions`
- `required_artifacts`
- `required_tests`
- `gate_commands`
- `expected_result_schema`

Required lane-receipt fields:

- `agent_id`
- `run_id`
- `stage_id`
- `files_read`
- `files_changed`
- `commands_run`
- `tests_run`
- `exit_status`
- `artifact_refs`
- `output_digest`
- `risks`
- `no_git_assertion`

Acceptance:

- A subagent result without matching `run_id` and `stage_id` is rejected.
- A subagent result outside allowed paths is rejected.
- A subagent result cannot advance workflow state.
- The orchestrator reruns gates before accepting the lane.

### Phase 6 - Human Review Provider

Effort: M

Add a human review provider abstraction.

Providers:

| Provider | Purpose | Production |
| --- | --- | --- |
| `interactive` | Ask the human in chat/terminal | yes |
| `receipt-file` | Apply a user-supplied JSON receipt | yes |
| `test-fixture` | Generate deterministic E2E receipts | no |

Acceptance:

- Interactive review writes a digest-bound receipt and calls `workflow review`.
- AI actor receipts are still rejected.
- Test fixture receipts require an explicit flag and fixture run metadata.

### Phase 7 - End-to-End Tests

Effort: H

Implementation status: covered for the current deterministic CLI loop. Tests cover natural docs
read-only routing, brief/recon run setup, paired-review natural setup, existing-run reuse, stage
mismatch blocking without mutation, ambiguous prompt fail-closed behavior, unsafe target path
rejection, lane-receipt-required advancement, subagent self-review rejection, fixture human reviews,
multi-stage advancement, and stale closed-stage material artifact invalidation.

E2E scenarios:

1. Natural docs prompt stays read-only and does not mutate files.
2. Natural brief/recon prompt creates a workflow run and required artifacts.
3. Natural code-edit prompt enters V-cycle implementation and blocks at human gate.
4. Subagent attempts to bypass a gate and is rejected.
5. Human approval advances a stage.
6. Material artifact change after approval invalidates the receipt.
7. Full fixture run advances through all selected stages with test-only human reviews.

Acceptance:

- `python -m pytest` covers the orchestrator loop.
- E2E logs show every stage transition and gate result.
- The orchestrator, not the subagent, owns all `workflow advance` calls.

### Phase 8 - Documentation

Effort: L-M

Update:

- `README.md`
- `docs/COMMANDS.md`
- V-cycle vigilance docs
- orchestrator agent instructions

Acceptance:

- A user can run the interactive path from `aimsun-psp`.
- Docs explain root selection, target path selection, and gate status.
- Docs state that test-fixture human reviews are not production approvals.

## Definition of Done

- Natural wording selects the correct capability and gate policy.
- The installed CLI gives useful diagnostics when run from the wrong root.
- The chat orchestrator always enters through modeller plan/route.
- Subagents receive gate-bound work orders and return lane receipts.
- Workflow state advances only through machine gates plus valid human review.
- E2E tests can drive the full gated flow with test-only human approval fixtures.
