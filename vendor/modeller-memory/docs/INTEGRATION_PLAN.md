# modeller-memory — Integration Plan

> **Status:** draft 2026-07-08, revised 2026-07-08 to the org-level orchestration decisions;
> restructured 2026-07-10 around the three ecosystem workflows this repo serves;
> **revised 2026-07-11 after antagonist review** (findings AM-01…AM-14) — subsystem scope
> narrowed, ownership contradictions resolved, build sequence re-sequenced (M0–M7);
> **revised 2026-07-12 after a cross-repo consistency pass** — stale "empty repo" claims
> corrected to on-disk reality, ADR-0005/`vault_doctor` folded into §4/§7, and cross-repo
> decision statuses (0005/0007) reconciled with `modelling-knowledge`'s 2026-07-12 antagonist
> direction review. See the *Cross-Repo Status & References* block below.
> Derived from a deep analysis of Testudo's memory architecture (ADR-0002 three-layer model)
> plus the stated goal for this repo.
> Source of the analysis: `AItlantis/Testudo` — see "Appendix A: what Testudo does".
>
> **Locked decisions (see [`../../docs/ORCHESTRATION.md`](../../docs/ORCHESTRATION.md)):** this repo is consumed by hosts
> as a **git subtree** (not a submodule) under `vendor/modeller-memory`; its install/doctor
> tooling is **Python** (an importable `modeller_memory` package), called by the host's
> `modeller` CLI; the upstream backends are **pinned+hashed and fetched at install
> time** (§6e), not vendored as source.
>
> **Revised product statement (post-review):** `modeller-memory` provides generated repository
> intelligence, scoped companion recall, and candidate-classification contracts. It never owns
> accepted knowledge, agent orchestration, source truth, or behavioural guardrails.

> **Current implementation note (2026-07-14):** the candidate classification runtime, candidate
> event ledger, and scoped in-memory companion provider are now built and tested. Older sections that
> describe the memory runtime as "not built" are historical build-sequence context and are superseded
> by this note plus `README.md`.

## Cross-Repo Status & References

This plan coordinates three repositories. The load-bearing cross-repo facts and their current
status (as of 2026-07-12) — kept here so no section below silently goes stale:

| Item | Owner | Current status | Reference |
|---|---|---|---|
| Local-agents / central-skills boundary | `modelling-knowledge` | accepted | [`modelling-knowledge/decisions/0001`](../../modelling-knowledge/decisions/0001-local-agents-central-skills.md) |
| Domain scope (only `domains/transport/` new) | `modelling-knowledge` | **accepted** | [`0005`](../../modelling-knowledge/decisions/0005-knowledge-vault-domain-scope.md) |
| Memory-promotion coordination (propose→transport→govern) | `modelling-knowledge` | **accepted as a coordination model**; content promotion remains gated on a real `MemoryCandidate` exercise and general N-2 proof (§3.1a) | [`0007`](../../modelling-knowledge/decisions/0007-memory-promotion-coordination.md), [ADR-0004](ADR/ADR-0004-vault-promotion-seam.md) |
| Memory-is-generated-recall / non-authority | `modelling-knowledge` | accepted (A.1.5) | [`0008`](../../modelling-knowledge/decisions/0008-authority-decisions-foundation.md) |
| Discovery-draft inbound contract (`source`=classifier / `owner`=writer) | `modelling-knowledge` | published standard | [`standards/discovery-draft-schema.md`](../../modelling-knowledge/standards/discovery-draft-schema.md) |
| Skill ownership (`memory-recon` exists; `memory-maintain` not yet) | `modeller-agents` | as stated (§3.1, §5) | [`memory-recon SKILL`](../../modeller-agents/.claude/plugins/modeller/skills/memory-recon/SKILL.md), [ADR-0002](ADR/ADR-0002-skill-ownership.md) |
| `vault_doctor` co-location (orthogonal tool, not a memory layer) | `modeller-memory` | **BUILT** (outside M0–M7) | [ADR-0005](ADR/ADR-0005-vault-doctor-colocation.md) |
| N-2: `authority_context` completeness/currency validator | coordination (partly `modeller-memory`) | **open** — AM-02 fence designed, not verified (§3.2) | [vault-alignment-plan, Antagonist Direction Review](../../modelling-knowledge/docs/dev/vault-alignment-plan.md) |
| N-3: CI import-guard "no memory runtime imports `tools/vault_doctor`" | `modeller-memory` | **SATISFIED** — enforced by `tests/test_import_guards.py` | [ADR-0005](ADR/ADR-0005-vault-doctor-colocation.md); vault-alignment-plan DR-6/N-3 |

**Cross-repo dependency (updated 2026-07-12):** `modeller-agents` has implemented the D3/D4/D5
routing conditions (`src/modeller/knowledge_packs.py`) including D5's parity check against current
`vault_doctor export-index` / `export-domains` output. `modelling-knowledge` now commits
`docs/dev/vault-index.json` and `docs/dev/knowledge-domains.json` as VA3 source artifacts; the
domain export carries per-domain `notes_digest` so a pack pins to its own domain's note entries
instead of the whole vault index. This is still a cross-repo Close-phase currency rule, not memory
runtime behavior, and is noted here because `vault_doctor` (the export producer) lives in this repo.
See
[`modeller-agents/docs/architecture/typed-packs-open-decisions.md`](../../modeller-agents/docs/architecture/typed-packs-open-decisions.md)
(D3–D6) and the vault's VA3.

**Historical state (updated 2026-07-12, superseded by the 2026-07-14 implementation note): early
scaffold before the memory runtime was built; one orthogonal *tool* existed.** What existed on disk:

- **Built and committed:** `pyproject.toml` (installable `modeller_memory` package), the five ADRs
  (0001–**0005**), the `docs/contracts/` and `schemas/` index READMEs, and
  **`src/modeller_memory/tools/vault_doctor/`** — a working 6-module vault-validation tool with a
  24-test suite and a `vault-doctor` CI workflow. `vault_doctor` is **not a memory-runtime layer**;
  it is host-agnostic tooling for `modelling-knowledge`, co-located here by decision **ADR-0005**,
  isolated under `tools/` and importing none of the memory runtime. It sits **outside** the M0–M7
  build sequence (see §4 and §7).
- **Historical not-yet-built list as of 2026-07-12:** the memory runtime under `src/modeller_memory/`
  (`adapters/`, `policy/`, `candidates/`, `integration/`, `mcp/`), the actual `docs/contracts/*.md`
  and `schemas/*.schema.json` (only index READMEs exist so far), `templates/`, `upstreams.lock.toml`,
  and `README.md`. This no longer describes the current package state.

Everything described below under the revised repo layout is historical plan context unless a
current status block says otherwise. The layout **no longer contains** `skills/` or `engine/guardrails/` — skills
are owned by `modeller-agents`, reuse guardrails by the agent method.

---

## 1. What this repo is

