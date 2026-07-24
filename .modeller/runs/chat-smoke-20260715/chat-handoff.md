# modeller orchestrator handoff

Use the `modeller:orchestrator` agent behavior for this session.

## User request

Create a brief.md and recon.md about aimsun-psp rendering_geh pipeline

## Current orchestration state

- status: awaiting-user-approval
- target_repository: aimsun-psp
- requested_capability: v-cycle
- workflow_family: v-cycle
- stage_id: project-governance
- run_id: chat-smoke-20260715
- context_envelope: C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents\.modeller\runs\chat-smoke-20260715\context-envelope.json
- subagent_work_order: C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents\.modeller\runs\chat-smoke-20260715\work-orders\project-governance-subagent.json

## Required behavior

1. Read the context envelope and subagent work order before doing repository-local work.
2. Report the selected intent, run id, current stage, gate policy, and current blockers to the human.
3. Wait for explicit human approval before dispatching subagents or mutating files.
4. Dispatch subagents only for the active run and current stage, using the generated work order as the contract.
5. Treat subagent output as raw evidence until a valid lane receipt is persisted and ingested.
6. Run the workflow gate after every lane receipt or artifact update.
7. Request human review before advancing a stage; do not self-approve a stage.
8. Advance only through `modeller.cli workflow advance` after the machine gate and human review pass.

## Workflow status

```text
workflow_family: v-cycle
run_id: chat-smoke-20260715
status: running
invocation_mode: stage
current_stage: project-governance (draft)
stages:
  - project-governance: draft review=missing
```

## Current gate

- ok: False
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/BRIEF.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/RECON.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/handoff.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/machine-evidence.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/stages/project-governance/decision-log.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/stages/project-governance/document-configuration-log.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/stages/project-governance/planning-baseline.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/stages/project-governance/risk-register.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/stages/project-governance/status-report.md
- blocker: artifact still contains TBD placeholder: .modeller/runs/chat-smoke-20260715/artifacts/workflow-plan.md
- blocker: missing complete subagent lane receipt for work order 'wo-685786984d94927b'
- blocker: human review receipt is required before stage advance

## Deterministic commands

```powershell
python -m modeller.cli route --root C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents --envelope C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents\.modeller\runs\chat-smoke-20260715\context-envelope.json --run-id chat-smoke-20260715
```
```powershell
python -m modeller.cli workflow --root C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents lane-receipt --work-order C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents\.modeller\runs\chat-smoke-20260715\work-orders\project-governance-subagent.json --receipt <lane-receipt.json>
```
```powershell
python -m modeller.cli workflow --root C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents check --run-id chat-smoke-20260715
```
```powershell
python -m modeller.cli workflow --root C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents request-review --run-id chat-smoke-20260715 --provider receipt-file --receipt <human-review.json>
```
```powershell
python -m modeller.cli workflow --root C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-agents advance --run-id chat-smoke-20260715
```
