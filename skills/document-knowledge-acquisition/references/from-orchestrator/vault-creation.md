# Vault Creation (Stage A / Wave C)

How the orchestrator stands up a governed knowledge vault before any acquisition
begins. This is the front end that the acquisition waves (Stage B) assume exists.

## Why a creation stage

Historically each mission vault started from an ad-hoc folder, which produced the
recurring gaps seen in the ADMobility and DRIEAT vaults: low/inconsistent front
matter, no `.gitignore` (generated artifacts and `.obsidian` state committed),
oversized notes, and restricted values pasted into notes. Wave C fixes those *once*,
at creation, from templates aligned to the downstream standard.

## Run it

```
python scripts/scaffold_vault.py --target <new_vault_dir> \
       --vault-name "<Mission Name>" --sensitivity restricted --prefix <PREFIX>
```

- `--target` may already contain `sources/` and/or `.obsidian/`; the scaffolder
  refuses to overwrite any *other* pre-existing content unless `--force`.
- `--prefix` is the entity-id prefix (e.g. `DRIEAT`, `ADHSME`). The generic graph
  builder auto-detects it; never hardcode it in tooling.
- `--sensitivity` defaults to `restricted`.

Then verify the gate:

```
python scripts/scaffold_vault.py --check <new_vault_dir>
```

## What it creates

Folder skeleton: `corpus/ data/ lanes/ curation/{board-packs,promotion}/
diataxis/{reference,explanations,how-to,tutorials}/ model-checks/ templates/`.

Root docs (instantiated from `references/templates/` with `{{VAULT_NAME}}`,
`{{SENSITIVITY}}`, `{{PREFIX}}`, `{{DATE}}` substitution): `HOME.md`, `HANDOFF.md`,
`plan.md`, `knowledge-graph-ontology.md`, `README.md`.

Per-type note templates copied into `<vault>/templates/` for the Wave 4 authoring
lanes: `note-reference`, `note-explanation`, `note-how-to`, `note-tutorial`.

Seeded (empty) curation control surface + CSV headers: `acquisition-ledger.md`
(with the GC verdict), `lane-status.md`, `conflict-register.md`, `decision-queue.md`,
`decision-record.md`, `promotion/G7-checklist.md`, `data/source-register.csv`,
`data/accepted-layer.csv`.

A `.gitignore` that keeps generated artifacts, `__pycache__`, and personal `.obsidian`
state out of version control.

## Alignment with `modelling-knowledge`

Every note template carries the controlled-vocabulary fields from
`modelling-knowledge/standards/knowledge-metadata-standard` (`status`, `type`,
`authority_level`, `sensitivity`) plus provenance (`source_anchor`) and the
restricted-handling fields (`derived_from_restricted`, `redaction_review`). Candidate
notes start `status: proposed` / `authority_level: evidence`; on promotion they map
1:1 onto the accepted profile (`status: accepted` / `authority_level: authoritative`)
with no field renaming. `promotion_target` records the intended accepted-layer path.

## Gate GC

See `gate-criteria.md`. GC must pass before Wave 0. It is mechanical: skeleton +
`.gitignore` + root docs present, every template parses and carries the four
controlled-vocabulary fields, sensitivity defaulted to `restricted`.
