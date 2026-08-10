# Template Pipeline Backend

This directory is a **complete, runnable, conforming** pipeline backend for the
`modeller-pipelines` contract v1.0.  Copy it to bootstrap a new pipeline repo;
the example pipeline (`trip_summary`) runs in under five seconds on any machine
using only Python stdlib.

---

## How to copy

```bash
cp -r template/ ../my-new-pipeline-backend
cd ../my-new-pipeline-backend
# 1. Edit backend.json — set a unique backend_id.
# 2. Rename or replace the trip_summary pipeline with your own.
# 3. Update contract.lock when you pin a release tag.
```

---

## How to run the example

```bash
# From the repo root (modeller-pipelines/):
python template/runner/minirunner.py describe

# Run trip_summary against the bundled sample data:
python template/runner/minirunner.py run trip_summary \
  --config template/data/smoke_config.yml \
  --run-dir /tmp/trip_summary_run
```

Exit 0 means success.  The final stdout line is the absolute path to
`result.json` in the run dir.

---

## How to add your first step

1. Create `pipelines/<pipeline_name>/steps/<N>_<verb>_<noun>.py` with a single
   `run(config, step_params, run_context) -> dict` function.
2. Add the step entry to `<pipeline_name>.pipeline.yml` under `steps:`.
3. If the step depends on an earlier step, add a `gates:` entry.
4. Run the smoke command above to verify end-to-end.

See `conventions/CONVENTIONS.md` for the full naming and import rules.

---

## How to register as a backend

Once your repo is ready:

1. Ensure `backend.json` has a unique `backend_id`.
2. Update `contract.lock` with the pinned tag:
   ```bash
   echo "modeller-pipelines contract-v1.0 <git-sha>" > contract.lock
   ```
3. Register the backend path in the modeller-agents config (see that repo's
   `BACKENDS.md`).
4. Run the conformance kit:
   ```bash
   pytest conformance/ --backend-root <your-repo> \
     --backend-cmd "python runner/minirunner.py"
   ```

---

## Directory layout

```
template/
├── README.md
├── backend.json
├── contract.lock
├── conventions/
│   ├── CONVENTIONS.md
│   ├── DEFINITION_OF_DONE.md
│   ├── LAYOUT.md
│   └── QUALITY_GATES.md
├── pipelines/
│   └── trip_summary/
│       ├── trip_summary.pipeline.yml
│       ├── trip_summary_config.py
│       └── steps/
│           ├── acquire_trips.py
│           ├── analyse_stats.py
│           ├── enrich_geo.py
│           └── export_report.py
├── shared/
│   └── result_builder.py
├── runner/
│   └── minirunner.py
├── data/
│   └── trips_sample.csv
└── tests/
    └── test_self_conformance.py
```
