from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}


WORKSPACE_ROOT = Path(__file__).resolve().parents[6]
ROOT = Path(os.environ.get("DRIEAT_KNOWLEDGE_WORKDIR", WORKSPACE_ROOT / "drieat_knowledge_structure"))
DOCX_DIR = ROOT / "sources" / "docx"
OUT = ROOT / "vault"
MARKDOWN_DIR = OUT / "corpus" / "markdown"
ASSETS_DIR = OUT / "corpus" / "assets"
TABLES_DIR = OUT / "corpus" / "tables"
DATA_DIR = OUT / "data"
DIATAXIS_DIR = OUT / "diataxis"


DOC_CODES = [
    ("260225_Remarques_modele_final", "REM"),
    ("EME200071_R1_Donnees_entree", "R1"),
    ("EME200071_R2_Codage", "R2"),
    ("EME200071_R3_Dynamisation", "R3"),
    ("EME200071_R04_Calage", "R4"),
    ("EME200071_R05_Manuel", "R5"),
]


RULE_PATTERNS = re.compile(
    r"\b("
    r"doit|doivent|devra|objectif|crit[eè]re|seuil|r[eè]gle|condition|"
    r"GEH|RMSE|R[²2]|slope|pente|%|pourcentage|tol[eé]rance|"
    r"Q15|Q85|15\s*min|30\s*min|heure|moyenne"
    r")\b",
    re.IGNORECASE,
)
ISSUE_PATTERNS = re.compile(
    r"\b("
    r"remarque|commentaire|probl[eè]me|incoh[eé]ren|erreur|manque|insuffisant|"
    r"non\s+reproduct|ne\s+permet|pas\s+suffisant|à\s+corriger|corriger|"
    r"question|clarifier|incertain|impossible|contradic"
    r")\b",
    re.IGNORECASE,
)
WORKFLOW_PATTERNS = re.compile(
    r"\b("
    r"workflow|processus|[ée]tape|import|export|ajustement|affectation|"
    r"calage|validation|dynamisation|warm[- ]?up|SRC|DUE|simulation|"
    r"sc[eé]nario|exp[eé]rience|r[eé]plication"
    r")\b",
    re.IGNORECASE,
)
OBJECT_PATTERNS = re.compile(
    r"\b("
    r"matrice|demande|profil|configuration|couche|attribut|horizon|"
    r"sous[- ]?chemin|itin[eé]raire|section|centro[iï]de|connecteur|"
    r"type\s+de\s+voie|comptage|capteur|RDS|FCD|TomTom|Aimsun"
    r")\b",
    re.IGNORECASE,
)
TERM_PATTERNS = re.compile(
    r"\b(PPM|PPS|VP|VL|PL|TV|UVP|SRC|DUE|GEH|RMSE|R[²2]|Q15|Q85|FCD|RDS|OD|PFD|CCAP)\b",
    re.IGNORECASE,
)


