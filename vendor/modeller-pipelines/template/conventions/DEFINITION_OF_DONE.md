# Definition of Done

A pipeline step / pipeline / backend is **done** when all of the following are checked:

## Step level

- [ ] **Implemented** — `run(config, step_params, run_context) -> dict` exists and returns a valid step-result dict
- [ ] **Tests** — at least one unit test for the step's core logic (Aimsun/Qt mocked or absent)
- [ ] **Error handled** — failure path returns `{"status": "failed", ...}`, does not raise
- [ ] **Paths relative** — all artifact paths are relative to run dir

## Pipeline level

- [ ] **Config round-trip** — `Config.from_yaml(Config(...).to_yaml())` round-trips losslessly
- [ ] **Smoke** — `minirunner.py run <pipeline_id> --config fixtures/smoke_config.yml --run-dir /tmp/smoke` exits 0
- [ ] **Schema valid** — `<name>.pipeline.yml` validates against `pipeline.schema.json`
- [ ] **Docs** — each step's purpose documented in its `title` field in the yml

## Backend level

- [ ] **`backend.json`** — present at repo root, validates against `backend.schema.json`
- [ ] **`contract.lock`** — present and pinned to a released `modeller-pipelines` tag
- [ ] **CLI seam** — `describe` and `run` subcommands work per `CLI_SEAM.md`
- [ ] **Conformance kit** — `pytest conformance --backend-root . --backend-cmd "<cmd>"` passes (static tier at minimum)
- [ ] **Changelog** — entry added for any user-visible change
- [ ] **Limitations** — known edge cases or deferred scope documented in README
