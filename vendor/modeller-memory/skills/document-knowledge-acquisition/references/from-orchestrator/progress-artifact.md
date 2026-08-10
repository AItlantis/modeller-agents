# Progress Artifact — Knowledge Vault Progression

A single visual that answers "where is this knowledge-acquisition run right now?"
without anyone reading eight curation reports. It renders the wave roadmap from
plan sections 5-14 (Wave 0 preflight through Wave 7 promotion) as 8 rows, each
coloured by state, with a legend and a one-line wrap-up.

Use it: at the top of a status update, pasted into an Obsidian note, or dropped
into a dashboard alongside `curation/lane-status.md`, which is its source of
truth. Regenerate it — do not hand-edit it — whenever `lane-status.md` changes.

## The 8 rows

One row per wave (matches `curation/lane-status.md`'s "Progress by wave" table
exactly, in order):

| # | Wave | What "complete" means |
|---|---|---|
| 0 | Preflight | package/source validation, Gate G0 |
| 1 | Acquisition | all Wave-1 source lanes returned receipts, Gate G1 |
| 2 | Reconciliation | terms/objects/workflow/rules/conflicts reconciled, Gate G2 |
| 3 | Decisions | board packs signed off, decision-record written, Gate G3 |
| 4 | Authoring | reference → explanation → how-to notes authored (status: proposed) |
| 5 | Graph validation | reviewed-layer graph built, 7 §12 checks pass, byte-identical rebuild, Gate G5 |
| 6 | Reproduction | independent modeller reproduces the pilot from the how-to guides, Gate G6 |
| 7 | Promotion | governed promotion package prepared and approved, Gate G7 |

## Legend and state rule

- **green (done)** — the wave's gate has passed and the row is closed.
- **amber (current)** — the first wave, in order, that is not complete. This is
  always exactly one row (or zero, if every wave is done) — it is the wave an
  orchestrator or reader should look at next.
- **grey (pending)** — every wave after the current one. A wave can have all its
  *prep* work finished (e.g. Wave 6/7 in this vault both say "prep done") and
  still be amber/grey rather than green — prep is not the same as the gate
  passing.

The state is derived mechanically from the **Status** column of
`curation/lane-status.md`'s wave table: the word "complete" (and not
"incomplete") means done; the first row without it is current; everything after
is pending. This means the visual can never silently disagree with the table —
if the table says a wave is blocked, the roadmap will show it amber/grey, not
green, no matter what a report elsewhere claims.

## Wrap-up line

The SVG's own `<desc>` and its bottom-left caption both carry a one-sentence
wrap-up, generated the same way every time:

```text
<N> of 8 waves complete; wave <k> (<label>) is current; <M> pending behind it.
```

(If every wave is complete, the wrap-up drops the "current"/"pending" clauses:
"8 of 8 waves complete.")

## Ready-to-use inline SVG

This is the exact output of `scripts/progress_svg.py --vault <this vault>`,
captured at the point this run had passed Wave 5 (Gate G5) with Wave 6
(reproduction) blocked on live `.ang` model access and an independent modeller —
see `curation/lane-status.md` for the underlying table this was generated from.
Regenerate rather than hand-edit when that file changes (see "Regenerating"
below).

Theme-awareness: every colour is a CSS custom property with a hard-coded
fallback (`var(--ka-color-done, #22c55e)` etc.), so the SVG adapts automatically
if the host page defines `--ka-color-done`, `--ka-color-current`,
`--ka-color-pending`, `--ka-color-spine`, `--ka-text`, `--ka-text-muted` and
`--ka-bg`, and falls back to a light-theme-safe palette (green/amber/grey on a
transparent background) if it does not. Accessibility: the root `<svg>` carries
`role="img"` plus a `<title>`/`<desc>` pair holding the same one-line wrap-up,
and every row has its own `<title>` tooltip with the full status text for that
wave.

