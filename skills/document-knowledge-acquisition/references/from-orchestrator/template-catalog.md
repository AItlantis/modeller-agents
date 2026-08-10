# Template Catalog

The templates under `references/templates/` used by Wave C (`scripts/scaffold_vault.py`).
Tokens substituted at scaffold time: `{{VAULT_NAME}}`, `{{SENSITIVITY}}`, `{{PREFIX}}`, `{{DATE}}`.

## Root documents (→ vault root)

| Template | Becomes | Purpose |
|---|---|---|
| `home.template.md` | `HOME.md` | Index / map-of-content; gate-state table; entry point. |
| `handoff.template.md` | `HANDOFF.md` | Next-orchestrator handoff; gate state; learned traps. |
| `plan.template.md` | `plan.md` | Execution plan; governing boundary; stop conditions. |
| `ontology.template.md` | `knowledge-graph-ontology.md` | Controlled node/edge ontology + id prefix. |

`README.md` and `.gitignore` are emitted directly by the scaffolder (not template files).

## Per-type note templates (→ `<vault>/templates/`)

| Template | Diátaxis type | Authored in | Notes |
|---|---|---|---|
| `note-reference.template.md` | reference | Wave 4 (first) | Facts + tables; every value carries a `source_anchor`. |
| `note-explanation.template.md` | explanation | Wave 4 (after reference) | No new thresholds/names/steps beyond reference. |
| `note-how-to.template.md` | how-to | Wave 4 (after reference) | Steps with input/output; a verification section. |
| `note-tutorial.template.md` | tutorial | Wave 6+ (last) | Deferred stub until reproduction (G6) succeeds. |

## Front-matter contract (candidate → accepted)

All note templates carry, aligned to `modelling-knowledge/standards/knowledge-metadata-standard`:

```yaml
title, status, type, owner, id, domain, authority_level, sensitivity,
source_repositories, derived_from_restricted, redaction_review{status,reviewer,reviewed_at},
source_anchor, related_decisions, last_reviewed, refresh_trigger, promotion_target
```

Candidate defaults: `status: proposed` (tutorial: `blocked-pending-reproduction`),
`authority_level: evidence`, `derived_from_restricted: true`, `redaction_review.status: pending`.
On promotion these become `status: accepted`, `authority_level: authoritative`, and
`redaction_review.status: cleared` — a 1:1 field map, no renaming.

## Extending

Add a new template file here and register it in `scaffold_vault.py` (`ROOT_DOCS` or
`NOTE_TEMPLATES`). Keep the four controlled-vocabulary fields so gate GC passes.
