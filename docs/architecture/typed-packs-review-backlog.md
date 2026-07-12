# Typed Packs & Knowledge Axis — Antagonist Review Backlog

Status: OPEN backlog. Date: 2026-07-10. Owner: modeller-agents.

This file is where antagonist / adversarial reviewers record findings against `typed-packs-knowledge-axis.md` before any of it is implemented. It mirrors the four review lanes used elsewhere in this repository (source boundary, evidence quality, sensitivity, architecture fit — see `antagonist-review/SKILL.md`), but adds axis targeting: every finding should be filed against one of the six knowledge axes (A1-A6) defined in the design doc, so feedback maps cleanly onto the section it attacks.

### A1 Routing (WHERE vs WHAT)

Review prompts:

- Can a free-string `intent.domains[]` value ever leak into `route.py` code or into the envelope JSON schema as a hard-coded name? Prove it can't, not just that the design says it shouldn't.
- If a request's `domains[]` and a bundle's `defaultKnowledge[]` both name knowledge packs, what actually happens today (in the proposal) if a reviewer disagrees with the assumed union-no-override semantics in D3 — where would that disagreement be caught before it ships?
- Does adding `intent.domains[]` require any change to `target_repository` resolution, or can the two axes be shown to be genuinely independent (i.e., can axis 2 be deleted with zero effect on axis 1's behavior)?
- What happens when `intent.domains[]` is present but `intent.target_repository` is missing or invalid — does axis 2 resolution run before or after axis 1's existing hard error path?

Findings:

| ID | Severity | Finding | Axis | Raised by | Status |
|---|---|---|---|---|---|
| — | — | — | A1 | — | — |

### A2 Pack typing (repo pack vs knowledge pack)

Review prompts:

- If `reference-packs/domains/_registry.toml` is the only file `route.py` reads to resolve a domain, what happens on a typo or unknown domain id — hard fail, silent drop, or something else? The design doc doesn't say; force a choice.
- What stops a knowledge pack's `[[notes]]` pointers from going stale relative to the `modelling-knowledge` content they point at, given knowledge packs are supposed to link, never copy?
- Is `kind = "repo"` actually back-compatible, or does every consumer of today's untyped reference packs (`validate_reference_pack` and callers) need to be shown, not assumed, to tolerate an unrecognized field being added?
- Who or what enforces that a knowledge pack never smuggles in repo-pack fields like `central_skills[]` or `[vendor]` — is `kind` load-bearing anywhere, or purely documentation?

Findings:

| ID | Severity | Finding | Axis | Raised by | Status |
|---|---|---|---|---|---|
| — | — | — | A2 | — | — |

### A3 Skill/method (domain_affinity)

Review prompts:

- For a skill declaring `domain_affinity = ["*"]`, can a reviewer reconstruct after the fact exactly which knowledge packs were loaded for a given run, or only that "all resolved packs were eligible"? If not reconstructable, is that acceptable per D4, or does it need a runtime log requirement added to the design?
- Does "skills stay generic, packs carry knowledge" hold up for a skill like `backend-align` that plausibly needs domain-specific logic, not just domain-specific facts — or does this axis quietly assume all domain variation is knowledge-shaped when some of it might be method-shaped?
- What enforces the intersection (`knowledge_packs ∩ domain_affinity`) at load time — is this a code change to every skill's loader, a shared helper, or unspecified?

Findings:

| ID | Severity | Finding | Axis | Raised by | Status |
|---|---|---|---|---|---|
| — | — | — | A3 | — | — |

### A4 Knowledge-vault scope

Review prompts:

- Does this design's knowledge-pack mechanism accidentally pre-empt or narrow the pending ADR 0005 ruling by baking in assumptions (e.g., about what counts as vault-scope) before that ADR lands?
- If ADR 0005 rules differently than the verdict table summarized here (transport-modelling=vault; testing/memory/ux/feature-development=owning repo), does anything in the knowledge-pack format need to change, or is the format genuinely scope-agnostic as claimed?
- Is the litmus test ("does the knowledge survive if every repo were rewritten from scratch?") actually applied anywhere in this design, or only quoted?

Findings:

| ID | Severity | Finding | Axis | Raised by | Status |
|---|---|---|---|---|---|
| — | — | — | A4 | — | — |

### A5 Scale-invariant

Review prompts:

- What enforces the "≤2 default knowledge packs per bundle" cap — code (a validator), review (a human checking bundle diffs), or nothing at all today? If nothing, is this cap a real invariant or an aspiration?
- Walk the zero-code extension checklist for adding "transport modelling" as a new domain end to end — does step (c) or (d) (updating a bundle's `defaultKnowledge[]` or a skill's `domain_affinity`) actually require touching a file that isn't itself pure data, e.g. does any skill body need a code change despite the claim that it wouldn't?
- If context loaded per request is meant to stay bounded, what is the actual upper bound once a request supplies an unbounded `intent.domains[]` list — is there any cap on axis 2 analogous to the axis-1 bundle cap, or can a single request request arbitrarily many knowledge packs?

Findings:

| ID | Severity | Finding | Axis | Raised by | Status |
|---|---|---|---|---|---|
| — | — | — | A5 | — | — |

### A6 Pre-existing debt

Review prompts:

- Does adding the five missing pipeline skills to `CAPABILITY_SKILLS` change any existing route outcome for envelopes that don't reference those skills — i.e., is this genuinely additive, or could it shift a fallback-to-`workflow` case that some caller currently depends on?
- If D2's bundle-key ambiguity is resolved by renaming `pipeline-backend` to a real repository id, what breaks for any envelope or test that currently targets `pipeline-backend` as a `target_repository` value?
- Is there evidence (tests, other callers) that anything currently relies on `pipeline-backend` resolving as it does today, such that "fixing" D2 is itself a breaking change requiring its own migration path?

Findings:

| ID | Severity | Finding | Axis | Raised by | Status |
|---|---|---|---|---|---|
| — | — | — | A6 | — | — |

## How to use

Reviewers append rows to the relevant axis's Findings table as they attack the design (ID, Severity, a one- or two-sentence Finding, the Axis it falls under, who Raised it, and a Status such as OPEN / DISPUTED / ACCEPTED / WONT-FIX). Any finding whose resolution implies an actual decision needs to be made should be promoted into `typed-packs-open-decisions.md` as a new D-numbered entry, with a back-reference to the finding ID here.
