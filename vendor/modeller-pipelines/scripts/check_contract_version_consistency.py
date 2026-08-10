# Stdlib-only, per ADR-0001's no-added-runtime-dependency posture.
"""check_contract_version_consistency — CI check for CONTRACT_REVISION_PROPOSAL.md SS3a.

Verifies that every normative doc's "Contract version:" banner in `contracts/*.md`
and every embedded version segment in `contracts/schemas/*.json`'s `$id` field agree
with the single source of truth, `contracts/VERSION`.

Usage:
    python scripts/check_contract_version_consistency.py [--contracts-dir <dir>]

Exit 0 if every file agrees with the version in `contracts/VERSION`.
Exit 1 (with every offending file and its found, wrong version listed) otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Matches e.g. "**Contract version:** 1.2" (bold markdown label, case-insensitive,
# tolerant of the bold markers being absent).
MD_BANNER_RE = re.compile(
    r"contract version:\*{0,2}\s*([0-9]+(?:\.[0-9]+)*)",
    re.IGNORECASE,
)

# Matches the version segment embedded in a schema $id, e.g.
# ".../modeller-pipelines/contracts/1.2/backend.schema.json".
SCHEMA_ID_RE = re.compile(r'"\$id"\s*:\s*"[^"]*?/contracts/([0-9]+(?:\.[0-9]+)*)/')


def _read_expected_version(contracts_dir: Path) -> str:
    version_path = contracts_dir / "VERSION"
    if not version_path.is_file():
        raise SystemExit(f"ERROR: version source of truth not found: {version_path}")
    return version_path.read_text(encoding="utf-8").strip()


def _check_markdown_files(contracts_dir: Path, expected: str) -> list[str]:
    mismatches = []
    for md_path in sorted(contracts_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        match = MD_BANNER_RE.search(text)
        if match is None:
            mismatches.append(
                f"{md_path}: no 'Contract version:' banner found "
                f"(expected {expected})"
            )
            continue
        found = match.group(1)
        if found != expected:
            mismatches.append(
                f"{md_path}: banner says {found}, contracts/VERSION says {expected}"
            )
    return mismatches


def _check_schema_files(schemas_dir: Path, expected: str) -> list[str]:
    mismatches = []
    for schema_path in sorted(schemas_dir.glob("*.json")):
        text = schema_path.read_text(encoding="utf-8")
        match = SCHEMA_ID_RE.search(text)
        if match is None:
            mismatches.append(
                f"{schema_path}: no versioned $id segment found (expected {expected})"
            )
            continue
        found = match.group(1)
        if found != expected:
            mismatches.append(
                f"{schema_path}: $id says {found}, contracts/VERSION says {expected}"
            )
    return mismatches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contracts-dir",
        default=str(REPO_ROOT / "contracts"),
        help="Path to the contracts/ directory to check (default: repo's contracts/).",
    )
    args = parser.parse_args(argv)

    contracts_dir = Path(args.contracts_dir)
    schemas_dir = contracts_dir / "schemas"

    if not contracts_dir.is_dir():
        print(f"ERROR: contracts dir not found: {contracts_dir}", file=sys.stderr)
        return 1

    expected = _read_expected_version(contracts_dir)

    mismatches = []
    mismatches.extend(_check_markdown_files(contracts_dir, expected))
    if schemas_dir.is_dir():
        mismatches.extend(_check_schema_files(schemas_dir, expected))

    if mismatches:
        print(
            f"Contract version consistency check FAILED "
            f"(contracts/VERSION == {expected}):",
            file=sys.stderr,
        )
        for line in mismatches:
            print(f"  - {line}", file=sys.stderr)
        print(
            "\nFix each listed file so its version matches contracts/VERSION, "
            "or bump contracts/VERSION if this is an intentional release.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: all contracts/*.md and contracts/schemas/*.json agree on version {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
