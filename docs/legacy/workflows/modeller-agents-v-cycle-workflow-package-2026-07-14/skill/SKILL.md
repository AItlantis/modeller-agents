---
name: v-cycle
description: Plan, execute, review, or continue work at any stage of a project V-cycle, with paired traceability and mandatory human-review gates. Use for opportunity, needs, specifications, architecture, detailed design, implementation, unit/integration/system tests, acceptance, deployment, operations/REX, or transversal project governance.
metadata:
  version: 0.1.0
  author: AItlantis
---

# V-Cycle

## Required input

```yaml
invocation_mode: full | stage | paired-review
requested_stage: <stage-id | null>
outcome: <user outcome>
project_context: <resolved context>
expected_artifacts: []
risk: low | medium | high
```

## Protocol

1. Preserve the request in the Companion brief.
2. Resolve the selected V-stage.
3. Recon upstream, paired and governance artifacts.
4. Identify missing, stale or contradictory prerequisites.
5. Build the stage plan and trace obligations.
6. Apply the vigilance policy and human-role requirements.
7. Obtain approval for mutating, external, decision-sensitive or contractual work.
8. Dispatch repository-local agents with bounded scopes.
9. Run machine gates.
10. Enter `awaiting-human-review`; never self-approve.
11. Validate receipt role and artifact digest.
12. Update trace links and downstream obligations.

## Hard rules

- AI proposals are not approvals.
- Never invent a missing upstream baseline.
- Human-only decisions remain human-only.
- Every ascending artifact links to the descending artifact it validates.
- Estimated gains are advisory until measured internally.
- Every deliverable discloses AI assistance.
