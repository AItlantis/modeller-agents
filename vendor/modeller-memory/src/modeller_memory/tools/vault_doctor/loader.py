"""Read-only vault loader: walk, parse front matter, resolve links.

Strictly read-only against the vault. It parses ``.md`` files, extracts YAML
front matter, and records the wikilink / relative-markdown-link graph so
checks.py can detect broken internal links.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import model

# Directories excluded from the walk entirely.
EXCLUDED_DIRS = frozenset([".git", "templates", ".obsidian", "node_modules", ".venv"])

# Generated artifact extensions excluded from the note set.
EXCLUDED_SUFFIXES = frozenset([".json", ".csv"])

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Fenced code blocks (``` or ~~~), including the info string and content.
_FENCE_RE = re.compile(r"(?ms)^([ \t]*)(`{3,}|~{3,}).*?\n.*?^\1\2[ \t]*$")
# Inline code spans (`code`), one or more backticks.
_INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")
# Wikilinks: [[target]] or [[target|alias]] or [[target#heading]]
_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")
# Markdown links: [text](target) — capture target, skip external/anchors/images
_MDLINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")


@dataclass
class Note:
    """A parsed vault note (Markdown file with optional YAML front matter)."""

    rel_path: str  # POSIX, vault-relative, e.g. "domains/accessibility/workflow.md"
    abs_path: Path
    front_matter: dict
    front_matter_error: str | None
    body: str
    profile: str
    wikilinks: list[str] = field(default_factory=list)
    md_links: list[str] = field(default_factory=list)
    size_bytes: int = 0
    line_count: int = 0

    @property
    def note_id(self):
        v = self.front_matter.get("id")
        return v if isinstance(v, str) and v.strip() else None

    @property
    def title(self):
        v = self.front_matter.get("title")
        return v if isinstance(v, str) else self.rel_path

    @property
    def status(self):
        return self.front_matter.get("status")

    @property
    def sensitivity(self):
        return self.front_matter.get("sensitivity")


@dataclass
class Vault:
    """The parsed, indexed vault."""

    root: Path
    notes: list[Note]
    tracked_files: list[str]  # POSIX rel paths of git-tracked files (may be empty)

    # Resolution indexes (built in __post_init__).
    by_rel_path: dict = field(default_factory=dict)
    by_id: dict = field(default_factory=dict)  # id -> list[Note] (dupes possible)
    by_basename_noext: dict = field(default_factory=dict)  # "workflow" -> [Note,...]
    _link_targets: set = field(default_factory=set)  # resolvable link keys

    def __post_init__(self):
        self.by_rel_path = {n.rel_path: n for n in self.notes}
        self.by_id = {}
        self.by_basename_noext = {}
        self._link_targets = set()
        for n in self.notes:
            if n.note_id:
                self.by_id.setdefault(n.note_id, []).append(n)
            base = n.rel_path.rsplit("/", 1)[-1]
            base_noext = base[:-3] if base.endswith(".md") else base
            self.by_basename_noext.setdefault(base_noext, []).append(n)
            # Link resolution keys: full rel path, without .md, and bare basename.
            self._link_targets.add(n.rel_path)
            self._link_targets.add(n.rel_path[:-3] if n.rel_path.endswith(".md") else n.rel_path)
            self._link_targets.add(base_noext)

    def resolves(self, link_target: str, from_note: Note) -> bool:
        """Return True if a wikilink/relative-md link target resolves to a note.

        Obsidian resolves wikilinks by note name (basename without extension),
        by path from the vault root, or by relative path. We accept all three.
        External links (http/https/mailto) and pure anchors are treated as
        resolvable (out of scope for internal-link integrity).
        """
        t = link_target.strip()
        if not t:
            return True  # empty target — nothing to resolve
        low = t.lower()
        if low.startswith(("http://", "https://", "mailto:", "#")):
            return True

        # Strip trailing anchor and query.
        t = t.split("#", 1)[0].split("?", 1)[0].strip()
        if not t:
            return True
        # Normalize backslashes.
        t = t.replace("\\", "/")

        candidates = set()
        # As given (vault-root relative).
        candidates.add(t)
        candidates.add(t[:-3] if t.endswith(".md") else t)
        candidates.add(t + ".md")
        # Bare basename.
        base = t.rsplit("/", 1)[-1]
        candidates.add(base)
        candidates.add(base[:-3] if base.endswith(".md") else base)
        candidates.add(base + ".md")
        # Relative to the linking note's directory.
        from_dir = from_note.rel_path.rsplit("/", 1)[0] if "/" in from_note.rel_path else ""
        if from_dir:
            joined = os.path.normpath(f"{from_dir}/{t}").replace("\\", "/")
            candidates.add(joined)
            candidates.add(joined[:-3] if joined.endswith(".md") else joined)

        return any(c in self._link_targets for c in candidates if c)


def _strip_code(body: str) -> str:
    """Remove fenced code blocks and inline code spans (replace with blanks).

    Newlines inside fences are preserved so line-based context is not shifted.
    """
    def _blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    body = _FENCE_RE.sub(_blank, body)
    body = _INLINE_CODE_RE.sub(_blank, body)
    return body


def _parse_front_matter(text: str):
    """Return (front_matter_dict, body, error_str_or_None)."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text, None
    raw = m.group(1)
    body = text[m.end():]
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return {}, body, f"YAML parse error: {exc}"
    if data is None:
        return {}, body, None
    if not isinstance(data, dict):
        return {}, body, "front matter is not a mapping"
    return data, body, None


def _git_tracked_files(root: Path) -> list[str]:
    """Best-effort list of git-tracked files (POSIX rel paths). Empty on failure."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in out.stdout.splitlines() if line.strip()]


def load_vault(vault_path: str | os.PathLike) -> Vault:
    """Walk ``vault_path`` and return a parsed, indexed Vault (read-only)."""
    root = Path(vault_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"vault path is not a directory: {root}")

    notes: list[Note] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in place.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            abs_path = Path(dirpath) / fname
            rel = abs_path.relative_to(root).as_posix()
            try:
                text = abs_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                try:
                    text = abs_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
            fm, body, err = _parse_front_matter(text)
            profile = model.classify_profile(rel, fm)
            # Strip code (fences + inline spans) before link extraction: Obsidian
            # does not resolve wikilinks/markdown links inside code, and example
            # snippets frequently contain [[...]] / TOML [[table]] headers.
            link_source = _strip_code(body)
            wikilinks = _WIKILINK_RE.findall(link_source)
            md_links = _MDLINK_RE.findall(link_source)
            notes.append(
                Note(
                    rel_path=rel,
                    abs_path=abs_path,
                    front_matter=fm,
                    front_matter_error=err,
                    body=body,
                    profile=profile,
                    wikilinks=[w.strip() for w in wikilinks],
                    md_links=[m.strip() for m in md_links],
                    size_bytes=len(text.encode("utf-8")),
                    line_count=text.count("\n") + 1,
                )
            )

    notes.sort(key=lambda n: n.rel_path)
    tracked = _git_tracked_files(root)
    return Vault(root=root, notes=notes, tracked_files=tracked)
