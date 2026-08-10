# Conformance Kit

A black-box pytest suite that proves a backend conforms to the `modeller-pipelines` contract. "Black-box" means: subprocess calls and file assertions only — the kit never imports the backend's code.

## Two tiers

| Tier | Tests | When to run |
|---|---|---|
| Static | `test_static.py`, `test_describe.py` | Always — no backend runtime needed |
| Runtime | `test_run_smoke.py`, `test_failure_mode.py` | When the backend can actually run a pipeline |

## CLI options

| Option | Default | Description |
|---|---|---|
| `--backend-root` | `template` | Path to the backend repo root |
| `--backend-cmd` | `python template/runner/minirunner.py` | Command to invoke the backend CLI |
| `--skip-runtime` | off | Skip runtime tests (static tests still run) |
| `--smoke-config` | auto | Path to smoke config yml (auto-detected for template backend) |

## Example invocations

```bash
# Self-conformance: run against the template (from repo root)
pytest conformance --backend-root template --backend-cmd "python template/runner/minirunner.py"

# Static tests only (safe for any backend, no pipeline execution)
pytest conformance --backend-root /path/to/my-backend \
    --backend-cmd "python -m my_backend.cli" --skip-runtime

# Full conformance for aimsun-psp (static + runtime smoke)
pytest conformance --backend-root /path/to/aimsun-psp \
    --backend-cmd "python -m aimsun_psp.cli" \
    --smoke-config conformance/fixtures/smoke_config_template.yml
```

## Adding this to your backend's CI

```yaml
# In your backend's CI (GitHub Actions example):
- name: Fetch modeller-pipelines at pinned contract
  run: |
    SHA=$(cat contract.lock | awk '{print $3}')
    git clone --depth 1 https://github.com/your-org/modeller-pipelines /tmp/mp
- name: Run conformance (static)
  run: pytest /tmp/mp/conformance --backend-root . --backend-cmd "python -m my_backend.cli" --skip-runtime
```
