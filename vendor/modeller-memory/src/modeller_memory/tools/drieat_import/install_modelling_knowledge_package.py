from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[6]
AITLANTIS_ROOT = Path(__file__).resolve().parents[5]
SOURCE_ROOT = Path(
    os.environ.get("DRIEAT_SOURCE_VAULT", WORKSPACE_ROOT / "drieat_knowledge_structure" / "vault")
)
TARGET_REPO = Path(os.environ.get("MODELLING_KNOWLEDGE_REPO", AITLANTIS_ROOT / "modelling-knowledge"))
PACKAGE_ID = "drieat-model-knowledge-acquisition-2026-07-16"
PACKAGE_ROOT = TARGET_REPO / "docs" / "audit" / PACKAGE_ID
TODAY = date(2026, 7, 16).isoformat()


FRONT_MATTER = {
    "status": "draft",
    "owner": "modelling-knowledge",
    "authority_level": "evidence",
    "sensitivity": "restricted",
    "generated_from": ["DRIEAT report DOCX corpus converted by drieat_knowledge_structure"],
    "last_reviewed": TODAY,
}


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def has_front_matter(text: str) -> bool:
    return text.startswith("---\n") and "\n---\n" in text[4:]


def strip_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not has_front_matter(text):
        return {}, text
    _, rest = text.split("---\n", 1)
    fm_text, body = rest.split("\n---\n", 1)
    data: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data, body


