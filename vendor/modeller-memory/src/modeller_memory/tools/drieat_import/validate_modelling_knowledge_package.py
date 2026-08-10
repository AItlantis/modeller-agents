from __future__ import annotations

import csv
import json
import os
from pathlib import Path


AITLANTIS_ROOT = Path(__file__).resolve().parents[5]
TARGET_REPO = Path(os.environ.get("MODELLING_KNOWLEDGE_REPO", AITLANTIS_ROOT / "modelling-knowledge"))
PACKAGE_ID = "drieat-model-knowledge-acquisition-2026-07-16"
PACKAGE_ROOT = TARGET_REPO / "docs" / "audit" / PACKAGE_ID


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def has_front_matter(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return text.startswith("---\n") and "\n---\n" in text[4:]


def main() -> None:
    required = [
        PACKAGE_ROOT / "README.md",
        PACKAGE_ROOT / "SOURCES.md",
        PACKAGE_ROOT / "INGESTION-RUNBOOK.md",
        PACKAGE_ROOT / "MATRIX-CATALOG.md",
        PACKAGE_ROOT / "knowledge-graph-ontology.md",
        PACKAGE_ROOT / "references" / "source-register.csv",
        PACKAGE_ROOT / "references" / "evidence-matrix.csv",
        PACKAGE_ROOT / "references" / "traceability-matrix.csv",
        PACKAGE_ROOT / "graph" / "nodes.csv",
        PACKAGE_ROOT / "graph" / "edges.csv",
        PACKAGE_ROOT / "graph" / "knowledge-graph.jsonld",
        TARGET_REPO / "inbox" / "discovery-drafts" / "drieat-hybrid-model-knowledge-acquisition.md",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    markdown_missing_fm = [str(path) for path in PACKAGE_ROOT.rglob("*.md") if not has_front_matter(path)]
    if markdown_missing_fm:
        raise SystemExit(f"Markdown files without front matter: {markdown_missing_fm[:20]}")

    evidence = read_csv(PACKAGE_ROOT / "references" / "evidence-matrix.csv")
    cache: dict[Path, str] = {}
    broken: list[tuple[str, str, str]] = []
    for row in evidence:
        link = row["evidence_link"]
        rel_path, _, anchor = link.partition("#")
        target = (PACKAGE_ROOT / "references" / rel_path).resolve()
        if not target.exists():
            broken.append((row["id"], "file", str(target)))
            continue
        if anchor:
            text = cache.setdefault(target, target.read_text(encoding="utf-8"))
            if f'id="{anchor}"' not in text and f"id='{anchor}'" not in text:
                broken.append((row["id"], "anchor", anchor))
    if broken:
        raise SystemExit(f"Broken evidence links: {broken[:20]}")

    graph = json.loads((PACKAGE_ROOT / "graph" / "knowledge-graph.jsonld").read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in graph["nodes"]}
    broken_edges = [
        (edge.get("source", ""), edge.get("target", ""), edge.get("relation", ""))
        for edge in graph["edges"]
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids
    ]
    if broken_edges:
        raise SystemExit(f"Broken graph edges: {broken_edges[:20]}")
    registry = json.loads((TARGET_REPO / "docs" / "audit" / "audit-registry.json").read_text(encoding="utf-8"))
    registry_ids = {entry.get("audit_id") for entry in registry.get("entries", [])}
    if PACKAGE_ID not in registry_ids:
        raise SystemExit("Package missing from audit-registry.json")
    audit_index = (TARGET_REPO / "docs" / "audit" / "audit-index.md").read_text(encoding="utf-8")
    if PACKAGE_ID not in audit_index:
        raise SystemExit("Package missing from audit-index.md")

    print(f"package={PACKAGE_ID}")
    print(f"sources={len(read_csv(PACKAGE_ROOT / 'references' / 'source-register.csv'))}")
    print(f"sections={len(read_csv(PACKAGE_ROOT / 'references' / 'section-matrix.csv'))}")
    print(f"tables={len(read_csv(PACKAGE_ROOT / 'references' / 'table-matrix.csv'))}")
    print(f"comments={len(read_csv(PACKAGE_ROOT / 'references' / 'comment-matrix.csv'))}")
    print(f"evidence={len(evidence)}")
    print(f"rules={len(read_csv(PACKAGE_ROOT / 'references' / 'rule-matrix.csv'))}")
    print(f"issues={len(read_csv(PACKAGE_ROOT / 'references' / 'issue-matrix.csv'))}")
    print(f"workflows={len(read_csv(PACKAGE_ROOT / 'references' / 'workflow-matrix.csv'))}")
    print(f"graph_nodes={len(graph['nodes'])}")
    print(f"graph_edges={len(graph['edges'])}")
    print(f"markdown_files={len(list(PACKAGE_ROOT.rglob('*.md')))}")
    print("broken_evidence_links=0")
    print("broken_graph_edges=0")
    print("front_matter=ok")
    print("audit_registry=ok")
    print("discovery_draft=ok")


if __name__ == "__main__":
    main()
