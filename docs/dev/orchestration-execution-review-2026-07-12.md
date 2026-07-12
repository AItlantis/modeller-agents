---
title: Orchestration Execution Review + modeller-agents Improvements
status: active
type: process
owner: modeller-agents
authority_level: supporting
last_reviewed: 2026-07-12
---

# Orchestration Execution Review — 2026-07-12

**Context:** a real parallel-subagent orchestration was run across `modelling-knowledge`,
`modeller-memory`, and `modeller-agents` to close the remaining VA/decision gaps. This document
reviews how that execution actually went and turns the observations into ranked, actionable
improvements for `modeller-agents`. The best evidence here is not theory — it is what broke and
what recovered during this run.

---

## Part 1 — What the run did

| Lane | Repo | Work | Outcome |
|---|---|---|---|
| A | modelling-knowledge | VA3 `vault-index.json` + `knowledge-domains.json` export artifacts | ✅ committed, determinism proven |
| B | modelling-knowledge | Reconcile 0010 status, routability rollback→reactivation drift, N-1/N-2 wording | ✅ completed (recovered) |
| C | modelling-knowledge | Independent antagonist board pass on decisions 0006 & 0007 | ✅ 0006 accepted, 0007 accepted-as-coordination-model (recovered) |
| D | modeller-agents | This review + `sonnet`-default subagent policy | ✅ committed |

Foundation batches (previously done-but-uncommitted work in all three repos) were committed on
branches first, so the lanes ran against a clean, gate-green base.

## Part 2 — What actually happened during execution

1. **Isolation via git worktrees worked.** Three lanes writing the same repo (`modelling-knowledge`)
   ran without stepping on each other because each got its own worktree branched off the committed
   foundation. No merge conflicts on shared files were caused by *concurrent* edits.
2. **Two of three subagents died mid-run on an API spend limit**, not on the work. Both had
   effectively finished their edits but **neither had reached its gate-and-commit step**, so their
   output survived only as uncommitted worktree edits. The orchestrator recovered by finishing both
   lanes in the main loop and integrating them.
3. **A subagent shipped a gate-failing artifact.** Lane B set `status: coordination` on decision
   0010 — a value outside the controlled vocabulary — which the vault_doctor gate rejects. The
   subagent never caught it because it died before its own gate ran. The orchestrator caught it
   because it re-ran the gate during integration.
4. **A generated artifact went stale against later edits.** Lane A's `vault-index.json` was
   generated *before* Lanes B/C changed decision statuses (0006 proposed→accepted, 0007
   draft→accepted). The committed export therefore disagreed with the tree until it was regenerated
   on the integrated state. This is exactly the drift D5's parity check exists to catch — and it was
   caught only because integration re-ran the export and diffed it.
5. **Cross-validation emerged for free.** Lane A independently detected the same routability
   data-vs-comment mismatch that Lane B was assigned to fix, from the data side. Redundant lenses
   surfaced the same truth — a signal the finding is real.

## Part 3 — Ranked improvements for modeller-agents

Severity: **P0** blocks safe orchestration · **P1** high-value hardening · **P2** polish.

### P0-1 — The workflow gate must be the *subagent's* exit condition, not the orchestrator's

**Evidence:** two subagents died having produced edits but not run their gate; one shipped a
gate-failing value. The deterministic workflow gate (`method/workflows/*.workflow.json`,
`src/modeller/workflow.py`) exists, but nothing forces a *spawned worker* to pass it before its
output is considered done. Completion is currently trusted from the subagent's final message.

**Fix:** make "gate passed" a machine-checked artifact the orchestrator verifies, not a claim it
reads. A lane's output is `incomplete` until `modeller.cli workflow check` (or the relevant doctor)
exits 0 against that lane's branch. The orchestrator should run the gate itself on every returned
branch before integrating — treat the subagent's "done" as raw evidence (this is already the stated
principle in `docs/workflows/DETERMINISTIC_WORKFLOW.md § completion-authority`; it is not yet
*enforced* on the subagent-dispatch path).

