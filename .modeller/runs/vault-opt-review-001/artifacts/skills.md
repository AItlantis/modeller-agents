---
workflow_id: modeller-agents-build
run_id: vault-opt-review-001
artifact: skills
step: orchestration-design
status: complete
updated_by: architect
updated_at: 2026-07-11T21:21:28Z
---


# Skills

## Purpose

Record the completed skills artifact for workflow step orchestration-design.
## Evidence

Plugin skills discovered from the installed surface (python -m modeller.cli skills): antagonist-review, backend-align, backend-contract-check, backend-scaffold, memory-recon, orchestrate, pipeline-fix, pipeline-review, pipeline-smoke, review, source-boundary-check, workflow. Orchestrator execution proven end-to-end: routing a light context envelope (requested_capability: review, target_repository: modelling-knowledge) through 'modeller.cli route' returned ok:true, skill=review, bundle=modelling-knowledge, errors:[]. A first attempt using the wrong key (capability instead of requested_capability) was correctly REJECTED by the router (ok:false, unauthorized skill) - confirming the authorization/source-boundary guard works. This orchestration-design artifact was produced by the orchestrator incorporating raw evidence from the two sonnet subagents that audited the assessment (requirements + decisions streams); the skill/route facts above were verified by the orchestrator via the plugin CLI.
## Decisions Or Outputs

skill: review is the skill selected for a modelling-knowledge review task. trigger: a context envelope with requested_capability=review and target_repository=modelling-knowledge. verification: modeller.cli route returns ok:true with no errors; the source-boundary-check and consent_required:true guards remain in force; an unauthorized-skill envelope is rejected, proving the guard.
## Verification

Verification: artifact owner, required terms, evidence, and workflow gate were checked.
