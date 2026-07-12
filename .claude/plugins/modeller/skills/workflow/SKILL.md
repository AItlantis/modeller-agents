---
name: workflow
description: Run a gated multi-step modelling-agent workflow from context to verification. Use when a task requires recon, planning, source-boundary checks, execution or proposal, review, and final reporting.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Workflow

Use this skill for non-trivial work that spans more than one step.

## Steps

1. Read the context envelope or task brief.
2. Run `orchestrate` to resolve the owning repository and central skill.
3. Run `memory-recon` if memory is available; continue without it if unavailable.
4. Run `source-boundary-check` before any write or backend invocation.
5. Produce a plan for sensitive, broad, or high-risk changes.
6. Run `antagonist-review` for cross-boundary plans.
7. Execute only inside the allowed write scope, or return a proposal.
8. Run `review` and the relevant repository verification commands.
9. Return a structured result with evidence, limitations, and next required action.

Repository-specific gates belong in reference packs.

