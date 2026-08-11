from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from modeller.pipeline_runtime import PipelineRuntimeError, execute_accepted_pipeline_dispatch


ROOT = Path(__file__).resolve().parents[1]


class PipelineRuntimeTests(unittest.TestCase):
    def test_accepted_dispatch_runs_explicit_backend_and_emits_deterministic_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            backend_root = workspace / "backend"
            run_dir = workspace / "run"
            config = workspace / "config.yml"
            backend_root.mkdir()
            config.write_text("pipeline: smoke\n", encoding="utf-8")
            (workspace / "backends.toml").write_text(
                "\n".join([
                    'schema_version = "0.1"',
                    "",
                    "[backend.aimsun-psp]",
                    'status = "active"',
                    'backend_id = "aimsun-psp"',
                    'expected_contract = "1.2"',
                ]), encoding="utf-8",
            )
            runner = backend_root / "runner.py"
            runner.write_text(
                "import json, sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "run_dir = Path(args[args.index('--run-dir') + 1])\n"
                "run_dir.mkdir(parents=True, exist_ok=True)\n"
                "(run_dir / 'map.png').write_bytes(b'fixture')\n"
                "result = run_dir / 'result.json'\n"
                "result.write_text(json.dumps({\n"
                "'contract_version':'1.2','backend_id':'aimsun-psp',\n"
                "'pipeline_id':'smoke','pipeline_version':'1.0.0','run_id':'run-001',\n"
                "'status':'success','timestamps':{'started_at':'2026-08-11T00:00:00Z','completed_at':'2026-08-11T00:00:01Z'},\n"
                "'config_path':'config.yml','steps':[{'status':'success','step_id':1,'step_name':'smoke','artifacts':[]}],\n"
                "'artifacts':[{'name':'map','path':'map.png','type':'image/png'}]}, sort_keys=True), encoding='utf-8')\n"
                "print(str(result))\n", encoding="utf-8",
            )
            (backend_root / "backend.json").write_text(json.dumps({
                "backend_id": "aimsun-psp", "contract_version": "1.2",
                "runner": {"command": [sys.executable, "runner.py"], "interpreter": "system-python", "platform": ["any"]},
                "pipelines": [{"id": "smoke", "definition": "smoke.pipeline.yml"}],
            }), encoding="utf-8")
            response = {
                "accepted": True,
                "dispatch": {
                    "backend_id": "aimsun-psp", "mission_id": "mission-001", "task_id": "task-001",
                    "pipeline_execution_id": "execution-001", "attempt_id": "attempt-001",
                    "pipeline_id": "smoke", "pipeline_version": "1.0.0", "correlation_id": "corr-001",
                },
            }

            first = execute_accepted_pipeline_dispatch(
                response, root=ROOT, backend_root=backend_root, config=config, run_dir=run_dir,
            )
            second = execute_accepted_pipeline_dispatch(
                response, root=ROOT, backend_root=backend_root, config=config, run_dir=run_dir,
            )

            self.assertEqual(first.events, second.events)
            self.assertEqual(first.receipt, second.receipt)
            self.assertEqual(first.receipt["mission_id"], "mission-001")
            self.assertEqual(first.receipt["task_id"], "task-001")
            self.assertEqual(first.receipt["outputs"][0]["path"], "map.png")
            self.assertEqual(first.receipt["evidence"], ["result.json", "map.png"])

    def test_runtime_correlation_projects_evidence_to_testudo_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            backend_root = workspace / "backend"
            run_dir = workspace / "run"
            config = workspace / "config.yml"
            backend_root.mkdir()
            config.write_text("pipeline: smoke\n", encoding="utf-8")
            (workspace / "backends.toml").write_text(
                '[backend.aimsun-psp]\nstatus="active"\nbackend_id="aimsun-psp"\nexpected_contract="1.2"\n',
                encoding="utf-8",
            )
            runner = backend_root / "runner.py"
            runner.write_text(
                "import json,sys\nfrom pathlib import Path\n"
                "d=Path(sys.argv[sys.argv.index('--run-dir')+1]); d.mkdir(parents=True,exist_ok=True)\n"
                "(d/'map.png').write_bytes(b'x')\n"
                "(d/'result.json').write_text(json.dumps({'contract_version':'1.2','backend_id':'aimsun-psp','pipeline_id':'smoke','pipeline_version':'1.0.0','run_id':'r','status':'success','timestamps':{'started_at':'2026-08-11T00:00:00Z','completed_at':'2026-08-11T00:00:01Z'},'config_path':'config.yml','steps':[{'status':'success','step_id':1,'step_name':'smoke','artifacts':[]}],'artifacts':[{'name':'map','path':'map.png','type':'image/png'}]}))\n"
                "print(str(d/'result.json'))\n", encoding="utf-8",
            )
            (backend_root / "backend.json").write_text(json.dumps({
                "backend_id": "aimsun-psp", "contract_version": "1.2",
                "runner": {"command": [sys.executable, "runner.py"], "interpreter": "system-python", "platform": ["any"]},
                "pipelines": [{"id": "smoke", "definition": "smoke.pipeline.yml"}],
            }), encoding="utf-8")
            response = {"accepted": True, "dispatch": {
                "backend_id": "aimsun-psp", "mission_id": "m", "task_id": "t",
                "pipeline_execution_id": "e", "attempt_id": "a", "pipeline_id": "smoke",
                "pipeline_version": "1.0.0", "runtime_correlation": {
                    "schema_version": "1.0", "mission_id": "m", "task_id": "t",
                    "workflow_run_id": "w", "attempt_id": "a", "pipeline_execution_id": "e",
                    "pipeline_version_id": "pv", "project_id": "p", "active_context_revision_id": "c",
                    "capability_grant_id": "g", "principal": {"id": "u"},
                    "idempotency_key": "i", "sequence": 0,
                },
            }}
            execution = execute_accepted_pipeline_dispatch(response, root=ROOT, backend_root=backend_root, config=config, run_dir=run_dir)
            self.assertEqual(len(execution.testudo_events), 2)
            self.assertEqual(execution.testudo_events[0]["correlation"]["workflow_run_id"], "w")
            self.assertEqual(execution.testudo_receipt["sequence"], 3)

    def test_unaccepted_or_non_aimsun_dispatch_fails_closed(self) -> None:
        with self.assertRaises(PipelineRuntimeError):
            execute_accepted_pipeline_dispatch(
                {"accepted": False}, root=ROOT, backend_root=ROOT, config=ROOT / "x", run_dir=ROOT / "run",
            )
        with self.assertRaisesRegex(PipelineRuntimeError, "aimsun-psp"):
            execute_accepted_pipeline_dispatch(
                {"accepted": True, "dispatch": {
                    "backend_id": "other", "mission_id": "m", "task_id": "t", "pipeline_execution_id": "e",
                    "pipeline_id": "p",
                }}, root=ROOT, backend_root=ROOT, config=ROOT / "x", run_dir=ROOT / "run",
            )


if __name__ == "__main__":
    unittest.main()
