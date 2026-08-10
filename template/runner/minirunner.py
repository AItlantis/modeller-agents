# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# Line budget: 200 lines (CI-enforced). Zero extension points.
"""minirunner — stdlib-only pipeline runner for the template backend.

Usage:
    python runner/minirunner.py describe [--json]
    python runner/minirunner.py run <pipeline_id> \
        --config <cfg.yml> --run-dir <dir>

The final stdout line of `run` is the absolute path to result.json.
Exit 0 iff result.json status == "success".
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from the template root (pipelines.*, shared.*)
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

BACKEND_JSON = ROOT / "backend.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: str) -> dict:
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        result: dict = {}
        with open(path) as f:
            for line in f:
                line = line.rstrip()
                if not line or line.lstrip().startswith("#"):
                    continue
                if ":" in line and not line.startswith(" "):
                    k, _, v = line.partition(":")
                    result[k.strip()] = v.strip() or {}
        return result


def _load_pipeline_def(backend: dict, pipeline_id: str) -> dict:
    for p in backend.get("pipelines", []):
        if p["id"] == pipeline_id:
            yml_path = ROOT / p["definition"]
            return _load_yaml(str(yml_path))
    raise ValueError(f"Pipeline '{pipeline_id}' not declared in backend.json")


def _topo_sort(steps: list, gates: list) -> list:
    deps: dict = {s["id"]: set() for s in steps}
    for g in gates:
        deps[g["step_id"]] = set(g.get("requires", []))
    ordered, visited = [], set()

    def visit(sid: int) -> None:
        if sid in visited:
            return
        visited.add(sid)
        for dep in deps.get(sid, set()):
            visit(dep)
        ordered.append(sid)

    for s in steps:
        visit(s["id"])
    id_to_step = {s["id"]: s for s in steps}
    return [id_to_step[sid] for sid in ordered if sid in id_to_step]


def _write_result(run_dir: Path, result: dict) -> Path:
    out = run_dir / "result.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    return out


def cmd_describe(args: argparse.Namespace) -> None:
    with open(BACKEND_JSON) as f:
        data = json.load(f)
    print(json.dumps(data, indent=2))


def cmd_run(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())[:8]
    started = _now()
    config = _load_yaml(args.config)
    with open(BACKEND_JSON) as f:
        backend = json.load(f)

    result_base = {
        "contract_version": backend["contract_version"],
        "backend_id": "template",
        "pipeline_id": args.pipeline_id,
        "pipeline_version": "0.1.0",
        "run_id": run_id,
        "timestamps": {"started_at": started, "completed_at": started},
        "config_path": str(Path(args.config).absolute()),
        "steps": [],
        "artifacts": [],
        "metrics": {},
        "logs": [],
        "error": None,
    }

    try:
        pipeline_def = _load_pipeline_def(backend, args.pipeline_id)
        steps = _topo_sort(
            pipeline_def.get("steps", []),
            pipeline_def.get("gates", []),
        )
    except Exception as exc:
        result_base["status"] = "failed"
        result_base["timestamps"]["completed_at"] = _now()
        result_base["error"] = {"type": type(exc).__name__, "message": str(exc)}
        rp = _write_result(run_dir, result_base)
        print(str(rp.absolute()))
        sys.exit(1)

    run_context = {
        "run_dir": str(run_dir),
        "run_id": run_id,
        "pipeline_id": args.pipeline_id,
    }
    step_results, failed_required = [], False

    for step in steps:
        module = importlib.import_module(step["action_module"])
        t0 = time.monotonic()
        try:
            sr = module.run(config, step.get("params", {}), run_context)
        except Exception as exc:
            sr = {
                "status": "failed", "step_id": step["id"],
                "step_name": step["name"],
                "message": f"Unhandled exception: {exc}",
                "duration_s": round(time.monotonic() - t0, 3),
                "cached": False, "artifacts": [], "metrics": {},
                "error": {"type": type(exc).__name__, "message": str(exc), "traceback_path": None},
            }
        step_results.append(sr)
        if sr["status"] == "failed" and step.get("required", True):
            failed_required = True
            break

    statuses = {r["status"] for r in step_results}
    if failed_required:
        run_status = "failed"
    elif "skipped" in statuses or any(r["status"] == "failed" for r in step_results):
        run_status = "partial"
    else:
        run_status = "success"

    result_base["status"] = run_status
    result_base["timestamps"]["completed_at"] = _now()
    result_base["steps"] = step_results
    result_base["artifacts"] = [a for sr in step_results for a in sr.get("artifacts", [])]

    rp = _write_result(run_dir, result_base)
    print(str(rp.absolute()))
    sys.exit(0 if run_status == "success" else 1)


def main() -> None:
    p = argparse.ArgumentParser(description="modeller-pipelines template runner")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("describe").add_argument("--json", action="store_true")
    rp = sub.add_parser("run")
    rp.add_argument("pipeline_id")
    rp.add_argument("--config", required=True)
    rp.add_argument("--run-dir", required=True)
    args = p.parse_args()
    if args.command == "describe":
        cmd_describe(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
