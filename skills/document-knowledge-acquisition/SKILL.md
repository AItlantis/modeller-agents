---
name: document-knowledge-acquisition
description: Build governed knowledge-acquisition packages from document corpora, especially DOCX/PDF report sets that must be converted to Markdown, evidence matrices, traceability files, graph exports, and discovery drafts for modelling-knowledge. Use when preparing project reports, audits, manuals, comments, tables, figures, or reviewer remarks for curated knowledge promotion.
---

# Document Knowledge Acquisition

## Core Workflow

1. Identify the source-of-truth boundary before writing.
   - Raw project documents are evidence, not accepted knowledge.
   - `modelling-knowledge` receives standardized evidence packages and discovery drafts.
   - Tooling and repeatable validators live in `modeller-memory`.

2. Stage documents outside the target vault.
   - Preserve original filenames and hashes.
   - Convert every document to Markdown with stable paragraph, section, table and comment anchors.
   - Extract tables, embedded media, comments and links into separate files.

3. Generate acquisition references.
   - `source-register`
   - `section-matrix`
   - `evidence-matrix`
   - `rule-matrix`
   - `issue-matrix`
   - `workflow-matrix`
   - `model-object-matrix`
   - `terminology-matrix`
   - `comment-matrix`
   - `traceability-matrix`
   - graph nodes, edges and JSON-LD

4. Install into `modelling-knowledge` as `docs/audit/<package-id>/`.
   - Add audit/evidence front matter to every Markdown file.
   - Mark client/project material `sensitivity: restricted` unless reviewed otherwise.
   - Register the package in `docs/audit/audit-registry.json` and `docs/audit/audit-index.md`.
   - Add a discovery draft under `inbox/discovery-drafts/`.

5. Validate before handoff.
   - Run package-specific validators.
   - Run `vault-doctor check`.
   - Treat large-note and duplicate-filename warnings as expected for raw evidence packages unless they hide broken links or missing front matter.

## DRIEAT Tooling

For the DRIEAT report corpus, use the packaged CLI from `modeller-memory`:

```powershell
$env:PYTHONPATH='C:\Users\jean-noel.diltoer\software\sources\AItlantis\modeller-memory\src'
python -m modeller_memory.tools.drieat_import.cli build
python -m modeller_memory.tools.drieat_import.cli validate-source
python -m modeller_memory.tools.drieat_import.cli install
python -m modeller_memory.tools.drieat_import.cli validate-package
```

Override paths when needed:

```powershell
python -m modeller_memory.tools.drieat_import.cli build --workdir <staging-dir>
python -m modeller_memory.tools.drieat_import.cli install --source-vault <vault> --target-repo <modelling-knowledge>
python -m modeller_memory.tools.drieat_import.cli validate-package --target-repo <modelling-knowledge>
```

## Curation Rules

- Do not promote generated extraction directly into `domains/**`.
- Preserve source extracts and evidence IDs for every promoted claim.
- Split project-specific facts from reusable modelling method knowledge.
- Resolve reviewer comments and contradictions before marking a rule canonical.
- Keep implementation scripts out of `modelling-knowledge`.

## References

- Read `references/package-shape.md` when creating or reviewing an acquisition package.
- Read `references/promotion-review.md` before drafting accepted knowledge from extracted evidence.

### Process references (mirrored from `knowledge-vault-orchestrator`)

The corpus-agnostic lifecycle context — the waves and gates this memory-side tooling
produces evidence for — is mirrored under `references/from-orchestrator/` (source of
truth: the `knowledge-vault-orchestrator` skill; do not edit the copies). Read them to
align package output with the gate the orchestrator will check it against:

- `from-orchestrator/wave-definitions.md`, `from-orchestrator/gate-criteria.md` — the WC/G0–G7 gates.
- `from-orchestrator/vault-creation.md`, `from-orchestrator/template-catalog.md` — the vault the package installs into and the candidate→accepted front-matter contract.
- `from-orchestrator/board-pack-template.md`, `from-orchestrator/subagent-brief-templates.md`, `from-orchestrator/delta-rebaseline.md`, `from-orchestrator/obsidian-vault-linking.md`, `from-orchestrator/progress-artifact.md` — board, lane, delta, linking, and progress conventions.

See `references/from-orchestrator/README.md` for the full index and the ownership note
(agents owns the skill/orchestration; `modeller-memory` owns only the extraction/validation tooling).
