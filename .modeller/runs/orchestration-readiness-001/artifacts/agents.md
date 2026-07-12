---
workflow_id: modeller-agents-build
run_id: orchestration-readiness-001
artifact: agents
step: orchestration-design
status: complete
updated_by: architect
updated_at: 2026-07-10T07:25:50Z
---


# Agents

## Purpose

Specify agent authority and scope boundaries.
## Evidence

Evidence: agent layer uses orchestrator authority for central routing; subagents produce review/fix evidence but do not own gate status; local repository agents remain in source scope; agent authority is enforced in workflow artifacts through updated_by owner checks.
## Decisions Or Outputs

Output: agents accepted with agent, authority, and scope evidence.
## Verification

Verification: workflow tests cover wrong owner rejection and manual updated_by tampering.
