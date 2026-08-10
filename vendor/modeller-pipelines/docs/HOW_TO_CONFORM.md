# How to Conform an Existing Backend

This guide is for conforming an existing pipeline backend repo to the `modeller-pipelines` contract — the `aimsun-psp` path. You do **not** adopt this repo's code. You prove your CLI seam and output shape match the contract.

See `docs/BACKEND_ARCHETYPES.md` (non-normative) for a survey of observed backend shapes — in
particular, whether your pipeline needs a fixed model-path config field at all is archetype-specific,
not universal.

## What "conforming" means

You write a thin adapter. Your existing presenter/runners keep working unchanged. The adapter:
1. Exposes `describe` and `run` subcommands (the CLI seam).
2. Emits a conformant `result.json` (project your internal result to the contract shape).
3. Declares the contract version in `backend.json`.
4. Pins the contract tag in `contract.lock`.

## Step 1: Add `backend.json` at your repo root

```json
{
  "backend_id": "aimsun-psp",
  "contract_version": "1.2",
  "runner": {
    "command": ["python", "-m", "aimsun_psp.cli"],
    "interpreter": "aimsun-embedded",
    "platform": ["windows"]
  },
  "pipelines": [
    {"id": "vwe", "definition": "pipelines/vwe/vwe.pipeline.yml"}
  ],
  "smoke_pipeline": "seam_smoke",
  "plugin": ".claude/plugins/aimsun-psp-orchestrator"
}
```

Validate it: `python -c "import json; json.load(open('backend.json'))"`.

## Step 2: Add `contract.lock`

```
echo "modeller-pipelines contract-v1.2 <sha>" > contract.lock
```

Replace `<sha>` with the git SHA of the `contract-v1.2` tag in this repo.

## Step 3: Expose the CLI seam

Add a thin `cli.py` (or `__main__.py`) to your package:

```python
# aimsun_psp/cli.py
import argparse, json, sys

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("describe").add_argument("--json", action="store_true")
    run_p = sub.add_parser("run")
    run_p.add_argument("pipeline_id")
    run_p.add_argument("--config", required=True)
    run_p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    if args.cmd == "describe":
        with open("backend.json") as f:
            print(json.dumps(json.load(f)))
    elif args.cmd == "run":
        from aimsun_psp.runner_adapter import run_pipeline
        result_path = run_pipeline(args.pipeline_id, args.config, args.run_dir)
        print(result_path)   # <- MUST be the final stdout line
        sys.exit(0 if _result_ok(result_path) else 1)

if __name__ == "__main__":
    main()
```

The `runner_adapter` wraps your existing presenter/runners and writes `result.json`.

## Step 4: Emit conformant `result.json`

Your richer internal result can be projected to the contract shape. Write `result.json` to `<run-dir>/result.json`. The file MUST be written even on failure. See `contracts/RESULT_CONTRACT.md` for the required fields.

## Step 5: Add an Aimsun-free smoke pipeline

Declare a pipeline that runs in CI without a licensed Aimsun instance. Even an adapted `trip_summary` (copy the template's example) works. This is a better seam probe than any Aimsun pipeline — it tests the CLI contract in CI without Aimsun.

Add it to `backend.json` as `"smoke_pipeline": "seam_smoke"` and create `pipelines/seam_smoke/seam_smoke.pipeline.yml`.

## Step 6: Run the conformance kit in your CI

```bash
# Check out modeller-pipelines at your pinned contract tag
git clone --depth 1 --branch contract-v1.2 <modeller-pipelines-url> /tmp/modeller-pipelines

# Run static tests (no Aimsun needed)
pytest /tmp/modeller-pipelines/conformance \
  --backend-root . \
  --backend-cmd "python -m aimsun_psp.cli" \
  --skip-runtime

# Run smoke test (needs the smoke pipeline)
pytest /tmp/modeller-pipelines/conformance \
  --backend-root . \
  --backend-cmd "python -m aimsun_psp.cli"
```

## Conforming a dock

If your backend also ships one or more interactive Aimsun QtDocks (contract
v1.1+, unaffected by the v1.2 revision), conforming them is separate from —
and does not block — conforming your pipelines above.

### Step 1: Point `entry_module` at your existing launcher

You do not need to adopt `template/docks/`. If you already have a working
dock launcher (e.g. `aimsun_psp`'s `run_dsm_dock.py`-style module exposing
`run(model, _argv=None) -> bool`), declare it as-is:

```json
{
  "backend_id": "aimsun-psp",
  "contract_version": "1.1",
  "runner": { "...": "..." },
  "pipelines": [ "..." ],
  "smoke_pipeline": "seam_smoke",
  "docks": [
    {
      "dock_id": "dsm",
      "title": "Dock Script Manager",
      "dock_key": "aimsun_psp.dsm.v3",
      "entry_module": "domains/_70_Scripting/docks/dsm/run_dsm_dock.py",
      "doc": "domains/_70_Scripting/docks/dsm/README.md",
      "area": "right",
      "debug_env": "DSM_DOCK_DEBUG",
      "reload_prefixes": ["aimsun_psp.domains._70_Scripting.docks.dsm"]
    }
  ],
  "smoke_dock": "dsm"
}
```

Validate the whole file against `contracts/schemas/backend.schema.json`
(the `docks[]` entries validate against the same shape published standalone
as `contracts/schemas/dock.schema.json`).

### Step 2: Confirm the contract your launcher already satisfies

Read `contracts/DOCK_CONTRACT.md` and `contracts/DOCK_INTERFACE.md`. Most of
an already-hardened dock (module-scope `run(model, _argv=None) -> bool`,
lazy Qt imports, a single-instance registry, reload-tolerant reuse by class
qualified name, a `reset_state()` method, an Info affordance) is very likely
already true — these normative documents were distilled from exactly that
kind of dock. The gaps to check for:

- Is every Qt/widget import inside `run()` — none at module scope?
- Does reuse detection match by class qualified name, not bare `isinstance`?
- Is any dev-reload purge-based and scoped to the dock's own package (never a
  `shared`/framework prefix)?

### Step 3: Run dock conformance in CI with Qt absent

```bash
pytest /tmp/modeller-pipelines/conformance \
  --backend-root . \
  --backend-cmd "python -m aimsun_psp.cli" \
  --skip-runtime
```

The static/AST dock tests (`test_dock_static.py`, `test_dock_source.py`,
`test_dock_schema_consistency.py`, `test_dock_describe.py`) run and must pass
with **no Qt binding installed** — they parse and validate, they never
import the dock module or construct a widget. The one host-only tier
(`test_dock_import.py`) is gated behind a `qt_available` fixture and skips
cleanly in a Qt-free CI runner; run it manually on a machine with Qt (or
inside Aimsun) when you want the deeper live-widget check.

A backend with no docks at all is unaffected: the `backend_docks` fixture
reads an absent `docks` key as `[]`, so every dock conformance test is a
no-op for a pipeline-only backend.

## Open question O1: registration in `modeller-agents`

Registration (`backends.toml` in `modeller-agents`) is separate from conformance. Conformance can be completed and the conformance kit can pass **before** registration. O1 (confirming the authoritative `aimsun-psp` remote) blocks only the `backends.toml` entry — not any of the steps above.
