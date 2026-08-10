"""DRIEAT document-corpus import tooling.

This tool prepares a restricted document evidence package for the
``modelling-knowledge`` vault. It follows the same host-agnostic tooling
boundary as ``vault_doctor``: explicit paths or repository-relative defaults,
no runtime memory coupling.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import build_knowledge_structure
from . import install_modelling_knowledge_package
from . import validate_modelling_knowledge_package
from . import validate_source_vault


def _set_env(name: str, value: str | None) -> None:
    if value:
        os.environ[name] = str(Path(value).expanduser().resolve())


def _cmd_build(args: argparse.Namespace) -> int:
    _set_env("DRIEAT_KNOWLEDGE_WORKDIR", args.workdir)
    build_knowledge_structure.main()
    return 0


def _cmd_validate_source(args: argparse.Namespace) -> int:
    _set_env("DRIEAT_SOURCE_VAULT", args.source_vault)
    validate_source_vault.main()
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    _set_env("DRIEAT_SOURCE_VAULT", args.source_vault)
    _set_env("MODELLING_KNOWLEDGE_REPO", args.target_repo)
    install_modelling_knowledge_package.main()
    return 0


def _cmd_validate_package(args: argparse.Namespace) -> int:
    _set_env("MODELLING_KNOWLEDGE_REPO", args.target_repo)
    validate_modelling_knowledge_package.main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drieat-import",
        description="Convert DRIEAT DOCX reports into a modelling-knowledge acquisition package.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build the intermediate Markdown/matrix source vault.")
    p_build.add_argument(
        "--workdir",
        default=None,
        help="DRIEAT working directory containing sources/docx and receiving vault/ output.",
    )
    p_build.set_defaults(func=_cmd_build)

    p_validate_source = sub.add_parser("validate-source", help="Validate the intermediate source vault.")
    p_validate_source.add_argument(
        "--source-vault",
        default=None,
        help="Path to the generated DRIEAT source vault (default: sibling workspace drieat_knowledge_structure/vault).",
    )
    p_validate_source.set_defaults(func=_cmd_validate_source)

    p_install = sub.add_parser("install", help="Install the standardized package into modelling-knowledge.")
    p_install.add_argument("--source-vault", default=None, help="Path to the generated DRIEAT source vault.")
    p_install.add_argument("--target-repo", default=None, help="Path to the modelling-knowledge repository.")
    p_install.set_defaults(func=_cmd_install)

    p_validate_package = sub.add_parser("validate-package", help="Validate the installed modelling-knowledge package.")
    p_validate_package.add_argument("--target-repo", default=None, help="Path to the modelling-knowledge repository.")
    p_validate_package.set_defaults(func=_cmd_validate_package)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
