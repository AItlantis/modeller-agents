"""Compatibility CLI module for ``python -m modeller_agents.cli``."""

from modeller.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
