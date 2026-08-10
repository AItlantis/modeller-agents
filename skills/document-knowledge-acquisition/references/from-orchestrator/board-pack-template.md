# Board Pack Template

How `ka-board-pack-prep` turns `curation/decision-queue.md` into per-board
decision packs for the Wave 3 human review boards. Agents prepare evidence;
only a human closes a decision.

## One pack per board

Group decisions by the board that owns them (Data, Network/model,
Calibration, Validation, project-acceptance, Knowledge). A pack lists every
decision routed to that board plus a load/blocking count, e.g.:

```markdown
# Wave 3 Board Pack — <Board Name>

| Decision | Blocking? |
|---|---|
| DEC-0001 | yes |
| DEC-0009 | no |
```

## Per-decision entry format

Every decision entry in a pack has exactly these fields, in this order:

```markdown
### <DEC-ID> — <short title>

**Question:** <the single decision the board must make, phrased as a question>

**Evidence — Side A:** <verbatim extract> (<source anchor>)
**Evidence — Side B:** <verbatim extract> (<source anchor>)
<add Side C, D... only if the conflict is genuinely 3+-way (e.g. a 3-way naming conflict)>

**Options:**
1. <option 1>
2. <option 2>
3. <write your own — free text>

**Agent recommendation (non-binding):** <one sentence, clearly marked non-binding>

**Decision:** _____________________
**Owner:** _____________________
**Date:** _____________________
```

- Both/all sides of the conflict are always shown **verbatim with anchors**
  — never paraphrased or pre-resolved. The pack must not nudge by omission.
- The agent recommendation is advisory only. Label it explicitly
  "non-binding" so a board cannot mistake it for a ruling.
- Leave **Decision / Owner / Date** blank. These are the only fields a human
  fills in.

## 🔴 model-required marker

If a decision cannot be settled without the live delivered model open (an
object name, parameter or existence check that only the `.ang` can answer),
mark it **🔴 MODEL** next to the decision ID in both the summary table and
the entry heading:

```markdown
### DEC-0010 🔴 MODEL — Canonical geometry-config name
```

This tells the board the decision is blocked on model access, not on
judgment — it should not be rushed to a guess.

## Sign-off protocol

1. A decision is `accepted` only when **Decision + Owner + Date** are all
   filled in the pack.
2. Decisions marked **🔴 MODEL** stay open until the live model has been
   consulted, regardless of how confident the board is without it.
3. Nothing in a board pack is accepted knowledge until sign-off — sensitivity
   stays at the project default (typically `restricted`) throughout.
4. Once a board signs off, the orchestrator (not the board, not a subagent)
   folds the accepted decision back into `curation/decision-record.md`, the
   affected registers (conflict, object-resolution, rule status), and
   re-assesses the relevant gate (G2 re-check or G3).
5. Deferred decisions are logged with an explicit "deferred — out of
   [pilot/current] scope" note, not silently dropped; they re-enter scope
   for later phases.
6. Open decisions needing one more input (an analysis, a missing figure) are
   carried forward with the exact missing input named — never left as a bare
   "TBD".

## README index

Maintain `curation/board-packs/README.md` as the index: how to use the
packs, the sign-off protocol (above, in short form), and a load table
mapping each pack to its board, decision count and blocking count — so the
orchestrator can see at a glance which boards gate the next wave.
