# Gate Criteria — GC, then G0 through G7

Compact reference for every wave gate: what must be true to pass, and how
a **conditional pass** differs from an outright pass. Full narrative per
wave: `wave-definitions.md`.

**GC** is the Stage-A creation gate; **G0–G7** are the Stage-B/C acquisition
and promotion gates. GC must pass before G0 (no vault to acquire into otherwise).

## The conditional-pass pattern

Two different things can make a gate not cleanly pass, and the orchestrator
must tell them apart:

| Pattern | What it means | Orchestrator action |
|---|---|---|
| **Integration mechanics incomplete** | Dedup, provenance-linking, candidate merging, or diff generation itself did not finish or found a real defect (broken link, duplicate ID, missing receipt). | Gate **fails**. Fix the integration step and re-run before proceeding. |
| **Human/model dependency outstanding** | Integration mechanics are fully complete, but the pass criterion depends on something only a human or the live model can supply (a board ruling, live-model verification, an owner sign-off, a source document that is itself incomplete). | Gate is a **conditional pass** — record it explicitly as such, name the exact external dependency, and get the knowledge owner to ratify proceeding to the next wave with the gap tracked as a decision, not silently cleared. |

A conditional pass is never silent: the gate report must say which specific
criterion is outstanding, why it is an external dependency and not an
integration defect, and who/what closes it (a named board, the live `.ang`
model, the knowledge owner).

## Gate table

| Gate | Wave | Pass conditions | Typical conditional-pass driver |
|---|---|---|---|
| **GC** | C | Folder skeleton created · `.gitignore` present · `HOME`/`HANDOFF`/`plan`/`knowledge-graph-ontology`/`README` instantiated from templates · every per-type note template under `templates/` parses and carries the standard's controlled-vocabulary fields (`status`,`type`,`authority_level`,`sensitivity`) · `sensitivity` defaulted to `restricted`. Checked via `scaffold_vault.py --check <vault>`. | — (GC is mechanical; should PASS or FAIL cleanly). |
| **G0** | 0 | All sources resolve (hash match) · no blocking provenance error · every matrix link resolves · JSON-LD parses · sensitivity recorded as `restricted` · baseline digest stored. | — (G0 is mechanical; should not conditional-pass) |
| **G1** | 1 | All lane receipts pass · every critical acceptance/remarks issue linked to ≥1 report claim · every candidate has provenance · duplicate IDs = 0 · unresolved ambiguities visible in decision queue. | A lane self-reports `fail` because its *source material* is genuinely incomplete/contested, not because acquisition was sloppy — externalise to conflict/decision registers, ratify conditional pass. |
| **G2** | 2 | Every pilot workflow step has inputs+outputs · every pilot rule executable or explicitly blocked · every required object resolved or in blocker list · all critical issues traceable · graph validation has no structural error. | Reconciliation is complete but certification needs Wave 3 human decisions, live-model access, or board-adopted formulas/thresholds — record as blocked-by-design, not failed. |
| **G3** | 3 | Pilot-critical decisions accepted · deferred items explicitly scoped out · open items narrow and flagged, none blocking reference authoring. | Rare — G3 is itself the human decision point; a clean pass is expected once boards rule. |
| *(Wave 4)* | 4 | No numbered gate. Per-lane: reference values link to evidence/decision; explanations add no new thresholds/names/steps; how-to guides carry all required sections. | Reference must complete before explanation/how-to starts — treat premature explanation/how-to authoring as a sequencing violation, not a gate to conditionally pass. |
| **G5** | 5 | All seven deterministic checks pass: (1) stable IDs unique, (2) every rule has ≥1 evidence edge, (3) every workflow step has input+output edges, (4) every object has a status, (5) every critical conflict resolved/monitored/deferred/contested-v2, (6) no accepted node linked to an unresolved critical contradiction, (7) JSON-LD byte-identical across two runs. | None — G5 is deterministic and should PASS or FAIL cleanly via `gate_check.py --gate G5`. |
| **G6** | 6 | Independent modeller reproduces the accepted workflow without undocumented expert help, within approved tolerances. Checked via `gate_check.py --gate G6`: how-to guides present, protocol authored, zero `contested-v2` decisions, all objects verified vs live model. | Blocked (not conditional) until a live `.ang` model and an uninvolved modeller are available — this is a hard blocker, not a pass with a named gap. |
| **G7** | 7 | (1) traceability chain complete (G5 pass) · (2) decisions recorded, no Major `contested-v2` outstanding · (3) reproduction passes (G6 pass) · (4) sensitivity explicitly approved · (5) graph + vault gates pass (`vault-doctor check` run) · (6) knowledge owner explicitly approves promotion. | All six must be literal passes — G7 has no conditional-pass mode. A partial state is reported `BLOCKED` with the exact outstanding item(s) named. |

## Using `gate_check.py`

```bash
python scripts/gate_check.py --vault <vault_dir> --gate G5
python scripts/gate_check.py --vault <vault_dir> --gate G6
python scripts/gate_check.py --vault <vault_dir> --gate G7
```

Deterministic and read-only; exits 0 on PASS, 1 on BLOCKED/FAIL. Use it as
the actual gate check for G5/G6/G7 rather than a narrative judgment — G0–G3
are integration-report judgments made by the orchestrator against the
criteria above, since they depend on lane receipts and human decisions that
predate the graph.
