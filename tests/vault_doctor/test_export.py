"""Fixture-based tests for deterministic export and restricted-note fencing."""

from pathlib import Path
import subprocess
import sys

from modeller_memory.tools.vault_doctor import export
from modeller_memory.tools.vault_doctor.loader import load_vault

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = FIXTURES / "clean_vault"


def test_export_index_is_deterministic():
    v1 = load_vault(CLEAN)
    v2 = load_vault(CLEAN)
    b1 = export.dumps(export.build_index(v1))
    b2 = export.dumps(export.build_index(v2))
    assert b1 == b2, "unchanged vault must export byte-identical index"


def test_export_index_digest_stable_across_runs():
    idx1 = export.build_index(load_vault(CLEAN))
    idx2 = export.build_index(load_vault(CLEAN))
    assert idx1["index_digest"] == idx2["index_digest"]


def test_generated_at_omitted_by_default():
    idx = export.build_index(load_vault(CLEAN))
    assert "generated_at" not in idx


def test_generated_at_does_not_perturb_digest():
    a = export.build_index(load_vault(CLEAN), generated_at="2026-01-01T00:00:00Z")
    b = export.build_index(load_vault(CLEAN), generated_at="2099-12-31T23:59:59Z")
    # generated_at is excluded from the digest, so the digest is identical.
    assert a["index_digest"] == b["index_digest"]
    assert a["generated_at"] != b["generated_at"]


def test_restricted_note_is_not_exposable():
    idx = export.build_index(load_vault(CLEAN))
    restricted = [n for n in idx["notes"] if n["sensitivity"] == "restricted"]
    assert restricted, "clean fixture must contain a restricted note"
    for note in restricted:
        assert note["exposable"] is False
        assert note["exposure_scopes"] == []


def test_public_note_is_exposable():
    idx = export.build_index(load_vault(CLEAN))
    public = [n for n in idx["notes"] if n["sensitivity"] == "public"]
    assert public, "clean fixture must contain a public note"
    for note in public:
        assert note["exposable"] is True
        assert "internal-agent" in note["exposure_scopes"]


def test_notes_sorted_by_id():
    idx = export.build_index(load_vault(CLEAN))
    ids = [n["id"] for n in idx["notes"]]
    assert ids == sorted(ids)


def test_export_domains_shape():
    doms = export.build_domains(load_vault(CLEAN))
    assert doms["schema_version"] == 1
    assert any(d["id"] == "sample" for d in doms["domains"])
    for d in doms["domains"]:
        assert "routable" in d
        assert "sensitivity_ceiling" in d
        assert "notes_digest" in d


def test_export_domains_notes_digest_is_deterministic():
    d1 = export.build_domains(load_vault(CLEAN))
    d2 = export.build_domains(load_vault(CLEAN))
    sample1 = next(d for d in d1["domains"] if d["id"] == "sample")
    sample2 = next(d for d in d2["domains"] if d["id"] == "sample")
    assert sample1["notes_digest"].startswith("sha256:")
    assert sample1["notes_digest"] == sample2["notes_digest"]


def test_export_domains_cli_stdout_matches_dumps_bytes():
    expected = export.dumps(export.build_domains(load_vault(CLEAN))).encode("utf-8")
    actual = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "modeller_memory.tools.vault_doctor.cli",
            "export-domains",
            "--vault-path",
            str(CLEAN),
            "--json",
        ]
    )
    assert actual == expected
