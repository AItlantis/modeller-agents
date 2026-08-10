"""Self-conformance tests for the template backend.

These unit tests run WITHOUT the full conformance kit and verify the
most critical structural properties of the template.

To run the full conformance kit against the template:
    pytest conformance --backend-root template \
        --backend-cmd "python template/runner/minirunner.py"
"""
import json
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).parent.parent
REPO_ROOT = TEMPLATE_ROOT.parent


# ---------------------------------------------------------------------------
# Structural unit tests (no subprocess, no runtime)
# ---------------------------------------------------------------------------

def test_backend_json_exists():
    assert (TEMPLATE_ROOT / "backend.json").exists()


def test_backend_json_is_valid_json():
    data = json.loads((TEMPLATE_ROOT / "backend.json").read_text())
    assert data["backend_id"] == "template"
    assert data["contract_version"] == "1.2"


def test_backend_json_has_required_fields():
    data = json.loads((TEMPLATE_ROOT / "backend.json").read_text())
    for field in ("backend_id", "contract_version", "pipelines", "smoke_pipeline"):
        assert field in data, f"Missing field: {field}"


def test_pipeline_yml_exists():
    yml = TEMPLATE_ROOT / "pipelines" / "trip_summary" / "trip_summary.pipeline.yml"
    assert yml.exists()


def test_pipeline_yml_is_valid_yaml():
    yml = TEMPLATE_ROOT / "pipelines" / "trip_summary" / "trip_summary.pipeline.yml"
    try:
        import yaml
        data = yaml.safe_load(yml.read_text())
    except ImportError:
        pytest.skip("PyYAML not installed")
    assert data["pipeline_id"] == "trip-summary"
    assert "steps" in data


def test_pipeline_yml_has_required_fields():
    yml = TEMPLATE_ROOT / "pipelines" / "trip_summary" / "trip_summary.pipeline.yml"
    try:
        import yaml
        data = yaml.safe_load(yml.read_text())
    except ImportError:
        pytest.skip("PyYAML not installed")
    for field in ("pipeline_id", "pipeline_name", "version", "steps", "gates"):
        assert field in data, f"Missing field: {field}"


def test_result_builder_produces_valid_shape():
    import sys
    sys.path.insert(0, str(TEMPLATE_ROOT))
    from shared.result_builder import build_step_result, build_run_result

    sr = build_step_result(1, "acquire_trips", "success", "ok")
    assert sr["status"] == "success"
    assert sr["step_id"] == 1
    assert isinstance(sr["artifacts"], list)

    rr = build_run_result(
        contract_version="1.2", backend_id="template",
        pipeline_id="trip-summary", pipeline_version="0.1.0",
        run_id="test-001", status="success",
        started_at="2026-01-01T00:00:00Z", completed_at="2026-01-01T00:00:05Z",
        config_path="config.yml", steps=[sr],
    )
    assert rr["status"] == "success"
    assert rr["contract_version"] == "1.2"
    assert rr["timestamps"]["started_at"] == "2026-01-01T00:00:00Z"
    assert rr["timestamps"]["completed_at"] == "2026-01-01T00:00:05Z"
    assert len(rr["steps"]) == 1


def test_trips_sample_csv_exists_and_has_200_rows():
    csv_path = TEMPLATE_ROOT / "data" / "trips_sample.csv"
    assert csv_path.exists()
    lines = csv_path.read_text().strip().splitlines()
    assert lines[0].startswith("vehicle_id"), "Missing header"
    assert len(lines) == 201, f"Expected 200 data rows + header, got {len(lines) - 1}"


def test_minirunner_under_200_lines():
    runner = TEMPLATE_ROOT / "runner" / "minirunner.py"
    lines = runner.read_text().splitlines()
    assert len(lines) <= 200, f"minirunner.py is {len(lines)} lines — exceeds 200-line budget"