```svg
<svg viewBox="0 0 640 444" width="640" height="444" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="ka-progress-title ka-progress-desc">
<title id="ka-progress-title">Knowledge vault wave progression</title>
<desc id="ka-progress-desc">6 of 8 waves complete; wave 6 (Reproduction) is current; 1 pending behind it.</desc>
<rect x="0" y="0" width="100%" height="100%" fill="var(--ka-bg, transparent)"/>
<line x1="40" y1="58.0" x2="40" y2="366.0" stroke="var(--ka-color-spine, #d1d5db)" stroke-width="2"/>
<g>
<title>Wave 0 — Preflight: complete</title>
<circle cx="40" cy="58.0" r="10" fill="var(--ka-color-done, #22c55e)"/>
<path d="M 36 58.0 l 3 3 l 6 -7" stroke="var(--ka-bg, #ffffff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="70" y="63.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 0: Preflight</text>
<text x="616" y="63.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-done-text, #14532d)">complete</text>
</g>
<g>
<title>Wave 1 — Acquisition: complete</title>
<circle cx="40" cy="102.0" r="10" fill="var(--ka-color-done, #22c55e)"/>
<path d="M 36 102.0 l 3 3 l 6 -7" stroke="var(--ka-bg, #ffffff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="70" y="107.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 1: Acquisition</text>
<text x="616" y="107.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-done-text, #14532d)">complete</text>
</g>
<g>
<title>Wave 2 — Reconciliation: complete</title>
<circle cx="40" cy="146.0" r="10" fill="var(--ka-color-done, #22c55e)"/>
<path d="M 36 146.0 l 3 3 l 6 -7" stroke="var(--ka-bg, #ffffff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="70" y="151.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 2: Reconciliation</text>
<text x="616" y="151.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-done-text, #14532d)">complete</text>
</g>
<g>
<title>Wave 3 — Decisions: complete — 22 accepted, 5 deferred, ~4 open</title>
<circle cx="40" cy="190.0" r="10" fill="var(--ka-color-done, #22c55e)"/>
<path d="M 36 190.0 l 3 3 l 6 -7" stroke="var(--ka-bg, #ffffff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="70" y="195.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 3: Decisions</text>
<text x="616" y="195.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-done-text, #14532d)">complete — 22 accepted, 5 deferred, ~4 open</text>
</g>
<g>
<title>Wave 4 — Authoring: complete — 24 notes `proposed`; tutorial deferred</title>
<circle cx="40" cy="234.0" r="10" fill="var(--ka-color-done, #22c55e)"/>
<path d="M 36 234.0 l 3 3 l 6 -7" stroke="var(--ka-bg, #ffffff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="70" y="239.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 4: Authoring</text>
<text x="616" y="239.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-done-text, #14532d)">complete — 24 notes `proposed`; tutorial deferred</text>
</g>
<g>
<title>Wave 5 — Graph validation: complete — 175 nodes/287 edges, 7/7 checks, byte-identical</title>
<circle cx="40" cy="278.0" r="10" fill="var(--ka-color-done, #22c55e)"/>
<path d="M 36 278.0 l 3 3 l 6 -7" stroke="var(--ka-bg, #ffffff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="70" y="283.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 5: Graph validation</text>
<text x="616" y="283.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-done-text, #14532d)">complete — 175 nodes/287 edges, 7/7 checks, byte-identical</text>
</g>
<g>
<title>Wave 6 — Reproduction: prep done — needs live `.ang` + independent modeller</title>
<circle cx="40" cy="322.0" r="17" fill="none" stroke="var(--ka-color-current, #f59e0b)" stroke-width="2" opacity="0.45"/>
<circle cx="40" cy="322.0" r="12" fill="var(--ka-color-current, #f59e0b)"/>
<text x="70" y="327.0" font-family="sans-serif" font-size="15" font-weight="600" fill="var(--ka-text, #1f2937)">Wave 6: Reproduction</text>
<text x="616" y="327.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-current-text, #78350f)">prep done — needs live `.ang` + independent modeller</text>
</g>
<g>
<title>Wave 7 — Promotion: prep done — needs G6 + owner approval</title>
<circle cx="40" cy="366.0" r="10" fill="var(--ka-color-pending, #9ca3af)"/>
<circle cx="40" cy="366.0" r="3" fill="var(--ka-bg, #ffffff)"/>
<text x="70" y="371.0" font-family="sans-serif" font-size="15" font-weight="400" fill="var(--ka-text, #1f2937)">Wave 7: Promotion</text>
<text x="616" y="371.0" font-family="sans-serif" font-size="12" text-anchor="end" fill="var(--ka-color-pending-text, #374151)">prep done — needs G6 + owner approval</text>
</g>
<circle cx="40" cy="406" r="6" fill="var(--ka-color-done, #22c55e)"/>
<text x="52" y="410" font-family="sans-serif" font-size="11" fill="var(--ka-text, #1f2937)">done</text>
<circle cx="130" cy="406" r="6" fill="var(--ka-color-current, #f59e0b)"/>
<text x="142" y="410" font-family="sans-serif" font-size="11" fill="var(--ka-text, #1f2937)">current</text>
<circle cx="220" cy="406" r="6" fill="var(--ka-color-pending, #9ca3af)"/>
<text x="232" y="410" font-family="sans-serif" font-size="11" fill="var(--ka-text, #1f2937)">pending</text>
<text x="40" y="432" font-family="sans-serif" font-size="12" font-style="italic" fill="var(--ka-text-muted, #6b7280)">6 of 8 waves complete; wave 6 (Reproduction) is current; 1 pending behind it.</text>
</svg>
```

## Regenerating

The visual is generated, never hand-edited, from `scripts/progress_svg.py`
(dependency-free, stdlib only — see that script for the generator). Two ways to
regenerate:

**From a live vault** (reads `curation/lane-status.md` directly and derives
done/current/pending automatically):

```bash
python scripts/progress_svg.py --vault /path/to/vault --out diataxis/graph/progress.svg
```

Omit `--out` to print the SVG to stdout instead of writing a file (useful for
piping straight into a chat response or another tool).

**Without a vault** (manual override — useful for a mock-up, a different
project's roadmap, or when `lane-status.md` doesn't exist yet):

```bash
python scripts/progress_svg.py \
  --states done,done,done,done,done,done,current,pending \
  --labels "Preflight,Acquisition,Reconciliation,Decisions,Authoring,Graph validation,Reproduction,Promotion" \
  --out progress.svg
```

`--states` always overrides vault parsing if both are given. If `--vault` is
given but `curation/lane-status.md` is missing or its table can't be parsed, the
script falls back to the 8 default wave labels, all marked pending, and prints a
warning to stderr rather than crashing or guessing.

Re-run after every change to `lane-status.md` (a new gate pass, a wave becoming
blocked, etc.) so the visual never drifts from the table it is derived from —
treat a stale progress SVG the same as a stale generated report: regenerate it,
don't patch it by hand.