def qn(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def attr(el: ET.Element, prefix: str, local: str) -> str | None:
    return el.attrib.get(qn(prefix, local))


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def doc_code(path: Path) -> str:
    stem = path.stem
    for prefix, code in DOC_CODES:
        if stem.startswith(prefix):
            return code
    return slugify(stem).upper()[:8]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_zip_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        return None


def clean_text(value: str) -> str:
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def md_escape_cell(value: str) -> str:
    value = clean_text(value).replace("|", "\\|")
    return value.replace("\n", "<br>")


def truncate(value: str, limit: int = 360) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def rels_map(zf: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    root = read_zip_xml(zf, "word/_rels/document.xml.rels")
    result: dict[str, dict[str, str]] = {}
    if root is None:
        return result
    for rel in root.findall("rel:Relationship", NS):
        rid = rel.attrib.get("Id")
        if rid:
            result[rid] = {
                "type": rel.attrib.get("Type", ""),
                "target": rel.attrib.get("Target", ""),
                "mode": rel.attrib.get("TargetMode", ""),
            }
    return result


def styles_map(zf: zipfile.ZipFile) -> dict[str, str]:
    root = read_zip_xml(zf, "word/styles.xml")
    result: dict[str, str] = {}
    if root is None:
        return result
    for style in root.findall("w:style", NS):
        sid = attr(style, "w", "styleId")
        name_el = style.find("w:name", NS)
        if sid and name_el is not None:
            result[sid] = attr(name_el, "w", "val") or sid
    return result


def core_props(zf: zipfile.ZipFile) -> dict[str, str]:
    root = read_zip_xml(zf, "docProps/core.xml")
    result: dict[str, str] = {}
    if root is None:
        return result
    for key, path in {
        "title": "dc:title",
        "creator": "dc:creator",
        "last_modified_by": "cp:lastModifiedBy",
        "created": "dcterms:created",
        "modified": "dcterms:modified",
    }.items():
        el = root.find(path, NS)
        result[key] = clean_text(el.text or "") if el is not None else ""
    return result


def extract_comments(zf: zipfile.ZipFile, code: str) -> dict[str, dict[str, str]]:
    root = read_zip_xml(zf, "word/comments.xml")
    result: dict[str, dict[str, str]] = {}
    if root is None:
        return result
    for comment in root.findall("w:comment", NS):
        cid = attr(comment, "w", "id")
        if cid is None:
            continue
        text = clean_text("".join(t.text or "" for t in comment.findall(".//w:t", NS)))
        result[cid] = {
            "comment_id": f"{code}-C{int(cid):04d}" if cid.isdigit() else f"{code}-C{cid}",
            "doc_comment_id": cid,
            "author": attr(comment, "w", "author") or "",
            "date": attr(comment, "w", "date") or "",
            "text": text,
        }
    return result


def text_from_run(run: ET.Element) -> str:
    parts: list[str] = []
    for node in run.iter():
        if node.tag == qn("w", "t"):
            parts.append(node.text or "")
        elif node.tag == qn("w", "tab"):
            parts.append("\t")
        elif node.tag in {qn("w", "br"), qn("w", "cr")}:
            parts.append("\n")
    return "".join(parts)


def text_from_para(
    p: ET.Element,
    rels: dict[str, dict[str, str]],
) -> tuple[str, list[str]]:
    parts: list[str] = []
    comment_ids: list[str] = []
    for comment_node in p.findall(".//w:commentRangeStart", NS) + p.findall(".//w:commentReference", NS):
        cid = attr(comment_node, "w", "id")
        if cid and cid not in comment_ids:
            comment_ids.append(cid)
    for node in list(p):
        if node.tag == qn("w", "r"):
            parts.append(text_from_run(node))
        elif node.tag == qn("w", "hyperlink"):
            h_text = clean_text("".join(text_from_run(r) for r in node.findall("w:r", NS)))
            rid = attr(node, "r", "id")
            target = rels.get(rid or "", {}).get("target", "")
            if h_text and target:
                parts.append(f"[{h_text}]({target})")
            else:
                parts.append(h_text)
    return clean_text("".join(parts)), comment_ids


def para_style(p: ET.Element, styles: dict[str, str]) -> tuple[str, str]:
    p_style = p.find("w:pPr/w:pStyle", NS)
    sid = attr(p_style, "w", "val") if p_style is not None else ""
    return sid or "", styles.get(sid or "", sid or "")


def heading_level(p: ET.Element, styles: dict[str, str]) -> int | None:
    sid, name = para_style(p, styles)
    candidates = " ".join([sid, name]).lower()
    match = re.search(r"(heading|titre)\s*([1-9])", candidates)
    if match:
        return min(int(match.group(2)), 6)
    outline = p.find("w:pPr/w:outlineLvl", NS)
    val = attr(outline, "w", "val") if outline is not None else None
    if val is not None and val.isdigit():
        return min(int(val) + 1, 6)
    return None


def is_list_para(p: ET.Element) -> bool:
    return p.find("w:pPr/w:numPr", NS) is not None


def table_rows(tbl: ET.Element, rels: dict[str, dict[str, str]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in tbl.findall("w:tr", NS):
        row: list[str] = []
        for tc in tr.findall("w:tc", NS):
            parts = [text_from_para(p, rels)[0] for p in tc.findall("w:p", NS)]
            row.append(clean_text("\n".join(p for p in parts if p)))
        rows.append(row)
    return rows


def table_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)
    normalised = [r + [""] * (max_cols - len(r)) for r in rows]
    header = [md_escape_cell(c) or " " for c in normalised[0]]
    sep = ["---"] * max_cols
    body = [[md_escape_cell(c) for c in row] for row in normalised[1:]]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_jsonl(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def csv_to_md_table(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape_cell(str(row.get(field, ""))) for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def classify(text: str, source_kind: str) -> list[str]:
    kinds: list[str] = []
    if RULE_PATTERNS.search(text):
        kinds.append("rule_or_criterion")
    if ISSUE_PATTERNS.search(text) or source_kind == "comment":
        kinds.append("issue_or_question")
    if WORKFLOW_PATTERNS.search(text):
        kinds.append("workflow_or_method")
    if OBJECT_PATTERNS.search(text):
        kinds.append("model_or_data_object")
    if TERM_PATTERNS.search(text):
        kinds.append("terminology")
    if not kinds:
        kinds.append("claim_or_context")
    return kinds


def term_hits(text: str) -> list[str]:
    return sorted({m.group(0).upper().replace("²", "2") for m in TERM_PATTERNS.finditer(text)})


@dataclass
class BuildState:
    sources: list[dict[str, str]]
    sections: list[dict[str, str]]
    tables: list[dict[str, str]]
    comments: list[dict[str, str]]
    evidence: list[dict[str, str]]
    terminology: dict[str, dict[str, str]]
    images: list[dict[str, str]]


def add_evidence(
    state: BuildState,
    *,
    eid: str,
    doc: str,
    doc_title: str,
    source_kind: str,
    location: str,
    text: str,
    rel_link: str,
    section_id: str,
    section_title: str,
) -> None:
    if len(clean_text(text)) < 25:
        return
    kinds = classify(text, source_kind)
    row = {
        "id": eid,
        "document": doc,
        "document_title": doc_title,
        "source_kind": source_kind,
        "knowledge_types": "; ".join(kinds),
        "location": location,
        "section_id": section_id,
        "section_title": section_title,
        "extract": truncate(text),
        "evidence_link": rel_link,
        "status": "auto_extracted_needs_review",
    }
    state.evidence.append(row)
    for term in term_hits(text):
        rec = state.terminology.setdefault(
            term,
            {
                "term": term,
                "occurrences": "0",
                "documents": "",
                "first_evidence_link": rel_link,
                "notes": "auto-detected acronym/technical term; definition requires review",
            },
        )
        rec["occurrences"] = str(int(rec["occurrences"]) + 1)
        docs = set(filter(None, rec["documents"].split("; ")))
        docs.add(doc)
        rec["documents"] = "; ".join(sorted(docs))


def process_docx(path: Path, state: BuildState) -> None:
    code = doc_code(path)
    slug = slugify(f"{code}-{path.stem}")
    md_path = MARKDOWN_DIR / f"{slug}.md"
    table_dir = TABLES_DIR / slug
    asset_dir = ASSETS_DIR / slug
    table_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path) as zf:
        rels = rels_map(zf)
        styles = styles_map(zf)
        props = core_props(zf)
        comments = extract_comments(zf, code)
        doc_root = read_zip_xml(zf, "word/document.xml")
        if doc_root is None:
            raise RuntimeError(f"Cannot read word/document.xml from {path}")

        for member in zf.namelist():
            if member.startswith("word/media/") and not member.endswith("/"):
                target = asset_dir / Path(member).name
                target.write_bytes(zf.read(member))
                state.images.append(
                    {
                        "document": code,
                        "source_file": path.name,
                        "asset": str(target.relative_to(OUT)).replace("\\", "/"),
                        "original_member": member,
                    }
                )

        file_hash = sha256(path)
        title = props.get("title") or path.stem
        source_row = {
            "document": code,
            "title": title,
            "source_file": path.name,
            "markdown_file": str(md_path.relative_to(OUT)).replace("\\", "/"),
            "sha256": file_hash,
            "created": props.get("created", ""),
            "modified": props.get("modified", ""),
            "creator": props.get("creator", ""),
            "last_modified_by": props.get("last_modified_by", ""),
            "extraction_status": "converted_to_markdown",
        }
        state.sources.append(source_row)

        lines: list[str] = [
            "---",
            f"id: {code}",
            f"source_file: {json.dumps(path.name, ensure_ascii=False)}",
            f"sha256: {file_hash}",
            f"converted_at: {datetime.now(timezone.utc).isoformat()}",
            "---",
            "",
            f"# {title}",
            "",
            f"Source file: `{path.name}`",
            "",
        ]

        para_count = 0
        table_count = 0
        section_count = 0
        current_section_id = f"{code}-S000"
        current_section_title = "Document root"
        recorded_comment_ids: set[str] = set()

        body = doc_root.find("w:body", NS)
        for child in list(body) if body is not None else []:
            if child.tag == qn("w", "p"):
                text, cids = text_from_para(child, rels)
                if not text and not cids:
                    continue
                para_count += 1
                pid = f"{code}-P{para_count:04d}"
                level = heading_level(child, styles)
                if level and text:
                    section_count += 1
                    current_section_id = f"{code}-S{section_count:03d}"
                    current_section_title = text
                    state.sections.append(
                        {
                            "section_id": current_section_id,
                            "document": code,
                            "heading_level": str(level),
                            "title": text,
                            "paragraph_id": pid,
                            "evidence_link": f"../corpus/markdown/{md_path.name}#{pid}",
                        }
                    )
                    lines.extend([f'<a id="{pid}"></a>', "", f"{'#' * min(level + 1, 6)} {text}", ""])
                else:
                    prefix = "- " if is_list_para(child) else ""
                    markers = ""
                    if cids:
                        markers = " " + " ".join(
                            f"[^{comments[cid]['comment_id']}]" for cid in cids if cid in comments
                        )
                    lines.extend([f'<a id="{pid}"></a>', "", f"{prefix}{text}{markers}", ""])
                    add_evidence(
                        state,
                        eid=pid,
                        doc=code,
                        doc_title=title,
                        source_kind="paragraph",
                        location=f"paragraph {para_count}",
                        text=text,
                        rel_link=f"../corpus/markdown/{md_path.name}#{pid}",
                        section_id=current_section_id,
                        section_title=current_section_title,
                    )
                    for cid in cids:
                        if cid in comments and cid not in recorded_comment_ids:
                            recorded_comment_ids.add(cid)
                            rec = comments[cid].copy()
                            rec.update(
                                {
                                    "document": code,
                                    "document_title": title,
                                    "anchor_id": pid,
                                    "anchor_link": f"../corpus/markdown/{md_path.name}#{pid}",
                                    "section_id": current_section_id,
                                    "section_title": current_section_title,
                                }
                            )
                            state.comments.append(rec)
                            add_evidence(
                                state,
                                eid=rec["comment_id"],
                                doc=code,
                                doc_title=title,
                                source_kind="comment",
                                location=f"comment {cid} on paragraph {para_count}",
                                text=rec["text"],
                                rel_link=f"../corpus/markdown/{md_path.name}#{pid}",
                                section_id=current_section_id,
                                section_title=current_section_title,
                            )
            elif child.tag == qn("w", "tbl"):
                table_count += 1
                tid = f"{code}-T{table_count:04d}"
                rows = table_rows(child, rels)
                csv_path = table_dir / f"{tid}.csv"
                with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerows(rows)
                md_table = table_to_markdown(rows)
                lines.extend([f'<a id="{tid}"></a>', "", f"Table `{tid}`", "", md_table, ""])
                table_text = " | ".join(" ; ".join(cell for cell in row if cell) for row in rows[:8])
                state.tables.append(
                    {
                        "table_id": tid,
                        "document": code,
                        "section_id": current_section_id,
                        "section_title": current_section_title,
                        "rows": str(len(rows)),
                        "columns": str(max((len(r) for r in rows), default=0)),
                        "csv_file": str(csv_path.relative_to(OUT)).replace("\\", "/"),
                        "evidence_link": f"../corpus/markdown/{md_path.name}#{tid}",
                        "preview": truncate(table_text),
                    }
                )
                add_evidence(
                    state,
                    eid=tid,
                    doc=code,
                    doc_title=title,
                    source_kind="table",
                    location=f"table {table_count}",
                    text=table_text,
                    rel_link=f"../corpus/markdown/{md_path.name}#{tid}",
                    section_id=current_section_id,
                    section_title=current_section_title,
                )

        if comments:
            lines.extend(["", "## Extracted Comments", ""])
            for cid, rec in comments.items():
                comment_id = rec["comment_id"]
                if cid not in recorded_comment_ids:
                    state.comments.append(
                        {
                            **rec,
                            "document": code,
                            "document_title": title,
                            "anchor_id": "",
                            "anchor_link": f"../corpus/markdown/{md_path.name}#{comment_id}",
                            "section_id": "",
                            "section_title": "",
                        }
                    )
                    add_evidence(
                        state,
                        eid=comment_id,
                        doc=code,
                        doc_title=title,
                        source_kind="comment",
                        location=f"comment {cid}",
                        text=rec["text"],
                        rel_link=f"../corpus/markdown/{md_path.name}#{comment_id}",
                        section_id="",
                        section_title="",
                    )
                lines.extend(
                    [
                        f'<a id="{comment_id}"></a>',
                        "",
                        f"[^{comment_id}]: {rec.get('author', '')} {rec.get('date', '')}: {rec.get('text', '')}",
                        "",
                    ]
                )

    md_path.write_text("\n".join(lines), encoding="utf-8")


def build_matrix_files(state: BuildState) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    matrices: list[tuple[str, list[dict[str, str]], list[str]]] = [
        (
            "source-register",
            state.sources,
            [
                "document",
                "title",
                "source_file",
                "markdown_file",
                "sha256",
                "modified",
                "creator",
                "last_modified_by",
                "extraction_status",
            ],
        ),
        (
            "section-matrix",
            state.sections,
            ["section_id", "document", "heading_level", "title", "paragraph_id", "evidence_link"],
        ),
        (
            "table-matrix",
            state.tables,
            [
                "table_id",
                "document",
                "section_id",
                "section_title",
                "rows",
                "columns",
                "csv_file",
                "evidence_link",
                "preview",
            ],
        ),
        (
            "comment-matrix",
            state.comments,
            [
                "comment_id",
                "document",
                "author",
                "date",
                "anchor_id",
                "anchor_link",
                "section_id",
                "section_title",
                "text",
            ],
        ),
        (
            "evidence-matrix",
            state.evidence,
            [
                "id",
                "document",
                "source_kind",
                "knowledge_types",
                "location",
                "section_id",
                "section_title",
                "extract",
                "evidence_link",
                "status",
            ],
        ),
    ]

    rule_rows = [r for r in state.evidence if "rule_or_criterion" in r["knowledge_types"]]
    issue_rows = [r for r in state.evidence if "issue_or_question" in r["knowledge_types"]]
    workflow_rows = [r for r in state.evidence if "workflow_or_method" in r["knowledge_types"]]
    object_rows = [r for r in state.evidence if "model_or_data_object" in r["knowledge_types"]]
    terminology_rows = sorted(state.terminology.values(), key=lambda r: (r["term"]))
    traceability_rows = [
        {
            "trace_id": f"TR-{i:04d}",
            "evidence_id": r["id"],
            "document": r["document"],
            "knowledge_types": r["knowledge_types"],
            "source_kind": r["source_kind"],
            "source_location": r["location"],
            "evidence_link": r["evidence_link"],
            "review_status": r["status"],
            "canonical_note": "",
            "decision_or_issue": "",
        }
        for i, r in enumerate(state.evidence, start=1)
    ]
    image_rows = state.images

    matrices.extend(
        [
            (
                "rule-matrix",
                rule_rows,
                [
                    "id",
                    "document",
                    "source_kind",
                    "location",
                    "section_title",
                    "extract",
                    "evidence_link",
                    "status",
                ],
            ),
            (
                "issue-matrix",
                issue_rows,
                [
                    "id",
                    "document",
                    "source_kind",
                    "location",
                    "section_title",
                    "extract",
                    "evidence_link",
                    "status",
                ],
            ),
            (
                "workflow-matrix",
                workflow_rows,
                [
                    "id",
                    "document",
                    "source_kind",
                    "location",
                    "section_title",
                    "extract",
                    "evidence_link",
                    "status",
                ],
            ),
            (
                "model-object-matrix",
                object_rows,
                [
                    "id",
                    "document",
                    "source_kind",
                    "location",
                    "section_title",
                    "extract",
                    "evidence_link",
                    "status",
                ],
            ),
            (
                "terminology-matrix",
                terminology_rows,
                ["term", "occurrences", "documents", "first_evidence_link", "notes"],
            ),
            (
                "traceability-matrix",
                traceability_rows,
                [
                    "trace_id",
                    "evidence_id",
                    "document",
                    "knowledge_types",
                    "source_kind",
                    "source_location",
                    "evidence_link",
                    "review_status",
                    "canonical_note",
                    "decision_or_issue",
                ],
            ),
            (
                "image-register",
                image_rows,
                ["document", "source_file", "asset", "original_member"],
            ),
        ]
    )

    for name, rows, fields in matrices:
        write_csv(DATA_DIR / f"{name}.csv", rows, fields)
        csv_to_md_table(DATA_DIR / f"{name}.md", rows, fields)

    write_jsonl(DATA_DIR / "evidence-matrix.jsonl", state.evidence)
    build_graph_exports(state)


def build_graph_exports(state: BuildState) -> None:
    graph_dir = DIATAXIS_DIR / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []

    def add_node(node_id: str, label: str, node_type: str, **props: str) -> None:
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
            **{k: str(v) for k, v in props.items()},
        }

    def add_edge(source: str, target: str, relation: str, evidence_id: str = "") -> None:
        edges.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "evidence_id": evidence_id,
            }
        )

    for row in state.sources:
        add_node(
            row["document"],
            row["source_file"],
            "Document",
            title=row["title"],
            evidence_link=row["markdown_file"],
        )
        root_section_id = f"{row['document']}-S000"
        add_node(
            root_section_id,
            "Document root",
            "Section",
            document=row["document"],
            evidence_link=row["markdown_file"],
        )
        add_edge(row["document"], root_section_id, "CONTAINS")

    for row in state.sections:
        add_node(
            row["section_id"],
            row["title"],
            "Section",
            document=row["document"],
            evidence_link=row["evidence_link"],
        )
        add_edge(row["document"], row["section_id"], "CONTAINS")

    for row in state.tables:
        add_node(
            row["table_id"],
            row["table_id"],
            "Table",
            document=row["document"],
            section_id=row["section_id"],
            evidence_link=row["evidence_link"],
        )
        add_edge(row["section_id"] or row["document"], row["table_id"], "CONTAINS_TABLE")

    for row in state.comments:
        add_node(
            row["comment_id"],
            truncate(row["text"], 80),
            "Comment",
            document=row["document"],
            author=row["author"],
            evidence_link=row["anchor_link"],
        )
        parent = row["anchor_id"] or row["document"]
        if parent not in nodes:
            add_node(
                parent,
                parent,
                "Anchor",
                document=row["document"],
                evidence_link=row["anchor_link"],
            )
        add_edge(parent, row["comment_id"], "HAS_COMMENT")

    for row in state.evidence:
        add_node(
            row["id"],
            truncate(row["extract"], 80),
            "Evidence",
            document=row["document"],
            knowledge_types=row["knowledge_types"],
            evidence_link=row["evidence_link"],
            status=row["status"],
        )
        parent = row["section_id"] or row["document"]
        add_edge(parent, row["id"], "HAS_EVIDENCE", row["id"])
        for kind in row["knowledge_types"].split("; "):
            kind_id = f"KT-{slugify(kind).upper()}"
            add_node(kind_id, kind, "KnowledgeType")
            add_edge(row["id"], kind_id, "CLASSIFIED_AS", row["id"])
        for term in term_hits(row["extract"]):
            term_id = f"TERM-{term}"
            add_node(term_id, term, "Term")
            add_edge(row["id"], term_id, "MENTIONS_TERM", row["id"])

    node_fields = ["id", "label", "type", "document", "title", "section_id", "author", "knowledge_types", "evidence_link", "status"]
    edge_fields = ["source", "target", "relation", "evidence_id"]
    node_rows = list(nodes.values())
    write_csv(graph_dir / "nodes.csv", node_rows, node_fields)
    write_csv(graph_dir / "edges.csv", edges, edge_fields)
    csv_to_md_table(graph_dir / "nodes.md", node_rows, node_fields)
    csv_to_md_table(graph_dir / "edges.md", edges, edge_fields)
    (graph_dir / "knowledge-graph.jsonld").write_text(
        json.dumps(
            {
                "@context": {
                    "id": "@id",
                    "type": "@type",
                    "label": "http://www.w3.org/2000/01/rdf-schema#label",
                    "relation": "https://aimsun.com/drieat/relation",
                    "evidence_link": "https://aimsun.com/drieat/evidence_link",
                },
                "nodes": node_rows,
                "edges": edges,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_scaffold(state: BuildState) -> None:
    for subdir in [
        "tutorials",
        "how-to",
        "explanations",
        "reference",
        "decisions",
        "open-questions",
        "graph",
    ]:
        (DIATAXIS_DIR / subdir).mkdir(parents=True, exist_ok=True)

    (DIATAXIS_DIR / "reference" / "validation-criteria.md").write_text(
        """# Validation Criteria Reference

Status: auto-seeded from the rule matrix; requires modeller review before use as canonical criteria.

Primary source matrix: [rule-matrix](../../data/rule-matrix.md)

Recommended curation fields:

- stable criterion ID
- source evidence ID
- KPI
- population and exclusions
- temporal aggregation
- formula
- threshold
- pass/fail boundary
- missing-value behaviour
- accepted implementation
- reviewer and date
""",
        encoding="utf-8",
    )

    (DIATAXIS_DIR / "reference" / "known-issues-and-limitations.md").write_text(
        """# Known Issues and Limitations

Status: auto-seeded from comments and issue-like evidence; requires DRIEAT/Aimsun review.

Primary source matrix: [issue-matrix](../../data/issue-matrix.md)

Issue records should retain:

- evidence ID and source link
- impacted workflow or model object
- severity
- owner
- decision required
- accepted resolution
""",
        encoding="utf-8",
    )

    (DIATAXIS_DIR / "reference" / "model-object-registry.md").write_text(
        """# Model Object Registry

Status: auto-seeded from object-like document references; must be resolved against the delivered Aimsun model.

Primary source matrix: [model-object-matrix](../../data/model-object-matrix.md)

Resolution states:

- unresolved
- exact model object found
- multiple candidates
- obsolete name
- documented but missing from delivered model
""",
        encoding="utf-8",
    )

    (DIATAXIS_DIR / "how-to" / "reproduce-2023-base-validation.md").write_text(
        """# Reproduce the 2023 Base Validation

Status: placeholder generated from the audit plan.

This guide should be authored only after the workflow matrix, validation criteria, and model-object registry have been reviewed.

Evidence to curate first:

- [workflow-matrix](../../data/workflow-matrix.md)
- [rule-matrix](../../data/rule-matrix.md)
- [model-object-matrix](../../data/model-object-matrix.md)
- [traceability-matrix](../../data/traceability-matrix.md)
""",
        encoding="utf-8",
    )

    (OUT / "README.md").write_text(
        f"""# DRIEAT Knowledge Structure

Generated: {datetime.now(timezone.utc).isoformat()}

This vault converts the supplied DRIEAT report corpus into Markdown and reviewable knowledge matrices. The automated extraction is evidence-backed but not yet canonical: every rule, issue, workflow, object reference, and term should be reviewed before being used as accepted operational knowledge.

## Source Corpus

The original DOCX files copied for processing are in `../sources/docx/`.

Converted Markdown:

{chr(10).join(f"- [{row['document']} - {row['source_file']}](corpus/markdown/{Path(row['markdown_file']).name})" for row in state.sources)}

## Main Matrices

- [Source register](data/source-register.md)
- [Section matrix](data/section-matrix.md)
- [Evidence matrix](data/evidence-matrix.md)
- [Rule matrix](data/rule-matrix.md)
- [Issue matrix](data/issue-matrix.md)
- [Workflow matrix](data/workflow-matrix.md)
- [Model/object matrix](data/model-object-matrix.md)
- [Terminology matrix](data/terminology-matrix.md)
- [Traceability matrix](data/traceability-matrix.md)
- [Comment matrix](data/comment-matrix.md)
- [Table matrix](data/table-matrix.md)
- [Image register](data/image-register.md)

Graph exports:

- [Graph nodes](diataxis/graph/nodes.md)
- [Graph edges](diataxis/graph/edges.md)
- [JSON-LD graph](diataxis/graph/knowledge-graph.jsonld)

## Diátaxis Scaffold

- `diataxis/tutorials/`
- `diataxis/how-to/`
- `diataxis/explanations/`
- `diataxis/reference/`
- `diataxis/decisions/`
- `diataxis/open-questions/`
- `diataxis/graph/`

## Review Discipline

Use the `traceability-matrix` as the control surface. Promote an extracted item to canonical knowledge only after the evidence link, section context, model-object identity, and reviewer status are checked.
""",
        encoding="utf-8",
    )

    (OUT / "knowledge-graph-ontology.md").write_text(
        """# Knowledge-Graph Ontology

This ontology follows the attached audit plan and is intended as the curation target for the extracted matrices.

## Core Nodes

Document, Section, Table, Figure, Comment, Claim, Rule, Definition, Assumption, Decision, Issue, Workflow, WorkflowStep, Dataset, Observation, ModelArtifact, Scenario, Experiment, TrafficDemand, TrafficProfile, PathAssignmentPlan, Horizon, GeometryConfiguration, RoadType, Subpath, ValidationCriterion, KPI, ValidationResult.

## Core Edges

- Document CONTAINS Section
- Claim EXTRACTED_FROM Section
- Comment CHALLENGES Claim
- Rule APPLIES_TO Dataset, WorkflowStep, KPI, or ModelObject
- WorkflowStep CONSUMES Input
- WorkflowStep PRODUCES Output
- WorkflowStep PRECEDES WorkflowStep
- ValidationCriterion EVALUATES KPI
- ValidationResult TESTS ValidationCriterion
- Scenario USES TrafficDemand, GeometryConfiguration, or ModifiedAttribute
- Issue AFFECTS Reproducibility, Validity, or Usability
- Decision RESOLVES OpenQuestion

## Required Provenance Fields

- stable ID
- source document
- source section/table/comment/paragraph
- evidence link
- verbatim extract
- authority level
- evidence class
- confidence
- review status
- reviewer
- reviewed date
""",
        encoding="utf-8",
    )


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for path in [MARKDOWN_DIR, ASSETS_DIR, TABLES_DIR, DATA_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    state = BuildState([], [], [], [], [], {}, [])
    docs = sorted(DOCX_DIR.glob("*.docx"), key=lambda p: doc_code(p))
    if not docs:
        raise SystemExit(f"No .docx files found in {DOCX_DIR}")
    for doc in docs:
        print(f"Converting {doc.name}")
        process_docx(doc, state)
    build_matrix_files(state)
    write_scaffold(state)
    print(f"Converted {len(state.sources)} documents")
    print(f"Sections: {len(state.sections)}")
    print(f"Tables: {len(state.tables)}")
    print(f"Comments: {len(state.comments)}")
    print(f"Evidence items: {len(state.evidence)}")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