def test_minirunner_result_json_contract_version_matches_backend_json(tmp_path):
    """A live run's result.json must not drift from backend.json's declared
    contract_version (regression test for the hardcoded-literal bug)."""
    import subprocess
    import sys

    backend_data = json.loads((TEMPLATE_ROOT / "backend.json").read_text())
    config = REPO_ROOT / "conformance" / "fixtures" / "smoke_config_template.yml"
    run_dir = tmp_path / "contract_version_run"
    run_dir.mkdir()

    proc = subprocess.run(
        [
            sys.executable, str(TEMPLATE_ROOT / "runner" / "minirunner.py"),
            "run", "trip-summary",
            "--config", str(config),
            "--run-dir", str(run_dir),
        ],
        capture_output=True, text=True, cwd=str(TEMPLATE_ROOT),
    )
    result_path = run_dir / "result.json"
    assert result_path.exists(), (
        f"minirunner.py did not write result.json\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    result_data = json.loads(result_path.read_text())
    assert result_data["contract_version"] == backend_data["contract_version"], (
        f"result.json contract_version {result_data['contract_version']!r} != "
        f"backend.json contract_version {backend_data['contract_version']!r}"
    )


# ---------------------------------------------------------------------------
# Dock structural tests (contract-v1.1)
# ---------------------------------------------------------------------------

_LIB_LINE_BUDGETS = {
    "qt_compat.py": 90,
    "base_dock.py": 110,
    "integration.py": 200,
    "persistence.py": 90,
    "browse_bar.py": 110,
    "status_bar.py": 110,
    "diagnostics.py": 120,
}
_LAUNCHER_LINE_BUDGET = 140


def test_docks_registered_in_backend_json():
    data = json.loads((TEMPLATE_ROOT / "backend.json").read_text())
    dock_ids = {d["dock_id"] for d in data.get("docks", [])}
    assert "demo_dock" in dock_ids
    assert data.get("smoke_dock") == "demo_dock"


def test_dock_launcher_exists_and_under_line_budget():
    launcher = TEMPLATE_ROOT / "docks" / "run_dock_template.py"
    assert launcher.exists()
    lines = launcher.read_text().splitlines()
    assert len(lines) <= _LAUNCHER_LINE_BUDGET, \
        f"run_dock_template.py is {len(lines)} lines — exceeds {_LAUNCHER_LINE_BUDGET}-line budget"


def test_dock_launcher_has_copy_dont_import_header():
    launcher = TEMPLATE_ROOT / "docks" / "run_dock_template.py"
    header = launcher.read_text().splitlines()[0]
    assert header.startswith("# COPY THIS FILE"), \
        "run_dock_template.py must open with the COPY THIS FILE header"


def test_dock_lib_files_exist_have_header_and_under_line_budget():
    lib_dir = TEMPLATE_ROOT / "docks" / "lib"
    for filename, budget in _LIB_LINE_BUDGETS.items():
        path = lib_dir / filename
        assert path.exists(), f"Missing dock lib file: {path}"
        lines = path.read_text().splitlines()
        assert lines[0].startswith("# COPY THIS FILE"), \
            f"{filename} must open with the COPY THIS FILE header"
        assert len(lines) <= budget, \
            f"{filename} is {len(lines)} lines — exceeds {budget}-line budget"


def test_demo_dock_readme_exists_and_nonempty():
    readme = TEMPLATE_ROOT / "docks" / "demo_dock" / "README.md"
    assert readme.exists()
    assert readme.read_text(encoding="utf-8").strip()


def test_demo_dock_widget_defines_setup_ui_and_reset_state():
    widget = TEMPLATE_ROOT / "docks" / "demo_dock" / "demo_dock_widget.py"
    source = widget.read_text()
    assert "def setup_ui(self)" in source
    assert "def reset_state(self)" in source


def test_dock_key_literal_matches_manifest():
    data = json.loads((TEMPLATE_ROOT / "backend.json").read_text())
    manifest_key = next(d["dock_key"] for d in data["docks"] if d["dock_id"] == "demo_dock")
    launcher_source = (TEMPLATE_ROOT / "docks" / "run_dock_template.py").read_text()
    assert manifest_key in launcher_source
