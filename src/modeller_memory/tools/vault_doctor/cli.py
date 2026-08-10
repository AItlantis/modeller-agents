"""vault_doctor CLI.

Subcommands:
  check           validate the vault; exit non-zero on any blocking failure.
  export-index    emit the deterministic vault-index JSON.
  export-domains  emit the deterministic knowledge-domains JSON.

The vault path is an explicit ``--vault-path`` argument. Default: a sibling
``../modelling-knowledge`` relative to this repository. No absolute path is
hardcoded. The tool is READ-ONLY against the vault.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks as _checks
from . import export as _export
from .loader import load_vault


def _default_vault_path() -> Path:
    """Discover a sibling ../modelling-knowledge relative to this repo, if present.

    This file lives at <repo>/src/modeller_memory/tools/vault_doctor/cli.py, so
    the repo root is five parents up; the sibling vault is repo_root.parent /
    'modelling-knowledge'.
    """
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root.parent / "modelling-knowledge"


def _resolve_vault_path(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    return _default_vault_path().resolve()


def _add_vault_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--vault-path",
        default=None,
        help="Path to the Obsidian vault to validate (default: sibling ../modelling-knowledge).",
    )


def _cmd_check(args) -> int:
    vault_path = _resolve_vault_path(args.vault_path)
    if not vault_path.is_dir():
        print(f"error: vault path does not exist: {vault_path}", file=sys.stderr)
        return 2
    vault = load_vault(vault_path)
    blocking, warnings = _checks.run_all(vault)

    print(f"vault_doctor check — {vault_path}")
    print(f"  notes scanned: {len(vault.notes)}")
    print(f"  blocking findings: {len(blocking)}")
    print(f"  warning findings:  {len(warnings)}")
    print()

    if blocking:
        print("BLOCKING:")
        for f in blocking:
            print("  " + f.format())
        print()
    if warnings:
        print("WARNINGS:")
        for f in warnings:
            print("  " + f.format())
        print()

    if _checks.NOT_YET_APPLICABLE:
        print("NOT-YET-APPLICABLE (require the knowledge-pack / routable-domain layer):")
        for note in _checks.NOT_YET_APPLICABLE:
            print(f"  - {note}")
        print()

    failed = bool(blocking) or (args.warnings_as_errors and bool(warnings))
    if failed:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS" + (" (warnings present)" if warnings else ""))
    return 0


def _emit(obj, out_path: str | None) -> int:
    data = _export.dumps(obj).encode("utf-8")
    if out_path:
        Path(out_path).write_bytes(data)
        print(f"wrote {out_path}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(data)
    return 0


def _cmd_export_index(args) -> int:
    vault_path = _resolve_vault_path(args.vault_path)
    if not vault_path.is_dir():
        print(f"error: vault path does not exist: {vault_path}", file=sys.stderr)
        return 2
    vault = load_vault(vault_path)
    obj = _export.build_index(vault, generated_at=args.generated_at)
    return _emit(obj, args.output)


def _cmd_export_domains(args) -> int:
    vault_path = _resolve_vault_path(args.vault_path)
    if not vault_path.is_dir():
        print(f"error: vault path does not exist: {vault_path}", file=sys.stderr)
        return 2
    vault = load_vault(vault_path)
    obj = _export.build_domains(vault, generated_at=args.generated_at)
    return _emit(obj, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault-doctor",
        description="Read-only validator and index exporter for the modelling-knowledge vault.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Validate the vault (non-zero exit on blocking failure).")
    _add_vault_arg(p_check)
    p_check.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Treat warnings as failures (off by default; warning-first).",
    )
    p_check.set_defaults(func=_cmd_check)

    p_idx = sub.add_parser("export-index", help="Emit the vault-index JSON.")
    _add_vault_arg(p_idx)
    p_idx.add_argument("--json", action="store_true", help="Emit JSON (default format).")
    p_idx.add_argument("-o", "--output", default=None, help="Write to PATH instead of stdout.")
    p_idx.add_argument(
        "--generated-at",
        default=None,
        help="Optional ISO timestamp to stamp into the export (omitted by default for determinism).",
    )
    p_idx.set_defaults(func=_cmd_export_index)

    p_dom = sub.add_parser("export-domains", help="Emit the knowledge-domains JSON.")
    _add_vault_arg(p_dom)
    p_dom.add_argument("--json", action="store_true", help="Emit JSON (default format).")
    p_dom.add_argument("-o", "--output", default=None, help="Write to PATH instead of stdout.")
    p_dom.add_argument(
        "--generated-at",
        default=None,
        help="Optional ISO timestamp to stamp into the export (omitted by default for determinism).",
    )
    p_dom.set_defaults(func=_cmd_export_domains)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
