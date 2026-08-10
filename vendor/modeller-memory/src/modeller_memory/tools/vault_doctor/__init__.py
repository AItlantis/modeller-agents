"""vault_doctor — read-only validation and index export for an Obsidian vault.

Host-agnostic CLI tool. It is pointed at a vault via ``--vault-path`` and it
never writes, moves, or deletes any vault file. It only enforces rules the vault
itself declares (see the ``modelling-knowledge`` vault-alignment-plan and
knowledge-metadata-standard). It is explicitly NOT wired into the memory runtime.
"""

__all__ = ["cli", "checks", "export", "loader", "model"]
