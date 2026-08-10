# Acquisition Package Shape

Use this shape for document-derived evidence packages installed into `modelling-knowledge`.

```text
docs/audit/<package-id>/
├── README.md
├── SOURCES.md
├── INGESTION-RUNBOOK.md
├── MATRIX-CATALOG.md
├── knowledge-graph-ontology.md
├── corpus/
│   ├── markdown/
│   ├── tables/
│   └── assets/
├── references/
│   ├── source-register.csv
│   ├── evidence-matrix.csv
│   ├── traceability-matrix.csv
│   └── ...
├── graph/
│   ├── nodes.csv
│   ├── edges.csv
│   └── knowledge-graph.jsonld
└── draft-diataxis/
```

Every Markdown file in the package must carry planning/evidence metadata:

```yaml
title:
status: draft
type: audit | evidence | process
owner: modelling-knowledge
authority_level: evidence
sensitivity: restricted
audit_id:
generated_from:
last_reviewed:
```

Keep raw DOCX/PDF files out of `modelling-knowledge` unless a project explicitly approves storing restricted source attachments there. Prefer hashes, converted Markdown, extracted assets and traceability links.
