# Delta Re-baseline Procedure

What to do when a **revised version of a source document arrives while
acquisition is in progress** — after Wave 1 has already run against the
original, possibly after Wave 4 authoring has started. This is a scoped
sub-wave, never a full re-run.

## When to trigger it

- A new version of a source document is delivered (different SHA256, real
  content churn — not a typo fix).
- It arrives after the affected source's Wave 1 lane has already produced
  candidates that downstream lanes/waves depend on.

## When NOT to trigger it

- The revision is cosmetic (same SHA256-equivalent content, formatting
  only) — log it in the ledger, no re-acquisition needed.
- The revision only affects material already deferred out of the current
  scope (e.g. a future-horizon section outside the pilot) — log it, defer
  the delta too.

## Do NOT do a full re-run

Never re-dispatch all Wave 1 lanes because one source changed. Scope the
delta to the single affected source. A full re-run wastes the acquisition
already done on unaffected sources and re-opens settled decisions that
never needed to move.

## Where to insert it

Insert the delta re-baseline **at the nearest safe wave boundary before the
next artifact that must run against the final source set**. In practice
that is almost always the **Wave 4 → Wave 5 boundary**: Wave 5's graph
rebuild and Wave 6's reproduction both need the final corpus, and if Wave 4
authoring has already finished, there is no in-flight lane to disrupt by
inserting the delta now. Inserting it later forces a Wave 5/6 redo;
inserting it earlier (mid-Wave-4) risks touching notes that are still being
authored.

## Procedure

1. **Hash + register the revision.** Record the new SHA256 alongside the
   original in the source register; keep the original for provenance/audit
   (do not delete or overwrite it).
2. **Re-run acquisition scoped to only this source**, diffing against the
   existing candidates for it: classify each prior candidate as
   unchanged / changed / removed, and each new passage as a new candidate.
   Use a dedicated lane ID namespace for the delta (e.g. `KA-<SOURCE>-V2-DELTA`)
   so IDs never collide with the v1 lane's namespace.
3. **Check for previously-unextractable content now recoverable** — e.g. a
   formula that only exists in v2, or an embedded image/equation object
   worth an OMML/vector check.
4. **Triage every new reviewer comment** into the issue matrix and
   `decision-queue.md`. Some new comments will reopen a decision the boards
   already ruled on; some will close an existing open item.
5. **Refresh downstream linkage.** If other lanes (e.g. a final-remarks
   review) challenged specific anchors in the original version, check
   whether those anchors moved or were removed in the revision.
6. **Produce a note-upgrade punch list.** Any Diátaxis note currently marked
   `gap`, `reconstructed` or `PENDING(<id>)` because the original source was
   silent should be flagged for upgrade to source-backed once the revision
   is integrated.
7. **Hold the write-back matrix for contested items.** Any decision the
   revision reopens must be marked `contested-v2` (not silently reverted to
   its old value, and not silently kept at its old accepted value) in the
   Wave 5 write-back overlay, pending a fresh board ruling. `contested-v2`
   items block G6/G7 (see `gate-criteria.md`) until re-ruled.

## Worked example — R4 v2 (calibration report revision)

A revised calibration report (`R04_Calage_v2`) arrived after Wave 4
authoring had finished (all notes already `status: proposed`). Delta scope:

- **Provenance:** v2 SHA256 differed from v1; ~50% paragraph churn, +47 new
  client comments; both versions kept in the register.
- **What it closed:** v2 added the previously-missing 6-step
  methodology/workflow section — exactly the gap that had made the Wave 1
  workflow lane self-report `fail`. This let several how-to steps marked
  "reconstructed/gap" be upgraded to source-backed, and confirmed several
  board decisions already taken (single static assignment, warm-up
  duration/construction method, conservation-gap trend).
- **What it reopened:** four previously-accepted or open items were
  contradicted by new v2 evidence and had to be marked `contested-v2`
  pending a fresh ruling: a static-adjustment step ordering (new comment
  reversed the accepted order), a validation-metric formula (v2 showed a
  normalised-percentage form where the accepted formula was an absolute
  form), a calibration parameter (a new fourth candidate value appeared),
  and a pair of assignment parameters (new path-count/gap/interval values
  diverged further from the accepted figures).
- **New evidence not yet captured anywhere:** the 47 new comments became new
  issue-matrix rows and decision-queue items, separate from the reopened
  four.
- **Timing decision:** integrate the delta *before* Wave 5's graph rebuild
  and well before Wave 6 reproduction — both need to run against the final
  source set, and redoing them after would cost far more than the scoped
  delta lane itself.
- **Outcome recorded in the write-back overlay:** the four reopened items
  were marked `contested-v2` (not reverted, not silently kept accepted) and
  carried into the Wave 5 graph as such — G5's deterministic checks still
  passed because none of the four were in the critical-conflict tier and
  none carried an `accepted` status while unresolved. They remained a named
  blocker for G7 promotion until re-ruled.

This example is the reference pattern: close gaps cheaply where the
revision agrees with what was already decided, but never silently overwrite
a decision the revision contradicts — always downgrade it to `contested-v2`
and route it back through the board.
