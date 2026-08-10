from __future__ import annotations

import csv
import json
import os
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[6]
ROOT = Path(os.environ.get("DRIEAT_SOURCE_VAULT", WORKSPACE_ROOT / "drieat_knowledge_structure" / "vault"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "data" / "source-register.csv",
        ROOT / "data" / "evidence-matrix.csv",
        ROOT / "data" / "rule-matrix.csv",
        ROOT / "data" / "issue-matrix.csv",
        ROOT / "data" / "workflow-matrix.csv",
        ROOT / "data" / "traceability-matrix.csv",
        ROOT / "diataxis" / "graph" / "nodes.csv",
        ROOT / "diataxis" / "graph" / "edges.csv",
        ROOT / "diataxis" / "graph" / "knowledge-graph.jsonld",
    ]
    missing_files = [str(path) for path in required if not path.exists()]
    if missing_files:
        raise SystemExit(f"Missing required files: {missing_files}")

    evidence = read_csv(ROOT / "data" / "evidence-matrix.csv")
    cache: dict[Path, str] = {}
    broken: list[tuple[str, str, str]] = []
    for row in evidence:
        link = row["evidence_link"]
        rel_path, _, anchor = link.partition("#")
        target = (ROOT / "data" / rel_path).resolve()
        if not target.exists():
            broken.append((row["id"], "file", str(target)))
            continue
        if anchor:
            text = cache.setdefault(target, target.read_text(encoding="utf-8"))
            if f'id="{anchor}"' not in text and f"id='{anchor}'" not in text:
                broken.append((row["id"], "anchor", anchor))

    graph = json.loads((ROOT / "diataxis" / "graph" / "knowledge-graph.jsonld").read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in graph["nodes"]}
    broken_edges = [
        (edge.get("source", ""), edge.get("target", ""), edge.get("relation", ""))
        for edge in graph["edges"]
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids
    ]
    if broken_edges:
        raise SystemExit(f"Broken graph edges: {broken_edges[:20]}")
    print(f"sources={len(read_csv(ROOT / 'data' / 'source-register.csv'))}")
    print(f"sections={len(read_csv(ROOT / 'data' / 'section-matrix.csv'))}")
    print(f"tables={len(read_csv(ROOT / 'data' / 'table-matrix.csv'))}")
    print(f"comments={len(read_csv(ROOT / 'data' / 'comment-matrix.csv'))}")
    print(f"evidence={len(evidence)}")
    print(f"rules={len(read_csv(ROOT / 'data' / 'rule-matrix.csv'))}")
    print(f"issues={len(read_csv(ROOT / 'data' / 'issue-matrix.csv'))}")
    print(f"workflows={len(read_csv(ROOT / 'data' / 'workflow-matrix.csv'))}")
    print(f"graph_nodes={len(graph['nodes'])}")
    print(f"graph_edges={len(graph['edges'])}")
    print("broken_graph_edges=0")
    print(f"broken_evidence_links={len(broken)}")
    if broken:
        for item in broken[:20]:
            print(item)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
