# Normative Directory Layout

Every conforming pipeline backend repository MUST follow this layout.
Deviations require an ADR entry in `conventions/` explaining the trade-off.

```
<backend-repo>/
├── README.md                    # "Copy me" instructions and local docs
├── backend.json                 # backend manifest (owned by this repo)
├── contract.lock                # pinned modeller-pipelines tag
├── conventions/                 # normative docs (copy from template)
│   ├── CONVENTIONS.md
│   ├── DEFINITION_OF_DONE.md
│   ├── LAYOUT.md
│   └── QUALITY_GATES.md
├── pipelines/
│   └── <pipeline_name>/
│       ├── <name>.pipeline.yml  # pipeline definition
│       ├── <name>_config.py     # flat dataclass, from_yaml(), mirrors inputs: decl
│       └── steps/
│           ├── __init__.py      # empty
│           └── <N>_<verb>_<noun>.py   # one file per step
├── shared/                      # backend-LOCAL shared lib; grows by second-use test only
│   └── result_builder.py        # the only pre-seeded helper
├── runner/
│   └── minirunner.py            # COPY THIS FILE — never import it across repos
├── data/                        # fixtures and sample data for smoke tests
│   └── trips_sample.csv         # (or equivalent for your domain)
├── docks/                       # OPTIONAL — only if the backend registers backend.json:docks[]
│   ├── run_<dock_id>_dock.py    # launcher: run(model, _argv=None) -> bool; COPY, never import
│   ├── <dock_id>/
│   │   ├── <dock_id>_widget.py  # dock widget class + setup_ui/reset_state/on_close
│   │   ├── info_dialog.py       # (or shared under lib/) renders the dock's README
│   │   └── README.md            # the dock's Info documentation
│   └── lib/                     # COPY THIS DIRECTORY — never import it across repos
│       ├── qt_compat.py
│       ├── base_dock.py
│       ├── integration.py
│       ├── persistence.py
│       ├── browse_bar.py
│       └── status_bar.py
└── tests/
    └── test_self_conformance.py # conformance + unit tests
```

## Key invariants

- `backend.json` lives at the **repo root**, not nested under a subdirectory.
- `runner/minirunner.py` is a **copy**, not an import.  Each backend repo owns
  its own copy.  See `CONVENTIONS.md §4` for the rationale.
- `shared/` is backend-LOCAL.  Nothing outside this repo may import from it.
- Step modules live exactly one directory deep under `steps/`.  Nesting further
  is not supported by the dynamic import in `minirunner.py`.
- `data/` holds **fixtures only** — never production data or large binaries.
- `docks/` is **optional**. A pipeline-only backend omits it entirely and
  `backend.json` simply has no `docks` key. See `DOCK_CONVENTIONS.md` for the
  dock-specific rules (copy-don't-import `lib/`, `dock_key` versioning, the
  Info doc requirement, DEBUG-purge, and the `qt_compat` rule).