`modeller-memory` is a **reusable, embeddable memory subsystem** — vendored into any host repo
(first consumer: `modeller-agents`, later the `aimsun/*` repos) as a **git subtree** under the
known prefix `vendor/modeller-memory` (no `.gitmodules`; pins live in the host's `vendors.toml`
and are synced via `modeller sync`).

It packages **two** memory capabilities (revised — see §4 scope correction; the earlier draft
counted a third, agent-behaviour guardrails, which belong to `modeller-agents`, not memory —
AM-06):

| Capability | Upstream | Role here |
|---|---|---|
| **Repository intelligence (code graph)** | `codebase-memory-mcp` (pinned+hashed, §6e) | Structural graph of a host repo's source (modules/functions/callers/routes), **queried not read**, regenerated from Git, results stamped with a freshness state (§6a). |
| **Companion / semantic recall** | `mempalace` (candidate backend to *evaluate*, §6f) | Local-first, **scoped** conversation/decision memory. **Experimental and flag-gated** — activated only after the evaluation gates pass (M5→M7), never global-by-default (§6.2). Not "the main thing we ship first." |
| **Candidate-classification contracts** | *(ours)* | The `MemoryCandidate` propose seam (§3.1a), multi-axis record model (§6.1), policy, manifest, install/doctor. |

Not a memory capability, and **not in this repo**: reuse-first guardrails (`ponytail`) — owned by
`modeller-agents` as agent method/hooks (AM-06, ADR-0002). This repo may expose reuse *queries* the
guardrail consumes, but not the reuse *policy*.

**The load-bearing design rule (inherited from Testudo ADR-0002):** Git is the single source
of truth. Every memory layer is a *generated, non-authoritative index*. On any
graph-vs-repo disagreement, the repo wins and you re-index. Companion memory (mempalace) is
strictly tier 4 — context, never authority.

---

## 2. Retrieval query order (the contract every consumer inherits)

```
Step 1 — Repository intelligence (code graph, generated from Git; freshness-gated per §6a)   ← primary retrieval source (generated, non-authoritative)
Step 2 — The repository itself (grep / glob / read) when memory is down/stale                ← always-available fallback
Step 3 — Companion / conversation memory (mempalace, flag-gated; off until M5–M7)            ← secondary context only
```

*(Revised: "docs index" is dropped from v1 — only a code-graph / repository-structural index is
built. Markdown and accepted knowledge are read directly through `modeller-agents`, not through a
second generated index — AM-07, Option A.)*

This is memory's internal **query order** — an efficiency ordering, try the fastest generated
index first, fall back to the repo, consult companion memory last — not an **authority order**.
The authority order is the separate 4-tier ladder in §3.2 (source repo/Git → curated knowledge →
code graph → companion memory): Git and curated knowledge always outrank anything this repo
generates, including the code graph. Query order picks where to look first; authority order
decides who wins on disagreement. The two are not the same list and should not be numbered the
same way.

Reachability-first, never-block: probe the MCP server once at session start; degrade cleanly
to grep/read; maintenance is a **documented no-op** when a backend is absent. (This is the
single most important operational lesson from Testudo — the memory system must never make a
session fail.)

This query order is the cross-workflow contract: every consumer — Agents, Knowledge, Pipelines —
inherits the same three steps. §3 below works out what each workflow actually does with it.

---

## 3. Per-workflow integration matrix

`modeller-memory` is a peer subsystem, consumed by hosts, not a fourth authority. It serves
three ecosystem workflows — **Knowledge** (`modelling-knowledge`), **Agents**
(`modeller-agents`), **Pipelines** (`modeller-pipelines`) — and holds authority over none of
them.

