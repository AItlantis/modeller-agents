"""Fixture-based tests for vault_doctor checks and the check CLI exit code."""

import json
from pathlib import Path

import pytest

from modeller_memory.tools.vault_doctor import checks
from modeller_memory.tools.vault_doctor import model
from modeller_memory.tools.vault_doctor.cli import main
from modeller_memory.tools.vault_doctor.loader import Note, load_vault

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = FIXTURES / "clean_vault"
BROKEN = FIXTURES / "broken_vault"
WORKSPACE = Path(__file__).resolve().parents[2].parent
VAULT = WORKSPACE / "modelling-knowledge"
SHARED_ELIGIBILITY_FIXTURE = VAULT / "docs" / "dev" / "fixtures" / "eligibility-conformance.json"


def _blocking(vault_path):
    vault = load_vault(vault_path)
    blocking, _warnings = checks.run_all(vault)
    return blocking


def test_clean_vault_has_no_blocking_findings():
    blocking = _blocking(CLEAN)
    assert blocking == [], "clean fixture must have no blocking findings: " + "; ".join(
        f.format() for f in blocking
    )


def test_check_cli_exits_zero_on_clean_vault():
    assert main(["check", "--vault-path", str(CLEAN)]) == 0


def test_check_cli_exits_nonzero_on_broken_vault():
    assert main(["check", "--vault-path", str(BROKEN)]) == 1


def test_broken_vault_surfaces_expected_checks():
    blocking = _blocking(BROKEN)
    ids = {f.check for f in blocking}
    # The deliberately-broken fixture triggers each of these blocking checks.
    assert "duplicate-note-id" in ids
    assert "invalid-status" in ids
    assert "missing-stable-id" in ids
    assert "broken-internal-link" in ids


def test_warnings_do_not_fail_clean_vault():
    vault = load_vault(CLEAN)
    _blocking, warnings = checks.run_all(vault)
    # Clean vault may carry warnings (e.g. sparse links) but must still pass.
    assert main(["check", "--vault-path", str(CLEAN)]) == 0
    # warnings-as-errors flips only warnings to failure; if none, still passes.
    rc = main(["check", "--vault-path", str(CLEAN), "--warnings-as-errors"])
    assert rc == (1 if warnings else 0)


def test_missing_vault_path_returns_2(tmp_path):
    missing = tmp_path / "no-such-vault"
    assert main(["check", "--vault-path", str(missing)]) == 2


def test_restricted_note_is_not_a_blocking_finding_by_itself():
    # A well-formed restricted note in the clean vault must not fail the check.
    blocking = _blocking(CLEAN)
    assert not any("restricted" in f.check for f in blocking)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _active_domain_vault(tmp_path: Path, *, index_note: str = "sample-index") -> Path:
    root = tmp_path / "vault"
    _write(
        root / "registry" / "knowledge-domains.yml",
        f"""schema_version: 1
registry_owner: modelling-knowledge
status: active
routable: true

domains:
  sample:
    title: Sample Domain
    status: active
    routable: true
    sensitivity_ceiling: public
    aliases:
      - sample-domain
    index_note: {index_note}
    allowed_note_types:
      - explanation
      - reference
""",
    )
    _write(
        root / "domains" / "sample" / "_index.md",
        """---
title: Sample Domain Index
status: accepted
type: reference
owner: modelling-knowledge
id: sample-index
domain: sample
authority_level: authoritative
sensitivity: public
last_reviewed: 2026-07-11
---

# Sample Domain Index
""",
    )
    _write(
        root / "domains" / "sample" / "overview.md",
        """---
title: Sample Overview
status: accepted
type: explanation
owner: modelling-knowledge
id: sample-overview
domain: sample
authority_level: authoritative
sensitivity: public
last_reviewed: 2026-07-11
---

# Sample Overview
""",
    )
    return root


def test_active_domain_registry_passes_with_index_and_eligible_note(tmp_path):
    blocking = _blocking(_active_domain_vault(tmp_path))
    assert blocking == []


