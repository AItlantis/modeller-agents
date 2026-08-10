"""Fixture-based tests for the inbox discovery-draft checks (schema section 5).

These tests are self-contained (fixture vaults under fixtures/), never touching
the real modelling-knowledge vault.
"""

from pathlib import Path

from modeller_memory.tools.vault_doctor import checks
from modeller_memory.tools.vault_doctor.cli import main
from modeller_memory.tools.vault_doctor.loader import load_vault

FIXTURES = Path(__file__).parent / "fixtures"
INBOX_CLEAN = FIXTURES / "inbox_vault"
BROKEN_INBOX = FIXTURES / "broken_inbox"

MISSING_FIELD = BROKEN_INBOX / "missing_field"
AUTHORITY_INFLATION = BROKEN_INBOX / "authority_inflation"
INVALID_STATUS = BROKEN_INBOX / "invalid_status"
RESTRICTED_LEAK = BROKEN_INBOX / "restricted_leak"


def _blocking_ids(vault_path):
    vault = load_vault(vault_path)
    blocking, _ = checks.run_all(vault)
    return {f.check for f in blocking}


# --- clean draft passes ---------------------------------------------------- #

def test_clean_inbox_has_no_blocking_findings():
    vault = load_vault(INBOX_CLEAN)
    blocking, _ = checks.run_all(vault)
    assert blocking == [], "clean inbox must have no blocking findings: " + "; ".join(
        f.format() for f in blocking
    )


def test_check_cli_passes_clean_inbox():
    assert main(["check", "--vault-path", str(INBOX_CLEAN)]) == 0


def test_readme_and_promoted_draft_are_not_errors():
    # The inbox README (a process doc) is skipped; the promoted-draft (carries a
    # promoted_to pointer) is a well-formed draft and must not error.
    ids = _blocking_ids(INBOX_CLEAN)
    assert ids == set()


# --- broken drafts block --------------------------------------------------- #

def test_missing_required_field_blocks():
    ids = _blocking_ids(MISSING_FIELD)
    assert "draft-missing-required-field" in ids
    assert main(["check", "--vault-path", str(MISSING_FIELD)]) == 1


def test_authority_inflation_blocks():
    ids = _blocking_ids(AUTHORITY_INFLATION)
    assert "draft-authority-inflation" in ids
    assert main(["check", "--vault-path", str(AUTHORITY_INFLATION)]) == 1


def test_invalid_status_blocks():
    ids = _blocking_ids(INVALID_STATUS)
    # status: accepted trips both the vocab check and the authority-inflation check.
    assert "draft-invalid-status" in ids
    assert "draft-authority-inflation" in ids
    assert main(["check", "--vault-path", str(INVALID_STATUS)]) == 1


def test_restricted_leak_blocks():
    ids = _blocking_ids(RESTRICTED_LEAK)
    assert "draft-restricted-leak" in ids
    assert main(["check", "--vault-path", str(RESTRICTED_LEAK)]) == 1
