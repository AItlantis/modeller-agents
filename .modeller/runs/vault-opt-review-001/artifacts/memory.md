---
workflow_id: modeller-agents-build
run_id: vault-opt-review-001
artifact: memory
step: orchestration-design
status: complete
updated_by: architect
updated_at: 2026-07-11T21:21:29Z
---


# Memory

## Purpose

Record the completed memory artifact for workflow step orchestration-design.
## Evidence

Memory seam per decision 0007 (draft) + 0008 A.1.5 + modeller-memory INTEGRATION_PLAN: modeller-memory is generated recall, non-authoritative, with NO vault read/write path. vault_doctor is hosted in modeller-memory as host-agnostic tooling (ADR-0005) that is read-only against the vault and not wired into memory's retrieval runtime. The propose->transport->govern loop: modeller-memory classifies a MemoryCandidate (no vault I/O); the modeller-agents memory agent transports a draft into inbox/discovery-drafts/; the antagonist board governs acceptance.
## Decisions Or Outputs

memory: generated recall only, tier 3-4, never authoritative over accepted knowledge. source: conflict is checked against an orchestrator-supplied authority_context, not an independent vault read. retrieval: memory-recon reads the host code graph (freshness-gated); accepted knowledge is retrieved directly through modeller-agents, ahead of memory in the authority ladder (Git > curated knowledge > code graph > companion).
## Verification

Verification: artifact owner, required terms, evidence, and workflow gate were checked.
