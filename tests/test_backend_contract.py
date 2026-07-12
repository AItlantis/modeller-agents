from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from modeller.backend import check_backend
from modeller.run import run_backend_pipeline


class BackendContractTests(unittest.TestCase):
    def test_backend_check_rejects_unexpected_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, backend_root = _write_backend_fixture(Path(tmp), contract_version="0.1")

            result = check_backend(root, "aimsun-psp")

            self.assertFalse(result.ok)
            self.assertIn("contract_version '0.1' does not match expected '1.0'", result.errors)

    def test_run_rejects_unexpected_contract_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, backend_root = _write_backend_fixture(Path(tmp), contract_version="0.1")
            config = backend_root / "config.yml"
            config.write_text("{}", encoding="utf-8")

            result = run_backend_pipeline(
                root=root,
                backend_id="aimsun-psp",
                pipeline_id="smoke",
                config=config,
                run_dir=backend_root / "run",
                backend_root=backend_root,
                timeout_s=10,
            )

            self.assertFalse(result.ok)
            self.assertIsNone(result.returncode)
            self.assertEqual(result.command, [])
            self.assertIn("contract_version '0.1' does not match expected '1.0'", result.errors)

    def test_run_rejects_result_identity_mismatch_after_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, backend_root = _write_backend_fixture(Path(tmp), contract_version="1.0")
            runner = backend_root / "runner.py"
            runner.write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "from pathlib import Path",
                        "args = sys.argv[1:]",
                        "run_dir = Path(args[args.index('--run-dir') + 1])",
                        "run_dir.mkdir(parents=True, exist_ok=True)",
                        "result = run_dir / 'result.json'",
                        "result.write_text(json.dumps({",
                        "  'contract_version': '1.0',",
                        "  'backend_id': 'aimsun-psp',",
                        "  'pipeline_id': 'wrong-pipeline',",
                        "  'pipeline_version': '0.1',",
                        "  'run_id': 'run-001',",
                        "  'status': 'success',",
                        "  'timestamps': {'started_at': '2026-07-10T00:00:00Z', 'completed_at': '2026-07-10T00:00:01Z'},",
                        "  'config_path': 'config.yml',",
                        "  'steps': [{'status': 'success', 'step_id': 1, 'step_name': 'smoke'}],",
                        "  'artifacts': [{'name': 'result', 'path': 'result.json'}]",
                        "}), encoding='utf-8')",
                        "print(str(result.resolve()))",
                    ]
                ),
                encoding="utf-8",
            )
            _write_backend_manifest(backend_root, contract_version="1.0", command=[sys.executable, "runner.py"])
            config = backend_root / "config.yml"
            config.write_text("{}", encoding="utf-8")

            result = run_backend_pipeline(
                root=root,
                backend_id="aimsun-psp",
                pipeline_id="smoke",
                config=config,
                run_dir=backend_root / "run",
                backend_root=backend_root,
                timeout_s=10,
            )

            self.assertFalse(result.ok)
            self.assertIsNotNone(result.validation)
            self.assertIn("pipeline_id 'wrong-pipeline' does not match expected 'smoke'", result.validation.errors)


def _write_backend_fixture(tmp: Path, contract_version: str) -> tuple[Path, Path]:
    root = tmp / "repo"
    backend_root = tmp / "backend"
    root.mkdir()
    backend_root.mkdir()
    (root / "backends.toml").write_text(
        "\n".join(
            [
                'schema_version = "0.1"',
                "",
                "[backend.aimsun-psp]",
                'status = "active"',
                "required = false",
                'backend_id = "aimsun-psp"',
                'contract_family = "modeller-pipelines"',
                'expected_contract = "1.0"',
                'local_root_key = "aimsun-psp"',
            ]
        ),
        encoding="utf-8",
    )
    (root / "backends.local.toml").write_text(
        "\n".join(
            [
                "[roots]",
                f'aimsun-psp = "{backend_root.as_posix()}"',
            ]
        ),
        encoding="utf-8",
    )
    _write_backend_manifest(
        backend_root,
        contract_version=contract_version,
        command=[sys.executable, "should_not_run.py"],
    )
    return root, backend_root


def _write_backend_manifest(backend_root: Path, contract_version: str, command: list[str]) -> None:
    (backend_root / "backend.json").write_text(
        json.dumps(
            {
                "backend_id": "aimsun-psp",
                "contract_version": contract_version,
                "runner": {
                    "command": command,
                    "interpreter": "system-python",
                    "platform": ["any"],
                },
                "pipelines": [{"id": "smoke", "definition": "smoke.pipeline.yml"}],
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