| Workflow | What memory READS | What memory WRITES | Authority-ladder role | Ownership boundary (memory must NOT …) |
|---|---|---|---|---|
| **Knowledge** (`modelling-knowledge`) | Nothing — memory has no read path into the vault (D3's index scope is the host working tree plus the two `vendor/` prefixes only; `modelling-knowledge` is not vendored). It is the **consumer's** retrieval ladder, not memory, that ranks curated knowledge above memory's own layers. | Nothing. Memory never writes to the vault. | Curated knowledge is tier 2, above memory's tiers 3–4 (code graph, companion) — memory defers to it, not the reverse. | Must not write into the vault; must not be treated as authoritative over accepted knowledge; must not store accepted modelling concepts or replace repository maps (`modelling-knowledge`'s job); must not let its own domain taxonomy become a second write authority over vault-scoped subjects. |
| **Agents** (`modeller-agents`) | The host repo's source (for the code graph), companion memory, its own MCP tool surface. | Code-graph index (regenerated from Git), companion checkpoints/diary entries, runtime trace ingestion — all via the `memory-maintain` skill (planned, §5), never directly by agents. | Memory provides tiers 3–4 (code-graph + companion); tiers 1–2 (Git, curated knowledge) outrank it. | Must not be treated as authoritative over Git or curated knowledge; agents must never touch storage directly — only MCP tools, skills, and `memory-manifest.json`. |
| **Pipelines** (`modeller-pipelines`) | `vendor/modeller-pipelines` source, indexed as a live-source subtree for recon scope only. | Nothing pipeline-specific — only its own graph-index entries describing that subtree. | Feeds memory's own tier 3 (code graph) recon scope; no ladder role over contract content. | Must not interpret, own, or validate pipeline contracts, schemas, or execution as authoritative — indexing the files for recon scope is not the same as owning their meaning; that authority is `modeller-pipelines` at contract v1.0. |

### 3.1 Agents workflow (`modeller-agents`)

This is memory's live integration surface — the only workflow with a real, running touchpoint
today.

- **Two skills, asymmetric maturity — both owned by `modeller-agents`** (AM-03/04, ADR-0002).
  `memory-recon` (READ side) **already exists** in `modeller-agents` today —
  [`../../modeller-agents/.claude/plugins/modeller/skills/memory-recon/SKILL.md`](../../modeller-agents/.claude/plugins/modeller/skills/memory-recon/SKILL.md) —
  and is mapped in
  [`../../modeller-agents/src/modeller/route.py`](../../modeller-agents/src/modeller/route.py)'s
  `CAPABILITY_SKILLS` under both `"memory-recon"` and the alias `"recon"`. `memory-maintain`
  (maintain/WRITE side) does **not** exist in `modeller-agents` yet — it is **authored in
  `modeller-agents`** (not shipped from this repo; the earlier "ships from this repo" wording is
  withdrawn as an ownership conflict). This repo owns the **memory API/contracts** those two skills
  call (§5), not the skill bodies.
- **Where it sits in the flow.** `memory-recon` slots into step 6, "Query memory when
  available," of the 9-step routing flow in
  [`../../modeller-agents/method/workflows/baseline-flow.md`](../../modeller-agents/method/workflows/baseline-flow.md) —
  after knowledge retrieval (step 5, "Retrieve accepted knowledge") and before the
  source-boundary check (step 7).
- **Consumption surface.** MCP tools + the two skills + `memory-manifest.json` (commit-SHA
  staleness). Agents never touch storage or backend internals directly — enforced on the
  `modeller-agents` side by
  [`../../modeller-agents/docs/architecture/BOUNDARIES.md`](../../modeller-agents/docs/architecture/BOUNDARIES.md),
  which lists "Generated memory indexes or memory storage internals owned by `modeller-memory`"
  under what `modeller-agents` does **not** own. There is a second enablement surface alongside
  bundles: `memory-recon` is also listed in `central_skills` for three reference packs —
  `testudo.toml`, `aimsun-psp.toml`, and `modeller-pipelines.toml`
  (`../../modeller-agents/reference-packs/`) — so pack-level consumers pick it up independently
  of the bundle `skills[]` list.
- **Bundle enablement today.** `memory-recon` is currently listed in `skills[]` for the
  `testudo` and `aimsun-psp` bundles
  ([`../../modeller-agents/bundles/testudo.bundle.json`](../../modeller-agents/bundles/testudo.bundle.json),
  [`../../modeller-agents/bundles/aimsun-psp.bundle.json`](../../modeller-agents/bundles/aimsun-psp.bundle.json));
  extending it to further bundles is a host decision, made in `modeller-agents`, not here.
- **Vendored-subtree consumption.** `modeller-agents`'
  [`vendors.toml`](../../modeller-agents/vendors.toml) already carries a `modeller-memory`
  entry with `status = "planned"` and `pinned = ""` — the subtree has not been pulled and
  `vendor/modeller-memory` is empty. Its
  [`.mcp.json.example`](../../modeller-agents/.mcp.json.example) already registers a
  `modeller-memory` MCP server (`python -m modeller_memory.mcp`), ready to be dropped in once
  this repo exists to vendor.
- **Boundary.** Agents must never store memory as authority. `modeller-agents` enforces the
  complementary rule from its own side: memory storage internals are not its concern (see
  BOUNDARIES.md above) — the storage/authority split is symmetric across the seam.

### 3.1a Decision-capture → triage → promote (the orchestrator ↔ memory-agent loop)

> **Coordination model — accepted with content-promotion conditions (status corrected 2026-07-12)** (agreed in
> principle with `modelling-knowledge`; recorded as that repo's **accepted coordination-model** decision
> [`0007-memory-promotion-coordination`](../../modelling-knowledge/decisions/0007-memory-promotion-coordination.md),
> whose own verdict is accepted as a coordination model, with content promotion still gated on a real
> `MemoryCandidate` exercise and general N-2 authority-context proof. `modelling-knowledge`'s
> 2026-07-12 independent antagonist board closed the earlier DR-1 concern for the model itself.
> **M4 must not promote content through this path until those standing conditions are satisfied.**
> The design below is the ratified coordination shape, not proof that content promotion is operational.
> and mirrored in its `docs/dev/vault-optimisation-plan.md` **Phase H** / Authority Decision Order
> **A.2.11**). Decision 0007 rides accepted **0001** (agent placement) and accepted **0005** (domain
> scope / promotion-eligibility test). This subsection names a loop the earlier plan implied across
> §3.1, §3.2, and `memory-maintain` but never made explicit. It adds no new authority; it sequences
> one — and its final promotion-to-accepted step is gated on a live `MemoryCandidate` exercise plus
> general N-2 authority-context proof, matching decision 0007's standing conditions.

When a pipeline-building run produces an **idea or a decision**, that value must not be silently
dropped into whichever agent happens to hold it, nor written straight to durable knowledge. The
loop is **propose → transport → govern** — three owners, and *this repository owns only the first*:

```text
modeller-memory     PROPOSE    classify a candidate, return a MemoryCandidate   (NO vault I/O)
modeller-agents     TRANSPORT  validate the intended destination, invoke the vault intake seam
modelling-knowledge GOVERN     antagonist review → accept a discovery draft into inbox
```

The load-bearing correction (antagonist findings AM-01, AM-03, AM-04): **`modeller-memory` never
writes to the vault, and never contains the memory agent.** The subsystem *proposes*; a
`modeller-agents`-owned memory agent *transports*; `modelling-knowledge` *governs*. Splitting the
subsystem from the agent removes the earlier draft's two contradictions — a "no vault write path"
that later authorised inbox drafts, and a runtime actor whose home was ambiguous.

1. **Orchestrator (in `modeller-agents`) — captures, does not decide.** On producing an
   idea/decision, the orchestrator emits it as a structured **candidate record** (a workflow
   artifact carrying the gate's required `owner` / `status` / related-task-or-decision front
   matter, per `modeller-agents/docs/architecture/ARCHITECTURE_AND_WORKFLOW.md §6`). Crucially, it
   first **retrieves the accepted knowledge relevant to the candidate** (baseline-flow step 5,
   which precedes memory querying at step 6) and attaches it as an **`authority_context`** — the
   accepted-knowledge references, source-repository commit, and applicable decisions the candidate
   should be judged against.
2. **`modeller-memory` — classifies, returns a `MemoryCandidate` (no vault access).** The
   subsystem receives the candidate *plus* its `authority_context` and runs deterministic
   classification (`policy/classification.py`). It returns a typed `MemoryCandidate` with a
   recommended `target`, `classification`, `provenance`, `sensitivity`, and confidence. It reads
   **nothing** from the vault and writes **nothing** to it. Conflict detection is done **against
   the `authority_context` passed in** — not against an independent vault read path, which memory
   does not have and must not acquire in v1 (this resolves AM-02: memory cannot detect a
   contradiction against content it cannot access, so the orchestrator supplies the authoritative
   evidence). The classification outcomes are:
   - **ephemeral / session-project scoped** → recommend companion memory (tier 4, decay TTL) —
     lands in this repo's companion store, not the vault;
   - **durable-candidate** (passes 0005's "survives a from-scratch rewrite" test *and* does not
     conflict with any note in `authority_context`) → recommend `target: vault-inbox`;
   - **conflicts with an `authority_context` note** → recommend `target: discard` (or `flag`) with
     the conflicting ref cited; the vault wins.
3. **Memory agent (owned by `modeller-agents`) — transports.** The `modeller-agents`-owned memory
   agent validates the recommended destination against source-boundary and sensitivity rules, then
   — for a `vault-inbox` candidate — **performs the actual write** into
   `modelling-knowledge/inbox/discovery-drafts/`. The agent, not the subsystem, holds the inbox
   write. It invokes the `memory-maintain` skill, which **lives in `modeller-agents`** (see the
   skill-ownership correction below and ADR-0002).
4. **`modelling-knowledge` — governs.** Its existing inbox → review → antagonist → accepted
   lifecycle is the sole acceptance gate. The vault's Phase H makes `inbox/discovery-drafts/` a
   stable, schema-validated drop point (a `discovery-draft` front-matter contract + `vault_doctor`
   checks) so drafts are machine-checkable on arrival and can never masquerade as accepted.

> **`ponytail` is not part of this loop, and not part of this subsystem** (AM-06). Reuse-first
> guardrails are an *agent-behaviour* concern owned by `modeller-agents` (`method/guardrails/` or
> the plugin hooks), not a memory backend. `modeller-memory` may *expose* reuse-oriented queries
> (`find_existing_solution`, `find_related_decisions`, `find_previous_implementation`) that the
> guardrail consumes, but the policy "does this need to exist / can we reuse / write less code"
> belongs to the agent layer. See §6 (revised subsystem scope) and ADR-0002.

**Skill ownership — one source of truth (AM-03, AM-04).** Executable skills (`memory-recon`,
`memory-maintain`) are **owned by `modeller-agents`** under
`.claude/plugins/modeller/skills/`. `modeller-memory` owns the **technical API and contracts** the
skills call (`docs/contracts/`, `src/modeller_memory/`, `schemas/`) — *what* a memory operation
means and *how* it executes, not *how an agent uses it*. This repo does **not** ship a live
`SKILL.md`; at most it provides a clearly-labelled, non-executable `examples/skills/*.reference.md`.
Do not copy the same `SKILL.md` into two repositories.

**Two ratified boundary rules (the safety envelope):**

- **Timing — "capture now, promote later" (v1).** The capture + classify + transport half of this
  loop is v1 work (M4); **companion recall/write-back stays flag-off until M5–M7** per the revised
  build sequence (§7). So v1 exercises the **candidate → inbox-draft promotion path only**;
  standing companion recall activates later, behind evaluation gates. The promotion seam and the
  recall engine are sequenced separately.
- **Write scope — the subsystem writes no vault; the agent writes only the inbox.** `modeller-memory`
  writes only its own companion store and generated indexes. The `modeller-agents` memory agent may
  *draft* into `modelling-knowledge/inbox/` and nothing else in the vault — never accepted notes,
  maps, decisions, or the registry. Acceptance belongs to the antagonist board.

**What this subsection does *not* change:** it gives memory no read or write path into the vault
(both remain absent — §3.2), does not make companion memory an authority (still tier 4), and does
not re-decide 0005's scoping. It names the producer, the classify step, the transport owner, and
the timing of the promotion path that §3.2 already required — and corrects the ownership so no two
repositories claim the same skill or write path.

### 3.2 Knowledge workflow (`modelling-knowledge`)

Memory reads nothing from the vault — no read path exists or is planned (D3's index scope is
the host working tree plus the two `vendor/` prefixes; `modelling-knowledge` is not vendored).
What outranks memory here is not a read relationship but a **retrieval-ladder position**: in the
4-tier authority ladder that `modelling-knowledge`'s own architecture defines, curated knowledge
sits at tier 2 — above the generated code-graph (tier 3) and companion memory (tier 4) that this
repo owns:

```
1. Source repository files and Git history
2. Curated knowledge in modelling-knowledge
3. Generated code graph memory
4. Companion/session memory
```

*(quoted from [`../../modelling-knowledge/docs/architecture/tech-architecture.md`](../../modelling-knowledge/docs/architecture/tech-architecture.md))*
— "If memory disagrees with Git or curated knowledge, Git and curated knowledge win."

Memory never writes to the vault and is never authoritative over accepted knowledge. The same
document's working rule: "`modelling-knowledge` is the curated knowledge authority.
`modeller-memory` is generated recall, not truth." `modelling-knowledge`'s own
[`AGENTS.md`](../../modelling-knowledge/AGENTS.md) forbids its agents from "treat[ing]
generated memory as authoritative," and its
[`README.md`](../../modelling-knowledge/README.md) responsibility table records: "Memory
protocol implementation | No | Belongs in `modeller-memory`." Its
[`repository_maps/modeller-memory.md`](../../modelling-knowledge/repository_maps/modeller-memory.md)
entry for this repo is explicit in the same direction: "it will not be a source of truth for
accepted knowledge."

**The memory record model is memory-local, not vault-scope.** §6 below defines a **multi-axis
memory record** (kind × scope × durability × authority × status, replacing the earlier flat
`decision / project / calibration-fact / reference` list — AM-09). That model must stay
companion-memory context — tier 4 — and never drift into a second write authority over
transport-modelling knowledge. This is not a judgment call this repo gets to make:
`modelling-knowledge` decision
[`0005-knowledge-vault-domain-scope.md`](../../modelling-knowledge/decisions/0005-knowledge-vault-domain-scope.md)
has ruled that only `domains/transport/` is vault-scope, and named "memory" as a candidate
explicitly rejected — "Memory's durable specification is the `modeller-memory` baseline spec
(planned, work item W5). A `domains/memory/` note would create a second write authority over the
same subject the moment the baseline spec changes." This plan *is the seed of* that baseline spec.
**Status correction (2026-07-12):** 0005 is now `status: accepted` (not draft), but
`modelling-knowledge`'s antagonist direction review (DR-1) flagged the *lineage* of that acceptance
(self-authored) and commissioned an independent board pass. So this section's scoping — and M4's
(§7) — remains contingent, but for the current reason: 0005 is accepted-pending-independent-lineage-
confirmation, not draft (AM-10). If the independent board's confirmed ruling differs, re-check.

**Companion-fact transport rules.** Three rules keep the model from becoming a second write
authority in practice, not just in principle:
- **Promotion (compact, don't delete — AM-09).** A record whose `durability` reaches
  `promotion_candidate` and that passes 0005's governing test — it *survives a from-scratch
  rewrite* of every repository — is proposed (via the `MemoryCandidate` seam of §3.1a) for the
  vault inbox. On acceptance, the record is **not deleted**; it is compacted to a lightweight
  **promotion pointer** (`status: promoted`, `promoted_to: {note_id, note_path, decision_id}`),
  its retrieval priority drops to minimal, and the accepted vault note becomes the authority. This
  preserves the audit trail (which run produced it, which candidate was promoted) without keeping a
  competing body. Earlier drafts said "never retained as standing recall," which risked losing
  provenance — corrected here.
- **Conflict (resolved against `authority_context`, not an independent vault read — AM-02).** The
  subsystem has **no vault read path**. A candidate is checked for contradiction **only against the
  `authority_context` the orchestrator supplies** (accepted-knowledge refs + applicable decisions,
  attached at capture per §3.1a). On disagreement, the vault reference wins and the companion
  record is corrected, superseded, or discarded — never the vault. A future optimisation *may*
  allow the subsystem to read the vault's **metadata-only index** for conflict pre-checks, but that
  is not required for v1 and is not a general vault-retrieval capability.
  > **Open gap — N-2 (from `modelling-knowledge`'s 2026-07-12 antagonist review, finding DR-5).** This
  > fence is only as good as the `authority_context` the orchestrator supplies: nothing yet validates
  > that context is **complete** (didn't miss a relevant accepted note) or **current** (aligned with
  > vault HEAD). Memory can pass a candidate as "no conflict" simply because its input was incomplete.
  > **N-2** is a required cross-repo action assigned partly to `modeller-memory`: define a validator
  > for `authority_context` completeness/currency before M4's classification is trusted. Until N-2
  > exists, AM-02 is *designed* but not *verified* — treat the fence as provisional, not solved.
- **Decay.** Records with `durability: ephemeral | checkpoint` are session/project context, not
  durable knowledge — they expire (checkpoint TTL / project-close prune). Only records actually
  promoted to the vault (now pointers) persist as an audit trail.

§6 and M4/M5 (§7) reference this rule set rather than restating it.

### 3.3 Pipelines workflow (`modeller-pipelines`)

Memory's relationship to the Pipelines workflow is narrow: it **indexes**
`vendor/modeller-pipelines` as a live-source subtree for recon scope, per ORCHESTRATION D3 (one
index per working tree, including both vendored subtrees). `modeller-pipelines`'s own
[`docs/INTEGRATION_PLAN.md`](../../modeller-pipelines/docs/INTEGRATION_PLAN.md) records the
same relationship from its side: "`modeller-memory` indexes this repo's subtree as a
live-source subtree (recon scope)." There is a second, enablement-level touchpoint: `memory-recon`
is listed in `central_skills` for the `modeller-pipelines` reference pack itself
([`../../modeller-agents/reference-packs/modeller-pipelines.toml`](../../modeller-agents/reference-packs/modeller-pipelines.toml)),
alongside the `testudo` and `aimsun-psp` packs (§3.1) — so Pipelines-workflow agents pick up
`memory-recon` through the pack layer as well as the bundle layer.

Beyond indexing and that pack-level enablement, memory does not interpret, own, or validate the
pipeline contract, its schemas, or its conformance kit as authoritative — the code graph indexes
those files like any other source under `vendor/modeller-pipelines`, but graph-indexing them
confers no authority over their meaning. That authority belongs entirely to `modeller-pipelines`
at contract v1.0 (`contracts/`, the conformance kit, the reference template). The only other
touchpoint is indirect: companion memory (tier 4) may recall prior pipeline-work decisions
across sessions, the same way it recalls decisions from any other workflow — it is not a
pipelines-specific capability.

---

## 4. Revised subsystem scope and repo layout

> **Scope correction (antagonist findings AM-06, AM-07).** The earlier draft described three things
> as one subsystem: code intelligence, companion memory, and agent-behaviour guardrails. Only the
> first two are memory capabilities. **Reuse-first guardrails (ponytail) are an agent-method
> concern owned by `modeller-agents`, not a memory backend.** And the earlier "code graph + docs
> index" promise had only a code-graph implementation — so v1 ships a **repository structural
> index** (code graph) and drops the unbacked "docs index" from the contract; Markdown/accepted
> knowledge is read directly through `modeller-agents`, not through a second generated index (this
> is the lean Option A; a real `docs_index/` remains a possible later addition but is not in v1).

**Revised product statement.** `modeller-memory` provides **generated repository intelligence**,
**scoped companion recall**, and **candidate-classification contracts**. It never owns accepted
knowledge, agent orchestration, source truth, or behavioural guardrails.

**Two primary layers (not three):**

1. **Repository intelligence** — code graph, structural retrieval, freshness state.
2. **Companion memory** — session/project context, candidate capture, temporal recall, correction
   and decay.

*(The two memory **layers** below are planned — no `adapters/`, `policy/`, `candidates/`,
`integration/`, or `mcp/` runtime exists yet. What DOES exist is called out with `[BUILT]` in the
tree: the package scaffold, the five ADRs, and `src/modeller_memory/tools/vault_doctor/` — an
orthogonal tool (ADR-0005), not a memory layer. Notably absent, versus the earlier draft: `skills/`
and `engine/guardrails/` — skills live in `modeller-agents`, reuse guardrails live in the agent
method.)*

```
modeller-memory/
├── README.md
├── LICENSE
├── pyproject.toml
├── upstreams.lock.toml            # pinned + hashed + license + platform matrix (§ supply chain)
├── docs/
│   ├── INTEGRATION_PLAN.md        # this file
│   ├── architecture/
│   │   ├── memory-architecture.md
│   │   └── trust-and-authority.md
│   ├── contracts/                 # what memory operations mean / how they execute (this repo owns)
│   │   ├── query-contract.md
│   │   ├── candidate-contract.md
│   │   ├── health-contract.md
│   │   ├── manifest-contract.md
│   │   └── index-scope-contract.md
│   └── ADR/
│       ├── ADR-0001-generated-memory-layers.md         # [BUILT]
│       ├── ADR-0002-skill-ownership.md                 # [BUILT]
│       ├── ADR-0003-companion-store-isolation.md       # [BUILT]
│       ├── ADR-0004-vault-promotion-seam.md            # [BUILT]
│       └── ADR-0005-vault-doctor-colocation.md         # [BUILT] co-locates the tool below
├── schemas/
│   ├── memory-manifest.schema.json
│   ├── memory-record.schema.json      # multi-axis record (§6)
│   ├── memory-candidate.schema.json   # MemoryCandidate transport contract (§3.1a)
│   ├── memory-health.schema.json
│   └── index-scope.schema.json
├── src/modeller_memory/
│   ├── tools/                      # [BUILT] orthogonal tooling, NOT a memory layer (ADR-0005)
│   │   └── vault_doctor/           # [BUILT] host-agnostic vault validator/exporter for
│   │       │                       #   modelling-knowledge; read-only, --vault-path;
│   │       │                       #   imports no memory runtime module. Outside M0–M7.
│   │       ├── model.py · loader.py · checks.py · checks_inbox.py · export.py · cli.py
│   ├── adapters/                   # ↓ everything below here is PLANNED (memory runtime)
│   │   ├── code_graph.py           # codebase-memory-mcp wiring
│   │   └── companion.py            # mempalace wiring (experimental, flag-gated)
│   ├── policy/
│   │   ├── authority.py            # resolve conflict vs authority_context (no vault read)
│   │   ├── freshness.py            # fresh | stale | unavailable | incompatible
│   │   ├── classification.py       # candidate → kind/scope/durability/authority
│   │   ├── retention.py            # decay, correction, deletion, purge
│   │   └── sensitivity.py          # public/internal/restricted + scope fencing
│   ├── candidates/
│   │   ├── classify.py             # produce a MemoryCandidate
│   │   └── promote.py              # compact-to-pointer on acceptance
│   ├── integration/
│   │   ├── embed.py                # vendor/wire into a host (Python, no Node)
│   │   ├── doctor.py               # health/readiness levels (§ doctor)
│   │   └── manifest.py             # memory-manifest (pydantic)
│   └── mcp/
│       └── server.py
├── templates/
│   ├── memory-manifest.json
│   ├── index-scope.yml
│   └── mcp.json.example
├── tests/
│   ├── vault_doctor/               # [BUILT] fixtures + 24 tests for the tool above
│   ├── unit/ · contracts/ · integration/ · security/   # planned (memory runtime)
├── .github/workflows/
│   └── vault-doctor.yml            # [BUILT] CI scoped to tools/vault_doctor + tests/vault_doctor
└── examples/
    └── host-reference/             # non-executable skill/wiring examples only
```

---

## 5. Skill ownership and the memory API (AM-03, AM-04)

**One source of truth for skills: `modeller-agents`.** The executable skills `memory-recon` (READ)
and `memory-maintain` (WRITE/maintain) live under
`modeller-agents/.claude/plugins/modeller/skills/`. `memory-recon` already exists there today.
**This repository does not own or ship those skills** — the earlier draft's "this repo becomes the
packaged source of truth for the skills" is withdrawn as an ownership conflict.

**What this repo owns instead: the technical API and protocol the skills call** —
`docs/contracts/`, `src/modeller_memory/`, `schemas/`. The relationship:

```text
modeller-agents   owns  HOW AGENTS USE MEMORY   (memory-recon, memory-maintain skills; the memory agent)
modeller-memory   owns  WHAT MEMORY OPERATIONS MEAN AND HOW THEY EXECUTE   (query/candidate/health/manifest contracts, adapters)
```

The skills invoke the memory API through the MCP surface and the typed contracts. At most this repo
provides **non-executable** `examples/skills/*.reference.md` — labelled examples, never live skill
authority. **Do not copy the same `SKILL.md` into two repositories.**

**The API the skills consume (contract-level, not skill bodies):**

- **Query / recon side** (`query-contract.md`) — structural retrieval over the code graph:
  definitions, literal scoped code, caller/blast-radius, routes, architecture, change detection —
  each returning results **stamped with the freshness state** (§ freshness). Always scoped to
  live-source subtrees per the index-scope contract (archive-pollution was Testudo's #1 measured
  failure mode). Companion recall (`search` for prior rationale) is part of this contract but
  **flag-gated and off in v1**.
- **Maintain side** (`manifest-contract.md`) — `index_repository(mode=full|moderate|fast)` after
  merge/rebase/large refactor; runtime-trace ingestion for edges static analysis can't derive;
  staleness = repo-commit SHA in the manifest. Companion write-back (`checkpoint` / `diary_write`)
  is flag-gated and off in v1.
- **Candidate side** (`candidate-contract.md`) — `classify(candidate, authority_context) →
  MemoryCandidate` and `promote(candidate) → pointer`. This is the §3.1a propose seam. Memory
  returns a candidate; it never writes the vault.
- **Reuse-query side** (consumed by the agent guardrail, not owned as policy here) —
  `find_existing_solution`, `find_related_decisions`, `find_previous_implementation`. The queries
  live here; the reuse *policy* lives in `modeller-agents` (AM-06).

---

## 6. Companion memory: record model, isolation, and governance

This section replaces the earlier flat "domain taxonomy" (AM-09) and adds the isolation (AM-08)
and governance-operations (AM-11 privacy half) the earlier draft lacked.

### 6.1 Multi-axis record model (replaces the flat four-type list)

The earlier `decision / project / calibration-fact / reference` list conflated three independent
dimensions (knowledge type, scope, durability). A `calibration-fact` may be one-run-temporary,
project-valid, reusable, or superseded — the flat list cannot express that. Records carry
**orthogonal axes** (`schemas/memory-record.schema.json`):

```yaml
memory_record:
  id:
  kind:        [decision, observation, assumption, preference, issue, result, reference, candidate]
  scope:       [session, run, project, repository, ecosystem]
  durability:  [ephemeral, checkpoint, retained, promotion_candidate]
  authority:   [generated, user_asserted, source_verified, accepted_knowledge_reference]
  status:      [active, contradicted, superseded, expired, promoted, rejected]
  provenance:  { origin_run:, source_repository:, source_commit:, evidence_refs: [] }
  sensitivity: [public, internal, restricted]
  temporal:    { created_at:, last_confirmed_at:, expires_at: }
```

This is memory-local, tier 4, and — per 0005 — never a vault write authority. Promotion eligibility
is `durability: promotion_candidate` **and** the 0005 from-scratch-rewrite test, resolved against
the orchestrator-supplied `authority_context` (§3.2).

### 6.2 Store isolation is a security decision, not a default (AM-08)

A global companion store is convenient but can mix clients, projects, public/restricted repos, and
personal preferences. Global-by-default is **rejected**. Store topology:

```text
~/.modeller-memory/
├── stores/
│   ├── user/
│   ├── organizations/<organization-id>/
│   └── projects/<project-id>/
├── indexes/
└── config/
```

Every record carries `tenant_id`, `project_id`, `repository_id`, `sensitivity`, `visibility_scope`.
Retrieval **requires an explicit scope** — `memory.search(query, tenant_id=…, project_id=…,
allowed_sensitivity=[…])`. **Default behaviour with no explicit project/tenant scope returns no
companion results.** Unrestricted global semantic search is never the default. (See ADR-0003.)

### 6.3 Governance operations (AM-09, AM-11)

Decay alone is not governance. The companion layer must support:
`create · read · search · correct · supersede · expire · delete · export · purge-project ·
purge-tenant`, with policies for: retention by scope; user-requested deletion; project-close
pruning; correction of false memory; sensitivity up/downgrade; promotion trace (compact-to-pointer,
§3.2); storage-encryption decision; backups; crash recovery; lock/concurrency; and **sanitisation
of conversation material before it is written**.

### 6.4 What we still ADD over Testudo

1. **Activate mempalace as an experimental, flag-gated companion adapter** (Testudo deferred it) —
   scoped stores, the record model above, correction/deletion, retention, promotion pointers.
   **Not enabled globally; gated behind the evaluation gates (§ evaluation).**
2. **One-command embed** — `modeller_memory.embed()` (Python, no Node), invoked by the host's
   `modeller install`; fetches pinned+hashed backends, drops `.mcp.json.example`, patches hooks.
3. **A layered `doctor`/`readiness`** (§ doctor) — health *levels*, not a single reachable/absent
   bit, distinguishing healthy degradation from unsafe degradation (AM-12).

---

## 6a. Freshness gate before graph-first retrieval (AM-05)

Graph-first recon is efficient but a stale generated index can mislead. The earlier draft only
*represented* staleness (a SHA in the manifest); it never *required checking it before trusting
results*. Freshness is now a **mandatory gate**, part of the query contract:

```text
Session starts → read memory-manifest
  manifest missing              → graph unavailable   → repository directly (grep/glob/read)
  manifest.commit == HEAD       → graph fresh          → graph-first allowed (verify source before write)
  manifest.commit != HEAD       → graph stale          → graph advisory only; source read MANDATORY before any conclusion
  backend/schema unsupported    → graph incompatible   → disable graph until rebuilt
```

Every query result carries a `memory_state` block (`schemas/memory-health.schema.json`):

```yaml
memory_state:
  graph: { status: fresh|stale|unavailable|incompatible, indexed_commit:, current_commit:, indexed_at:, backend_version: }
```

The graph is a **navigational aid, never final authority** — even fresh, relevant source is
verified before a write. This distinction is part of the formal `query-contract.md`.

## 6b. Query order vs workflow order (AM-06 wording)

The query-order / authority-order split is correct but the *complete* cross-ecosystem order is
owned by the orchestrator, not by this repo. Stated precisely:

- **`modeller-memory` defines the internal ordering of memory-backed retrieval:**
  `fresh graph → repository fallback → companion (flag-gated)`.
- **`modeller-agents` defines the complete workflow order** in which knowledge, repository
  evidence, and memory are consulted:
  1. resolve task and source boundary; 2. retrieve accepted knowledge; 3. check memory
  health/freshness; 4. query fresh repository index; 5. verify against repository files; 6. query
  companion memory for prior rationale; 7. reconcile using authority order.

This repo must **not** publish step-list (1)–(7) as its own contract — accepted-knowledge retrieval
and source-boundary resolution are the orchestrator's, and step 2 preceding step 6 is exactly what
supplies the `authority_context` that makes conflict detection possible without a vault read path
(§3.1a, AM-02).

## 6c. Index-scope contract (AM-13)

"One index per working tree" needs an explicit inclusion policy or vendored/generated/archived/
private files pollute retrieval. `templates/index-scope.yml` (validated by
`schemas/index-scope.schema.json`):

```yaml
index_scope:
  root: "."
  include: ["src/**", "method/**", "vendor/modeller-memory/src/**", "vendor/modeller-pipelines/contracts/**"]
  exclude: [".git/**", ".venv/**", "node_modules/**", "dist/**", "build/**", "**/__pycache__/**",
            "vendor/**/tests/fixtures/**", "docs/archive/**", "inbox/**", "**/*.generated.*", ".memory/**"]
  subtree_roles:
    "vendor/modeller-memory":    { role: live-vendored-source }
    "vendor/modeller-pipelines": { role: contract-source }
```

Also defined by the contract: whether generated plugin files are indexed; duplicate-symbol handling
between source and generated copies; whether test code is indexed; whether restricted paths may be
indexed at all; project-id derivation; rename detection; and subtrees removed after a sync.
Archive pollution was already the #1 measured failure mode in the source inventory.

## 6d. Doctor and readiness semantics (AM-12)

A missing *optional* layer and a stale *required* layer are different states; "maintenance is a
no-op when absent" must not collapse them. Health **levels**:

```text
HEALTHY       all enabled layers reachable and fresh
DEGRADED      optional layer unavailable; safe fallback active
STALE         graph reachable but commit mismatch; source verification required
MISCONFIGURED enabled layer missing or invalid config
INCOMPATIBLE  backend/manifest schema unsupported
UNSAFE        scope/sensitivity violation or corrupt manifest
```

`python -m modeller_memory.doctor --json` emits per-layer `enabled/status/required`, plus
`safe_to_query`, `safe_to_write`, and `recommended_actions`. Three separated verbs:
**`doctor`** (health + config) · **`readiness`** (may a specific workflow safely run) ·
**`maintenance`** (refresh / re-index). Healthy degradation (`DEGRADED`) is distinct from unsafe
degradation (`STALE`/`UNSAFE`).

## 6e. Supply-chain pinning (AM-11)

"Pinned by version" is insufficient. `upstreams.lock.toml` records, per upstream: exact version,
immutable source, artifact `sha256`, license id + notice handling, supported-platform matrix,
runtime requirements, expected executable/module, health-check command, and rollback version:

```toml
[upstream.codebase-memory]
source = "github-release"; repository = "DeusData/codebase-memory-mcp"
version = "0.8.1"; asset = "…"; sha256 = "…"; license = "MIT"
supported_platforms = ["linux-x64", "windows-x64", "macos-arm64"]; verified_at = "…"

[upstream.mempalace]
source = "pypi"; package = "mempalace"; version = "…"; sha256 = "…"; license = "…"
```

Pins are based on **verified artifacts and hashes**, not a manually copied version string.
`mempalace` is a fast-moving project whose maintainers warn to use only the official GitHub repo,
official PyPI package, and official docs (impersonating domains have distributed malware) — so
provenance and checksum verification are mandatory, not optional. `ponytail` is MIT (reimplementation
is fine) but MIT notice/attribution is retained where implementation derives from it.

## 6f. Evaluation gates (AM-14)

The system must be shown to help before it is trusted or activated. **Code-graph evaluation:**
lookup latency, token reduction, definition-retrieval accuracy, caller/blast-radius accuracy,
stale-result rate, fallback frequency, index time, index size. **Companion-memory evaluation:**
useful-recall precision, false-memory rate, stale-memory rate, cross-project leakage rate,
promotion acceptance rate, correction/deletion success, added prompt tokens, session latency.

**Companion activation gate** — do not enable standing companion recall by default until, on the
test corpus:

```text
false authority rate      = 0
cross-project leakage      = 0
restricted-scope leakage   = 0
useful recall precision   ≥ agreed threshold
doctor correctly blocks stale/unsafe states
```

mempalace is a *candidate backend to evaluate*, not an architectural premise — independent analysis
notes some headline gains trace to verbatim storage + standard vector filtering rather than the
"memory palace" structure itself. Treat accordingly.

---

## 7. Revised build sequence (M0–M7)

Contracts and safety come before backends; the immediate knowledge-management value (candidate
capture → governed inbox handoff) is delivered at **M4, without waiting on mempalace**. Standing
companion recall is a **later, gate-activated** capability.

> **Orthogonal track — `vault_doctor` (not an M-milestone).** The `src/modeller_memory/tools/vault_doctor/`
> tool (ADR-0005) is **outside** this M0–M7 sequence: it is host-agnostic validation/export tooling
> for `modelling-knowledge`, co-located here for packaging convenience, not a memory-runtime layer.
> It shipped ahead of M1 (built + tested + CI'd) and does not gate, nor is gated by, any Mn. The
> cross-repo action it owed back — **N-3** (`modelling-knowledge`'s 2026-07-12 antagonist review:
> machine-enforce that no memory runtime module imports `tools/vault_doctor`) — is now **satisfied**
> by `tests/test_import_guards.py`, so ADR-0005's isolation is enforced, not just prose.

> **M0/M1 status (updated 2026-07-14):** candidate contracts and
> `schemas/memory-candidate.schema.json` are implemented; candidate classification, policy core,
> event-ledger evidence, and the scoped companion provider scaffold are built and tested. Remaining
> M0/M1 contracts and schemas are still pending, and M2-M7 remain future work unless stated in a
> current status block.

- **M0 — Decisions and contracts.** Before any implementation: ratify skill ownership (ADR-0002),
  the candidate transport seam and vault write boundary (ADR-0004), companion store isolation
  (ADR-0003), the memory-record schema, sensitivity model, upstream provenance policy, and
  doctor/readiness semantics. **Deliverables:** the four ADRs, the `docs/contracts/` documents, the
  `schemas/` JSON schemas. **→ unblocks everything; nothing implements before the contracts exist.**
- **M1 — Package and policy core (no external backends).** Pydantic models; authority policy
  (conflict vs `authority_context`); freshness state machine; scope/sensitivity policy; candidate
  classification; health-result model; test fixtures. A testable nucleus with zero upstreams.
- **M2 — Code-graph adapter.** Verified+hashed upstream pin; install adapter; index-scope
  enforcement; manifest; fresh/stale/unavailable/incompatible handling; query wrapper + freshness
  stamping; fallback guidance; contract tests. **No companion memory yet.**
- **M3 — Host integration and recon proof.** The `modeller-agents` `memory-recon` skill calls this
  repo's query contract → fresh graph or source fallback → structured evidence packet. Prove on one
  host working tree including vendored subtrees. **→ unblocks: Agents + Pipelines recon.**
- **M4 — Candidate triage and vault handoff (no mempalace).** Implement the propose→transport→govern
  promotion path: orchestrator candidate + `authority_context` → `classify()` → `MemoryCandidate` →
  `modeller-agents` memory agent transports → `modelling-knowledge` inbox contract. **This delivers
  the immediate knowledge-management requirement without semantic recall.** Its content-promotion
  step is gated on the live `MemoryCandidate` exercise and general N-2 proof recorded by decision 0007.
- **M5 — Companion-memory experimental adapter.** mempalace behind a feature flag: scoped stores,
  the record model (§6.1), correction/deletion, retention, project isolation (§6.2), retrieval
  evaluation (§6f), promotion pointers. **Not enabled globally.**
- **M6 — Operational hardening.** doctor/readiness integration; checksums + supply-chain
  verification; concurrency, recovery, and security tests; performance baselines; upgrade/rollback.
- **M7 — Controlled activation.** Enable companion recall for a single test project/repository
  **only after the M-evaluation gates (§6f) pass.**

---

## 8. Alignment with ORCHESTRATION.md

This plan does not re-decide anything the org-level document has already locked — it inherits.
Everything below traces a dependency in this plan back to the deciding section in
[`../../docs/ORCHESTRATION.md`](../../docs/ORCHESTRATION.md).

| This plan depends on … | Locked in ORCHESTRATION.md as … | Status here |
|---|---|---|
| Being consumed as a git subtree, not a submodule | **D1** (§9): subtree, `--squash`, `vendors.toml` manifest, `writable = false`, `modeller sync` the sole mutation path, `doctor` reconciles manifest ↔ split-SHA | Inherited as-is; not re-argued in this repo. |
| Being indexed as part of the host's working tree, not on its own | **D3** (§9): one index per working tree — `modeller-agents` indexes itself plus `vendor/modeller-memory` and `vendor/modeller-pipelines`; no federated multi-repo index in v1 | Inherited; this is why §3.3's indexing relationship to Pipelines is scoped the way it is. |
| Shipping install/doctor tooling as an importable Python package | §6.3: `embed()`/`doctor()` become Python, called by the host's `modeller` CLI | Inherited; drives §4's `src/modeller_memory/` layout. |
| The MCP runtime being a prebuilt binary, fetched at install | **O3** (§8): prebuilt (~269 MB), fetched by `modeller install`, never committed — recommended, not yet fully closed | Inherited direction; still open at the org level. |
| Where the companion-memory store lives | **O2** (§8): global `~/.modeller-memory/` recommended vs repo-local, flag-gated either way | **Refined by AM-08:** the store is *scoped* (user/org/project namespaces, §6.2, ADR-0003), never global-by-default; resolved at M5, not M3. |

---

## 9. Decisions — resolved & remaining (see `ORCHESTRATION.md` §8–§9)

**Resolved:**
- **Index scope → one index per *working tree*, not per repo.** In `modeller-agents`, index the
  host **including** `vendor/modeller-memory` and `vendor/modeller-pipelines` (one project id; the two
  `vendor/` prefixes declared as live-source subtrees in `references/modeller.md`). No federated
  multi-repo index in v1. `aimsun-psp` is a runtime backend (not vendored); it is indexed only in
  its own clone.

**Resolved by the 2026-07-11 antagonist review (ADRs at M0):**
- **Skill ownership** (AM-03/04, ADR-0002): executable skills live in `modeller-agents`; this repo
  owns the memory API/contracts. No `SKILL.md` is copied here.
- **Vault write boundary** (AM-01, ADR-0004): subsystem *proposes* a `MemoryCandidate`; the
  `modeller-agents` memory agent *transports* (writes the inbox); the vault *governs*. Memory writes
  no vault path.
- **Conflict detection** (AM-02): resolved against orchestrator-supplied `authority_context`, not an
  independent vault read.
- **Guardrail placement** (AM-06): `ponytail` is out of the memory subsystem; agent method owns it.
- **Docs-index** (AM-07): dropped from v1; code-graph / repository-structural index only.
- **Companion posture** (AM-14): experimental, flag-gated, evaluation-gated; not the first thing
  shipped and never global-by-default.

**Refined, resolved at M5 (was "input needed at M3"):**
- Companion-memory **store location + isolation** (ORCHESTRATION O2, refined by AM-08, ADR-0003):
  the store is **scoped** (`stores/user/`, `stores/organizations/<id>/`, `stores/projects/<id>/`).
  Global-by-default is rejected; retrieval requires an explicit tenant/project scope or returns
  nothing. Flag-gated regardless.

**Inherited direction, pending org-level closure (not re-decided here):**
- **MCP server runtime → prebuilt binary, fetched by `modeller install`, NEVER committed** — pending
  org-level closure of **O3** (ORCHESTRATION §8). Now paired with the AM-11 supply-chain requirement:
  whatever artifact is fetched must be hash-verified per `upstreams.lock.toml` (§6e).

---

## Appendix A: what Testudo actually does (reference)

- **Three layers, one ADR** (`docs/dev/architecture/adr/ADR-0002-memory-layer.md`): code memory LIVE, ponytail retained (hooks wired), mempalace deferred/never-activated.
- **No `MEMORY.md` record store, no typed memory files.** "Memory" = nodes/edges in a code
  graph, regenerated from source (~42k nodes / ~150k edges / 2,416 files for Testudo).
- **Storage off-repo:** SQLite graph under `~/.cache/codebase-memory-mcp/`; shareable
  `.codebase-memory/graph.db.zst`.
- **Planned-but-unbuilt in-repo layout** `.memory/` (manifest + code-graph.sqlite + docs-index.sqlite + vectors/ + reports/) — we adopt the manifest idea in `templates/`.
- **Zero application code touches memory** — entirely MCP + skills + hooks. Good: keeps the
  engine cleanly separable, which is exactly what makes it embeddable here.
- **Wiring:** `.mcp.json.example` (opt-in copy to `.mcp.json`) registers the MCP server
  project-wide; `.claude/settings.json` hooks run ponytail (guarded by `command -v node`, so
  graceful no-op). MCP servers load at session start and are **not** hot-reloaded — hence the
  one-probe reachability check.