def yaml_scalar(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if not text:
        return ""
    if any(ch in text for ch in [":", "#", "[", "]", "{", "}", '"', "'"]) or text != text.strip():
        return json.dumps(text, ensure_ascii=False)
    return text


def front_matter_block(fields: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def write_markdown_with_metadata(source: Path, target: Path, note_type: str) -> None:
    text = source.read_text(encoding="utf-8")
    old_fm, body = strip_front_matter(text)
    title = title_from_markdown(body, source.stem)
    fields: dict[str, object] = {
        "title": title,
        **FRONT_MATTER,
        "type": note_type,
        "audit_id": PACKAGE_ID,
    }
    for key in ["id", "source_file", "sha256", "converted_at"]:
        if key in old_fm and old_fm[key]:
            fields[key] = old_fm[key]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(front_matter_block(fields) + body.lstrip(), encoding="utf-8")


def copy_tree_files(source_dir: Path, target_dir: Path, *, markdown_type: str | None = None) -> None:
    if not source_dir.exists():
        return
    for source in source_dir.rglob("*"):
        if not source.is_file():
            continue
        target = target_dir / source.relative_to(source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() == ".md" and markdown_type:
            write_markdown_with_metadata(source, target, markdown_type)
        else:
            shutil.copy2(source, target)


def write_package_readme() -> None:
    readme = PACKAGE_ROOT / "README.md"
    body = f"""# DRIEAT Model Knowledge Acquisition Package

## Purpose

This package standardizes the DRIEAT report delivery into an acquisition-ready evidence set for `modelling-knowledge`. It is a restricted audit package, not accepted domain knowledge.

## Included Material

- `corpus/markdown/` - one Markdown conversion per source document with stable paragraph, table and comment anchors.
- `corpus/tables/` - CSV extraction of Word tables.
- `corpus/assets/` - embedded document media extracted from the DOCX files.
- `references/` - source, section, evidence, rule, issue, workflow, object, terminology, table, comment and traceability matrices.
- `graph/` - node/edge CSV plus JSON-LD graph export generated from the evidence matrices.
- `draft-diataxis/` - starter tutorial/how-to/reference scaffolds that must be reviewed before promotion.

## Acquisition Status

The package is generated evidence. It may be used for knowledge acquisition, classification, antagonist review and curation. It must not be treated as accepted `domains/transport` knowledge until the review path in `inbox/discovery-drafts/` and the normal promotion board have passed.

## Key Counts

| Item | Count |
|---|---:|
| Source documents | 6 |
| Sections | 460 |
| Tables | 29 |
| Comments | 865 |
| Evidence items | 3,521 |
| Rule-like records | 480 |
| Issue-like records | 683 |
| Workflow-like records | 842 |
| Graph nodes | 4,245 |
| Graph edges | 10,671 |

## Entry Points

- [Source register](references/source-register.md)
- [Evidence matrix](references/evidence-matrix.md)
- [Traceability matrix](references/traceability-matrix.md)
- [Knowledge graph ontology](knowledge-graph-ontology.md)
- [Ingestion runbook](INGESTION-RUNBOOK.md)
- [Matrix catalog](MATRIX-CATALOG.md)
- [Sources](SOURCES.md)

## Verification

The source vault validation passed before packaging with `broken_evidence_links=0`. Package-local references can be checked by confirming the matrix links resolve to `corpus/markdown/` anchors and that `graph/knowledge-graph.jsonld` parses as JSON.
"""
    fields = {
        "title": "DRIEAT Model Knowledge Acquisition Package",
        "status": "draft",
        "type": "audit",
        "owner": "modelling-knowledge",
        "authority_level": "evidence",
        "sensitivity": "restricted",
        "audit_id": PACKAGE_ID,
        "generated_from": ["DRIEAT report DOCX corpus", "drieat_knowledge_structure/vault"],
        "last_reviewed": TODAY,
    }
    readme.write_text(front_matter_block(fields) + body, encoding="utf-8")


def write_sources() -> None:
    source_register = (PACKAGE_ROOT / "references" / "source-register.md").read_text(encoding="utf-8")
    _source_register_fm, source_register_body = strip_front_matter(source_register)
    body = f"""# DRIEAT Source Register

The authoritative source register for this package is copied at [references/source-register.md](references/source-register.md). Source DOCX files are not copied into `modelling-knowledge`; the package records their filenames and SHA-256 hashes and stores standardized Markdown, extracted tables, media, matrices and graph exports.

## Registered Sources

{source_register_body}
"""
    fields = {
        "title": "DRIEAT Source Register",
        **FRONT_MATTER,
        "type": "evidence",
        "audit_id": PACKAGE_ID,
    }
    (PACKAGE_ROOT / "SOURCES.md").write_text(front_matter_block(fields) + body, encoding="utf-8")


def write_ingestion_runbook() -> None:
    body = """# DRIEAT Knowledge Acquisition Runbook

## 1. Start From Provenance

Use `references/source-register.csv` and `references/source-register.md` to identify the six source documents, hashes and converted Markdown paths. Treat the DOCX reports as evidence sources, not as a single source of truth.

## 2. Select Candidate Knowledge

Use these matrices as the acquisition queue:

- `references/rule-matrix.csv` for validation criteria, thresholds, filtering rules and method constraints.
- `references/workflow-matrix.csv` for calibration, assignment, validation and model-operation workflows.
- `references/model-object-matrix.csv` for demand, profile, scenario, horizon, section and data-object references.
- `references/issue-matrix.csv` and `references/comment-matrix.csv` for reviewer objections, reproducibility gaps and contested claims.
- `references/terminology-matrix.csv` for acronym and term normalization.

## 3. Preserve Evidence Links

Every promoted candidate must retain:

- evidence ID;
- source document code;
- section or paragraph/table/comment anchor;
- source extract;
- sensitivity classification;
- review status.

Use `references/traceability-matrix.csv` as the control surface for this.

## 4. Classify Before Promotion

Promote nothing directly into `domains/transport`. First create or refine discovery drafts under `inbox/discovery-drafts/`, then run source-boundary, evidence-quality, sensitivity and knowledge-architecture review.

## 5. Recommended First Curation Pass

Start with the 2023 morning-peak base validation subset:

1. count-selection and dynamisation rules;
2. GEH volume-validation rules;
3. travel-time-validation rules;
4. calibration/assignment workflow;
5. model-object references needed to reproduce one run;
6. reviewer comments that contest reproducibility.

## 6. Graph Consumption

Use `graph/nodes.csv`, `graph/edges.csv` or `graph/knowledge-graph.jsonld` for automated ingestion. These graph exports represent evidence and classifications, not accepted facts.
"""
    fields = {
        "title": "DRIEAT Knowledge Acquisition Runbook",
        **FRONT_MATTER,
        "type": "process",
        "audit_id": PACKAGE_ID,
    }
    (PACKAGE_ROOT / "INGESTION-RUNBOOK.md").write_text(front_matter_block(fields) + body, encoding="utf-8")


def write_matrix_catalog() -> None:
    rows = [
        ("source-register", "Document inventory, hashes and converted Markdown paths."),
        ("section-matrix", "Heading and section anchors for document navigation."),
        ("evidence-matrix", "All extracted evidence items with source kind, classification and links."),
        ("rule-matrix", "Rule-like and criterion-like evidence candidates."),
        ("issue-matrix", "Issue, comment, gap and contested-claim candidates."),
        ("workflow-matrix", "Workflow, method and simulation-process candidates."),
        ("model-object-matrix", "Model, demand, profile, data and network object references."),
        ("terminology-matrix", "Auto-detected acronyms and technical terms."),
        ("comment-matrix", "Word comments with anchors and reviewer metadata where available."),
        ("table-matrix", "Extracted Word table inventory and CSV paths."),
        ("traceability-matrix", "Evidence-to-canonical-note promotion control surface."),
        ("image-register", "Embedded media inventory."),
    ]
    table = "\n".join(
        ["| Matrix | Purpose |", "|---|---|"]
        + [f"| [references/{name}.md](references/{name}.md) | {purpose} |" for name, purpose in rows]
    )
    body = f"""# DRIEAT Matrix Catalog

{table}

All matrices also exist as `.csv` files. `evidence-matrix` is additionally available as JSONL for streaming ingestion.
"""
    fields = {
        "title": "DRIEAT Matrix Catalog",
        **FRONT_MATTER,
        "type": "evidence",
        "audit_id": PACKAGE_ID,
    }
    (PACKAGE_ROOT / "MATRIX-CATALOG.md").write_text(front_matter_block(fields) + body, encoding="utf-8")


def rewrite_reference_links() -> None:
    for path in (PACKAGE_ROOT / "references").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("../corpus/markdown/", "corpus/markdown/")
        text = text.replace("corpus/markdown/", "../corpus/markdown/")
        text = text.replace("corpus/tables/", "../corpus/tables/")
        text = text.replace("diataxis/graph/", "../graph/")
        path.write_text(text, encoding="utf-8")
    for path in (PACKAGE_ROOT / "graph").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("../corpus/markdown/", "../corpus/markdown/")
        path.write_text(text, encoding="utf-8")
    for path in (PACKAGE_ROOT / "draft-diataxis").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("../../data/", "../../references/")
        path.write_text(text, encoding="utf-8")


def copy_package() -> None:
    PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
    marker = PACKAGE_ROOT / ".generated-by-drieat-import"
    marker.write_text(f"{PACKAGE_ID}\n{datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
    stale_duplicate_graph = PACKAGE_ROOT / "draft-diataxis" / "graph"
    if stale_duplicate_graph.is_dir() and PACKAGE_ROOT in stale_duplicate_graph.parents:
        shutil.rmtree(stale_duplicate_graph)

    copy_tree_files(SOURCE_ROOT / "corpus" / "markdown", PACKAGE_ROOT / "corpus" / "markdown", markdown_type="evidence")
    copy_tree_files(SOURCE_ROOT / "corpus" / "tables", PACKAGE_ROOT / "corpus" / "tables")
    copy_tree_files(SOURCE_ROOT / "corpus" / "assets", PACKAGE_ROOT / "corpus" / "assets")
    copy_tree_files(SOURCE_ROOT / "data", PACKAGE_ROOT / "references", markdown_type="evidence")
    for child in (SOURCE_ROOT / "diataxis").iterdir():
        if child.name == "graph":
            continue
        copy_tree_files(child, PACKAGE_ROOT / "draft-diataxis" / child.name, markdown_type="evidence")
    copy_tree_files(SOURCE_ROOT / "diataxis" / "graph", PACKAGE_ROOT / "graph", markdown_type="evidence")
    shutil.copy2(SOURCE_ROOT / "diataxis" / "graph" / "knowledge-graph.jsonld", PACKAGE_ROOT / "graph" / "knowledge-graph.jsonld")
    write_markdown_with_metadata(SOURCE_ROOT / "knowledge-graph-ontology.md", PACKAGE_ROOT / "knowledge-graph-ontology.md", "evidence")
    rewrite_reference_links()
    write_package_readme()
    write_sources()
    write_ingestion_runbook()
    write_matrix_catalog()


def update_audit_registry() -> None:
    path = TARGET_REPO / "docs" / "audit" / "audit-registry.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    entry = {
        "audit_id": PACKAGE_ID,
        "date": TODAY,
        "language": "fr/en",
        "status": "draft",
        "scope": ["DRIEAT", "transport", "dynamic-model-validation", "knowledge-acquisition"],
        "root_path": f"docs/audit/{PACKAGE_ID}",
        "readme": f"docs/audit/{PACKAGE_ID}/README.md",
        "purpose": "Restricted evidence package converting DRIEAT report DOCX files into Markdown, matrices, references and graph exports for governed knowledge acquisition.",
    }
    entries = [item for item in registry.get("entries", []) if item.get("audit_id") != PACKAGE_ID]
    entries.append(entry)
    registry["entries"] = entries
    registry["last_reviewed"] = TODAY
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_audit_index() -> None:
    path = TARGET_REPO / "docs" / "audit" / "audit-index.md"
    text = path.read_text(encoding="utf-8")
    row = (
        f"| [[docs/audit/{PACKAGE_ID}/README]] | {TODAY} | draft | "
        "`DRIEAT`, `transport`, `dynamic-model-validation` | "
        "Restricted standardized evidence package for governed knowledge acquisition |"
    )
    if PACKAGE_ID not in text:
        marker = "| [[docs/audit/modelling-knowledge-vault-audit-2026-07-15/README]]"
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith(marker):
                lines.insert(index + 1, row)
                break
        else:
            lines.append(row)
        text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def write_discovery_draft() -> None:
    path = TARGET_REPO / "inbox" / "discovery-drafts" / "drieat-hybrid-model-knowledge-acquisition.md"
    body = """# DRIEAT hybrid model report corpus as a knowledge-acquisition source

## Claim

The DRIEAT report delivery contains project-specific candidate knowledge for dynamic transport modelling, including input-data selection, demand dynamisation, network coding, calibration and validation workflows, validation criteria, model-operation procedures, reviewer comments and reproducibility gaps. This material is not accepted knowledge yet; it should be curated from the restricted evidence package at `docs/audit/drieat-model-knowledge-acquisition-2026-07-16/`.

## Provenance

- Evidence package: [[docs/audit/drieat-model-knowledge-acquisition-2026-07-16/README]]
- Source register: [[docs/audit/drieat-model-knowledge-acquisition-2026-07-16/SOURCES]]
- Acquisition runbook: [[docs/audit/drieat-model-knowledge-acquisition-2026-07-16/INGESTION-RUNBOOK]]
- Traceability control surface: `docs/audit/drieat-model-knowledge-acquisition-2026-07-16/references/traceability-matrix.csv`

The package was generated from six DRIEAT DOCX reports and preserves document hashes, converted Markdown anchors, extracted Word comments, tables, media, classification matrices and graph exports.

## Sensitivity

`sensitivity: restricted`. The package derives from client/project reports and must not be exposed or promoted into public/internal reusable transport-domain notes without explicit review and redaction.

## Required Review

- source-boundary review: confirm the target for durable facts is `domains/transport` and that implementation/model-object facts remain evidence unless verified against the source model;
- evidence-quality review: validate formulas, thresholds and workflow semantics against source extracts and reviewer comments;
- sensitivity/privacy review: decide which derived facts can be downgraded from restricted;
- knowledge-architecture review: split accepted outputs into Diátaxis notes and keep project-specific records as restricted evidence.
"""
    fields = {
        "title": "DRIEAT hybrid model report corpus as a knowledge-acquisition source",
        "status": "draft",
        "type": "discovery-draft",
        "owner": "codex-import-agent",
        "source": "modeller-memory",
        "candidate_id": "DRIEAT-KA-2026-07-16",
        "origin_run": "codex-thread-drieat-knowledge-structure-2026-07-16",
        "authority_context_refs": [
            "[[project-context]]",
            "[[standards/knowledge-metadata-standard]]",
            "[[standards/source-boundary-standard]]",
            "[[docs/audit/drieat-model-knowledge-acquisition-2026-07-16/README]]",
        ],
        "related_decisions": ["[[decisions/0005-knowledge-vault-domain-scope]]", "[[decisions/0007-memory-promotion-coordination]]"],
        "sensitivity": "restricted",
        "captured_from": "Six DRIEAT report DOCX files converted to Markdown, matrices and graph exports on 2026-07-16.",
        "claim": "The restricted DRIEAT report corpus is an evidence-backed source of candidate dynamic transport modelling knowledge that requires governed curation before promotion.",
    }
    path.write_text(front_matter_block(fields) + body, encoding="utf-8")


def main() -> None:
    if not SOURCE_ROOT.exists():
        raise SystemExit(f"Missing source vault: {SOURCE_ROOT}")
    if not TARGET_REPO.exists():
        raise SystemExit(f"Missing target repository: {TARGET_REPO}")
    copy_package()
    update_audit_registry()
    update_audit_index()
    write_discovery_draft()
    print(f"Installed {PACKAGE_ID}")
    print(PACKAGE_ROOT)


if __name__ == "__main__":
    main()