def _live_domain_spec(vault, dom_id: str) -> dict | None:
    """Return the full registry spec for a domain even if it is not active.

    _active_domain_specs only returns active/routable domains. A synthetic case
    supplies its own status/routable overrides, but still needs the domain's real
    constraints (allowed_note_types, sensitivity_ceiling) from the registry.
    """
    domains, err = checks._load_domain_registry(vault)
    if err is not None or not isinstance(domains, dict):
        return None
    spec = domains.get(dom_id)
    return spec or None


def _synthetic_note_from_export_row(row: dict) -> Note:
    """Materialize a shared-fixture export-index row into a loaded Note.

    The synthetic_note is an export/vault-index row shape; the memory eligibility
    rule (checks._eligible_for_domain) works on a loaded Note (front_matter +
    profile + note_id). Map export fields onto the front-matter keys the rule
    reads and force PROFILE_ACCEPTED (a domain note that reached the export index
    is accepted-knowledge by construction).
    """
    front_matter = {
        "id": row.get("id"),
        "title": row.get("title"),
        "status": row.get("status"),
        "domain": row.get("domain"),
        "authority_level": row.get("authority_level"),
        "superseded_by": row.get("superseded_by"),
        "sensitivity": row.get("sensitivity"),
        "type": row.get("type"),
    }
    return Note(
        rel_path=row.get("canonical_path", ""),
        abs_path=Path(row.get("canonical_path", "")),
        front_matter=front_matter,
        front_matter_error=None,
        body="",
        profile=model.PROFILE_ACCEPTED,
    )


def test_shared_eligibility_conformance_fixture():
    if not SHARED_ELIGIBILITY_FIXTURE.is_file():
        pytest.skip("sibling modelling-knowledge shared eligibility fixture is not available")
    vault = load_vault(VAULT)
    active, parse_findings = checks._active_domain_specs(vault)
    assert parse_findings == []
    fixture = json.loads(SHARED_ELIGIBILITY_FIXTURE.read_text(encoding="utf-8"))

    # Live-vault cases assert eligibility against the REAL registry. When a case's
    # domain is intentionally deactivated (F-A: status draft / routable false), the
    # domain is not in _active_domain_specs and the routability-dependent
    # expectation cannot hold; skip such cases rather than fail. The synthetic
    # cases below are the recurring coverage and do not depend on live F-A state.
    evaluated_live = 0
    for case in fixture["cases"]:
        spec = active.get(case["domain"])
        if spec is None:
            # Domain not active/routable in the live registry -> case not meaningful.
            continue
        matches = vault.by_id.get(case["note_id"]) or []
        assert matches, f"{case['id']}: note_id does not resolve"
        actual = checks._eligible_for_domain(matches[0], case["domain"], spec)
        assert actual is case["expected"], f"{case['id']}: {case['reason']}"
        evaluated_live += 1

    # Synthetic cases are self-contained: they carry their own note row and domain
    # overrides so they exercise eligibility edges regardless of live F-A state.
    evaluated_synthetic = 0
    for case in fixture.get("synthetic_cases", []):
        if "vault_doctor" not in case.get("applies_to", []):
            # e.g. the stale-digest case is agent-side only; memory must skip it.
            continue
        base_spec = active.get(case["domain"]) or _live_domain_spec(vault, case["domain"])
        assert base_spec is not None, f"{case['id']}: domain missing from registry"
        spec = dict(base_spec)
        spec.update(case.get("synthetic_domain_overrides") or {})
        note = _synthetic_note_from_export_row(case["synthetic_note"])
        actual = checks._eligible_for_domain(note, case["domain"], spec)
        assert actual is case["expected"], f"{case['id']}: {case['reason']}"
        evaluated_synthetic += 1

    assert evaluated_synthetic > 0, "expected at least one vault_doctor synthetic case"


def test_active_domain_registry_requires_index_note(tmp_path):
    blocking = _blocking(_active_domain_vault(tmp_path, index_note="missing-index"))
    ids = {f.check for f in blocking}
    assert "active-domain-index-note" in ids
