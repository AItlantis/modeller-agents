---
workflow_id: modeller-agents-build
run_id: vault-opt-review-001
artifact: prd
step: requirements
status: complete
updated_by: planner
updated_at: 2026-07-11T21:19:24Z
---


# Prd

## Purpose

Record the completed prd artifact for workflow step requirements.
## Evidence

Requirements analysis by a sonnet subagent working the assessment (vault-optimisation-assessment.md F-01..F-20 + findings CSV) considering vault-alignment-plan.md (VA0..VA8), verified against live vault files. Requirements grouped by the assessment's waves: Wave 0 authority (F-01/F-04/F-10/F-15), Wave 1 navigation (F-05/F-08/F-13), Wave 2 retrieval/metadata (F-02/F-03/F-09/F-12), Wave 3 automation (F-14/F-11), Wave 4 ontology (F-06/F-19/F-20), plus cross-cutting F-07/F-16/F-17/F-18 and alignment RVA.1-RVA.5. Verified current status: 16 findings RESOLVED (F-01,02,03,04,05,09,10,11,12,13,14,15,19,20 + F-16 for modeller-agents), 4 IN-GOVERNED/PARTIAL (F-06 registry-sole-authority not fully confirmed, F-07 0006 correctly marked provisional, F-08 link density improved 46/58->22/87 but semantic-connectivity test not fully verified, F-17/F-18 not independently re-checked). Key deviation flagged: F-14 vault_doctor resolved cross-repo in modeller-memory (ADR-0005 co-location) not in-vault - deliberate, keeps zero runtime code in the vault.
## Decisions Or Outputs

requirements: the assessment's findings map to five waves of requirements plus alignment VA0-VA5; each carries an acceptance test drawn from assessment section 15 and the CSV expected_state. acceptance: measurable targets - 100% accepted notes carry status+type+id; 0 competing entry points; 0 orphan authority docs; 0 notes without front matter; vault_doctor exits 0; restricted notes exposable:false; >=1 end-to-end lifecycle trail; deterministic index export. non-goals: no large ontology; no speculative domain subfolders; no runtime source in the vault; preserve registry-as-authority + append-only decisions + antagonist board + sparse taxonomy; knowledge packs reference by id and never copy vault knowledge; no cross-repo authority transfer; memory is non-authoritative (inbox-draft write only); no wildcard domain_affinity; no UX domain yet.
## Verification

Verification: artifact owner, required terms, evidence, and workflow gate were checked.
