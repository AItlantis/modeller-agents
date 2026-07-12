---
workflow_id: modeller-agents-build
run_id: vault-opt-review-001
artifact: decisions
step: requirements
status: complete
updated_by: planner
updated_at: 2026-07-11T21:18:05Z
---


# Decisions

## Purpose

Record the completed decisions artifact for workflow step requirements.
## Evidence

Decisions analysis by a sonnet subagent working the assessment (vault-optimisation-assessment.md sections 11/12/13) considering vault-alignment-plan.md, verified against the actual decision files 0001-0010 + decisions-index.md. Accepted: 0001 (local agents/central skills), 0002 (aperta public/private split), 0003 (script-base ownership), 0004 (PSP boundary, sensitivity normalized to restricted/exposable:false - resolves assessment F-01/F-15), 0005 (domain scope, ratified 2026-07-11, only transport authorized), 0008 (authority foundation), 0009 (VA0 vault-side seam). Rejected (per 0005 + assessment section 12): domains/testing, domains/memory, domains/feature-dev, a large ontology, speculative subfolders, runtime source in the vault, transport-validation as a separate domain. Pending: 0006 (proposed, OSM boundary, antagonist board not yet run - assessment F-07 still open), 0007 (draft, memory promotion loop), 0010 (coordination, D3-D6 pending in modeller-agents).
## Decisions Or Outputs

Accepted decisions ratify the vault authority + seam foundation and resolve assessment findings F-01/F-04/F-05/F-15. Rejected items enforce the sparse-ontology non-goals. Pending decisions (0006 proposed, 0007 draft, 0010 coordination) remain governed and are not cited as accepted. Boundary rules that must hold: modelling-knowledge owns accepted knowledge + note ids + metadata + domain registry + sensitivity + vault index; modeller-agents owns pack schema/routing/skill-affinity and must not decide vault epistemic status; modeller-memory is generated recall with no vault read/write path (inbox-draft write only, via the modeller-agents memory agent); knowledge packs reference by id and never copy vault knowledge; sensitivity fencing precedes routing (restricted non-exposable); conflicts are reported not silently resolved. Residual: 0008/0009 carry antagonist-review status Pending - a consolidated board pass is outstanding.
## Verification

Verification: artifact owner, required terms, evidence, and workflow gate were checked.
