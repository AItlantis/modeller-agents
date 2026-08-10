from __future__ import annotations

from modeller_memory.tools.drieat_import.cli import build_parser


def test_drieat_import_parser_accepts_subcommands() -> None:
    parser = build_parser()

    assert parser.parse_args(["build"]).command == "build"
    assert parser.parse_args(["validate-source"]).command == "validate-source"
    assert parser.parse_args(["install"]).command == "install"
    assert parser.parse_args(["validate-package"]).command == "validate-package"


def test_drieat_import_parser_accepts_explicit_paths() -> None:
    parser = build_parser()

    args = parser.parse_args(["install", "--source-vault", "source-vault", "--target-repo", "target-repo"])

    assert args.command == "install"
    assert args.source_vault == "source-vault"
    assert args.target_repo == "target-repo"
