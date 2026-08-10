---
title: Obsidian Vault Linking
status: stable
last_updated: 2026-07-18
---

# Obsidian vault linking

The knowledge vault is an **Obsidian vault**: notes are cross-linked with `[[wikilinks]]`
so the graph view and backlinks work. Linking is applied by `scripts/obsidian_linkify.py`
as the **final step of every wave** (after integration writes/updates notes).

## What the linkifier does
- Scans every `*.md` in the vault for entity ids and links them to their canonical note:
  - `CR-*` → `[[conflict-register]]`
  - `DEC-*`, `DEC-VAL-*`, `ACC-*`, `R4V2-*` → `[[decision-record]]`
  - `RULE-*` / `DRIEAT-*-RULE-*` → `[[rules-formalized]]`
  - `DRIEAT-OBJ-*` → `[[object-resolution-register]]`
  - `DRIEAT-TERM-*` → `[[terminology-reconciled]]`
  - `STEP-*` → `[[workflow-step-register]]`
  - `ISSUE-*` → `[[decision-queue]]`
  - literal report filenames (e.g. `wave5-graph-report`) → linked where mentioned
- Appends an **idempotent** managed block to each note (between `OBSIDIAN:AUTO-LINKS`
  markers): a `## Related (auto-linked)` list of `[[links]]`, `#tags`
  (`#gate/G0..G7`, `#wave/0..7`, `#kind/...`), and a `[[HOME|↩ Vault index]]` backlink.
- (Re)generates `HOME.md` — the Map-of-Content hub grouping notes by governance,
  per-wave reports, registers, board packs, Diátaxis, and promotion.

## Conventions
- Obsidian resolves `[[note]]` by **basename**, so keep note basenames unique across the vault.
- The managed block is safe to re-run; it never touches body content or tables — it only
  rewrites the block between the markers. Hand-authored `[[links]]` in the body are preserved.
- Writes use temp-file + `os.replace` (this mount silently no-ops in-place rewrites).

## Run
```
python scripts/obsidian_linkify.py --vault <vault_dir>        # apply
python scripts/obsidian_linkify.py --vault <vault_dir> --dry-run
```
Run it at the end of Waves 1, 2, 4, 5 and 7 (any wave that writes notes), and after any
delta re-baseline, so the graph stays current.