### P0-2 — Generated artifacts need a currency/parity re-check after any dependent edit

**Evidence:** the stale `vault-index.json`. A generated export committed by one lane silently
disagreed with decision statuses changed by sibling lanes.

**Fix:** any workflow that both (a) edits note/decision metadata and (b) commits a generated export
must regenerate-and-diff the export as its final step, and fail if the committed artifact is not
byte-identical to a fresh generation on the final tree. This is the same recurring-parity condition
D5 already requires for knowledge packs (`typed-packs-open-decisions.md` D5 condition 1) — it should
be a general workflow rule, not a pack-only one.

### P1-1 — Default spawned subagents to `sonnet` (implemented this pass)

**Evidence + directive.** The orchestrator agent def declared `model: opus` and specified **no
model for the subagents it spawns**, so fan-out inherited the top tier by default. Implemented:
`.claude/plugins/modeller/agents/orchestrator.md` now states worker agents default to `sonnet`,
escalate to `opus` only for boundary-gating reasoning (adversarial verify, conflict resolution,
design trade-off), and `haiku` for mechanical recon — with the chosen tier stated per spawn brief.

### P1-2 — Make readiness recover-forward, not just report blockers

**Evidence:** `doctor --strict` correctly enumerates its blockers (draft reference packs,
planned/unpinned `modeller-memory` + `modeller-pipelines` vendors, sibling-schema fallback) but
there is no guided path from "here are 8 blockers" to "here is the ordered sequence to clear them."

**Fix:** add a `modeller.cli readiness --plan` mode that emits the ordered remediation sequence
(pin vendors → vendor schemas → promote packs after their review gate → activate backend after
smoke) with each step's precondition, so strict readiness becomes a runbook, not just a verdict.

### P1-3 — Reconcile the `modeller_agents` vs `modeller` package-name confusion

**Evidence:** handoff §5.L records `python -m modeller_agents.cli doctor` as failing ("not an
importable package; the importable package is `modeller`"). In the current repo, `modeller_agents`
*does* import and its `cli doctor` returns `ok: true`. Either the defect was fixed and the handoff
is stale, or the black-box test hit a different installed root. Two CLI entrypoints
(`modeller` and `modeller_agents`) for one tool is a standing confusion.

**Fix:** pick one canonical module name, alias the other with a deprecation note, and update the
black-box doc so the recorded state matches reality.

### P2-1 — Split the two largest modules

**Evidence:** `doctor.py` (744 LOC) and `knowledge_packs.py` (574 LOC) carry most of the growth
and the most conditional logic (budget contract, affinity, parity, supersession all live in the
latter). Not a bug, but the two files where a regression is most likely to hide.

**Fix:** extract the knowledge-pack eligibility/parity rules into a dedicated `eligibility` module
that both the pack path and (eventually) the shared N-1 conformance fixture import — which also
directly serves the open N-1 need (one eligibility implementation, consumed by both doctors).

### P2-2 — Orchestrator briefs should carry a standard boilerplate

**Evidence:** each lane brief had to independently re-state "do not push", "do not edit other
repos", "run the gate before commit", "commit on your branch". Two prior incidents in project
memory (unauthorized commit; destructive remote action) trace to briefs that under-specified
exactly these boundaries.

**Fix:** ship a spawn-brief template in `method/templates/` with the non-negotiable boundary block
pre-filled (write scope, push policy, gate-before-done, per-brief model tier), so no lane can be
dispatched without it.

## Part 4 — Net assessment

The architecture and tooling are sound: worktree isolation, the deterministic gate, and the
export/parity machinery all did their jobs *when they ran*. Every failure this session was a
**seam** failure — work that finished but wasn't gated, an artifact that wasn't re-checked for
currency, a default tier that was never set — not a logic failure. The P0 items close those seams;
the rest is hardening. The single highest-leverage change is **P0-1**: make the gate the
subagent's own exit condition so a dead or over-confident worker can never present ungated work as
done.
