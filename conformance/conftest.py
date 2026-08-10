"""Shared fixtures and CLI options for the modeller-pipelines conformance kit."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import pytest

from .helpers import SCHEMAS_DIR, load_backend_json, smoke_pipeline_id

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--backend-root",
        default="template",
        help="Path to the backend repo root (default: template/)",
    )
    parser.addoption(
        "--backend-cmd",
        default=None,
        help="Command to invoke the backend CLI (default: backend.json runner.command)",
    )
    parser.addoption(
        "--skip-runtime",
        action="store_true",
        default=False,
        help="Skip runtime tests (test_run_smoke.py, test_failure_mode.py)",
    )
    parser.addoption(
        "--smoke-config",
        default=None,
        help="Path to smoke config yml. Auto-detected for the template backend.",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def backend_root(request: pytest.FixtureRequest) -> Path:
    raw = request.config.getoption("--backend-root")
    p = Path(raw)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve()


@pytest.fixture(scope="session")
def backend_cmd(request: pytest.FixtureRequest, backend_root: Path) -> list[str]:
    raw = request.config.getoption("--backend-cmd")
    if raw:
        return shlex.split(raw)
    backend = load_backend_json(backend_root)
    command = backend.get("runner", {}).get("command")
    if not command:
        pytest.fail("backend.json missing runner.command; pass --backend-cmd")
    return [str(part) for part in command]


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    return SCHEMAS_DIR


@pytest.fixture(scope="session")
def skip_runtime(request: pytest.FixtureRequest) -> bool:
    return request.config.getoption("--skip-runtime")


@pytest.fixture(scope="session")
def backend_manifest(backend_root: Path) -> dict:
    return load_backend_json(backend_root)


@pytest.fixture(scope="session")
def smoke_pipeline(backend_manifest: dict) -> str:
    return smoke_pipeline_id(backend_manifest)


@pytest.fixture(scope="session")
def smoke_config_path(request: pytest.FixtureRequest, backend_root: Path) -> Path | None:
    raw = request.config.getoption("--smoke-config")
    if raw:
        return Path(raw).resolve()
    # Auto-detect: if backend is the template, use the bundled fixture
    fixture = REPO_ROOT / "conformance" / "fixtures" / "smoke_config_template.yml"
    if fixture.exists():
        return fixture
    return None


@pytest.fixture(scope="session")
def backend_docks(backend_manifest: dict) -> list:
    """Return the backend's declared docks[], or [] if the backend has none.

    Pipeline-only 1.0 backends have no ``docks`` key at all; this fixture
    makes every dock conformance test a no-op for them rather than an error.
    """
    return backend_manifest.get("docks", [])


@pytest.fixture(scope="session")
def qt_available() -> bool:
    """True when a Qt binding can be imported in this environment.

    Dock conformance tests that need a live widget/QApplication are
    guarded by this fixture and skip when no Qt binding is installed —
    the mandatory (static/AST) dock tests never depend on it.
    """
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import PyQt6  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import PyQt5  # noqa: F401
        return True
    except ImportError:
        pass
    return False


@pytest.fixture(scope="session")
def describe_output(backend_cmd: list[str], backend_root: Path) -> dict:
    """Run `describe --json` and return parsed JSON. Cached for the session."""
    result = subprocess.run(
        backend_cmd + ["describe", "--json"],
        capture_output=True,
        text=True,
        cwd=str(backend_root),
    )
    if result.returncode != 0:
        pytest.fail(
            f"`describe --json` exited {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"`describe` output is not valid JSON: {e}\nOutput: {result.stdout[:500]}")
