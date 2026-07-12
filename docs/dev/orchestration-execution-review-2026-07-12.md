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

**Observed for real at Close (2026-07-12).** When the vault decision changes (0006/0007 statuses)
landed on the vault's `main`, the vault **index digest** moved (`bf679a17…` → `8b1c8114…`) while the
**domains digest** stayed put (accessibility content unchanged). The `modeller-agents` D5 parity
check then correctly failed 6 tests: `reference-packs/domains/accessibility.toml` was pinned to the
old `source_index_digest`. The check did its job — it caught genuine cross-repo drift that no single
repo's gate would have seen. Fix applied: the orchestrator re-pinned the pack's `source_index_digest`
to the current export at Close and re-ran the gate (60 passed). This is the strongest argument for
P0-2 and for making export-currency an explicit Close-phase step: **a whole-index digest couples
every pack to unrelated vault edits.** Follow-up worth considering — scope the pack's parity to the
digest of *its own domain's notes* (the stable `source_domains_digest` already exists and did not
move) so unrelated decision edits don't invalidate every pack.

### P1-1 — Codified orchestration protocol: phase→tier + orchestrator-owns-git (implemented this pass)

**Evidence + directive.** The orchestrator agent def declared `model: opus` and specified **no
model for the subagents it spawns**, so fan-out inherited the top tier by default; and there was no
rule stopping a worker from committing (the two prior git incidents in project memory both trace to
workers doing their own git). Implemented in `.claude/plugins/modeller/agents/orchestrator.md` as a
full **Orchestration protocol**:

- **Fixed phase→tier mapping:** recon = `haiku`; planning = `sonnet` subagents + orchestrator on
  `opus`; implementation = `sonnet` only (no escalation); then documentation + handoff; then close.
- **Orchestrator owns all git.** Subagents are no-git workers — they receive a prepared worktree and
  a scope, return their edits, and never branch/stage/commit/push. Every git action, and every gate
  before a commit, is the orchestrator's at the Close phase.
- The only sanctioned escalation is a single adversarial-verify/conflict-resolution subagent raised
  to `opus` when its verdict gates a boundary — justified in the brief.

This directly removes the failure mode this session hit: workers died at their own gate-and-commit
step. Under the protocol they would simply have returned edits for the orchestrator to gate and
commit.

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
pre-filled (write scope, **no git**, model tier), so no lane can be dispatched without it.
**Partly done:** the orchestrator def (P1-1) now *mandates* that block in every brief (write scope,
no-git, fixed tier); the reusable `method/templates/` file remains the follow-up so the block is
copy-paste rather than restated each time.

## Part 4 — Net assessment

The architecture and tooling are sound: worktree isolation, the deterministic gate, and the
export/parity machinery all did their jobs *when they ran*. Every failure this session was a
**seam** failure — work that finished but wasn't gated, an artifact that wasn't re-checked for
currency, a default tier that was never set — not a logic failure. The P0 items close those seams;
the rest is hardening. The single highest-leverage change is **P0-1**: make the gate the
subagent's own exit condition so a dead or over-confident worker can never present ungated work as
done.
