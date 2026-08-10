# modeller-pipelines — Integration Plan

> **Status:** draft 2026-07-08. Target shape: the **reference scaffold + contract surface** that
> defines what a "pipeline repo" *is* in the modeller ecosystem. `modeller-agents` targets it as a
> contract; concrete backends (first: the existing `aimsun-psp`) conform to it without depending on it.
> Analysis sources: `aimsun-psp-orchestrator` plugin conventions (psp-* skills), Testudo's
> `vwe.pipeline.yml` + `actions/` + `pipeline/`, and the org orchestration doc.
> Advisory: shaped by a Fable advisory (see §9). Companion doc: `AItlantis/docs/ORCHESTRATION.md`.

---

## 1. What this repo is (and is NOT)

`modeller-pipelines` is **the specification of what a pipeline repo *is*** — a versioned contract
surface (data + normative prose) plus **one copyable, runnable template repo** that proves the
contract is implementable.

It is authoritative over the **seam** between agents and pipelines, never over any backend's
**internals**.

**Locked decisions (this document's inputs):**

1. **Nature = reference scaffold / canonical template**, with a runnable example pipeline. It is
   explicitly **NOT a shared executable framework** that other repos import.
2. **Contents =** (a) schemas & contracts, (b) conventions & structure docs, (c) a runnable example
   pipeline. **Deliberately excluded:** no shared base `Step`/`Action`/`Runner` library.
3. **Topology = "agents target the contract, aimsun-psp is a backend".** `modeller-agents` vendors
   this repo (subtree) as its contract; `aimsun-psp` is a runtime backend, **registered not vendored**.
4. **Testudo is out of scope** — intent documented only, no refactor implied.

**The one discipline everything flows from:** backends conform to `contracts/`, **not** to
`template/`. The template is an *illustration*; the contract is the *law*.

**What is deliberately absent** (per decision 2): no `src/`, no pip package, no importable base
classes, no plugin/skill code. The `psp-create-*` skills stay in `aimsun-psp-orchestrator`; this
repo carries the *conventions those skills encode*, as prose, so a future backend without that
plugin can still conform.

---

## 2. Repo layout

The scaffold and the example are the **same artifact** — the template *is* a complete, runnable,
conforming pipeline repo. "Start a new pipeline repo" = copy `template/`, rename, and delete the
example steps last (after your first real step passes conformance). We do not ship an empty
scaffold and a filled example separately; the empty one always rots.

```
modeller-pipelines/
├── README.md                        # what this is / is NOT (not a framework; nothing imports it)
├── CHANGELOG.md
├── CONTRACT_VERSIONS.md             # contract_version <-> git tag table + support window (N, N-1)
│
├── contracts/                       # ★ THE VERSIONED SURFACE — pure data + normative prose
│   ├── VERSION                      # e.g. "1.0" — the single pipeline_contract_version
│   ├── schemas/                     # JSON Schema draft 2020-12, engine-agnostic
│   │   ├── pipeline.schema.json     # *.pipeline.yml shape (generalized from vwe.pipeline.yml)
│   │   ├── result.schema.json       # run-level result.json
│   │   ├── step-result.schema.json  # per-step result envelope (success/failure/skipped)
│   │   ├── backend.schema.json      # backend.json manifest (registration — §5)
│   │   └── run-config.schema.json   # config envelope (inputs binding + params overrides)
│   ├── PIPELINE_DEFINITION.md       # normative: ids, gates, cache_inputs, inputs/outputs decl
│   ├── STEP_INTERFACE.md            # normative SPEC (no code): run(config, params, ctx) -> step-result
│   ├── CLI_SEAM.md                  # the `run` / `describe` subprocess contract (§3.3)
│   └── RESULT_CONTRACT.md           # result.json semantics: statuses, relative paths, error shape
│
├── conformance/                     # ★ RUNNABLE conformance kit — pytest, black-box, backend-agnostic
│   ├── README.md                    # how any backend runs this in its own CI
│   ├── conftest.py                  # --backend-root / --backend-cmd / --skip-runtime options
│   ├── test_static.py               # backend.json + every declared pipeline.yml validate vs schemas
│   ├── test_describe.py             # `describe` output == backend.json == on-disk definitions
│   ├── test_run_smoke.py            # runs the backend's declared smoke pipeline end-to-end
│   ├── test_failure_mode.py         # bad config -> exit!=0 AND a valid result.json status=failed
│   └── fixtures/                    # golden result.json, malformed configs, minimal CSVs
│
├── template/                        # ★ THE COPYABLE PIPELINE REPO (itself a conforming backend)
│   ├── README.md                    # "copy me" instructions + annotated layout
│   ├── backend.json                 # template registered as backend_id "template"
│   ├── contract.lock                # pinned modeller-pipelines tag this repo conforms to
│   ├── conventions/
│   │   ├── LAYOUT.md                # normative directory layout for a pipeline repo
│   │   ├── CONVENTIONS.md           # thin step scripts; reuse-first / second-use test; shared/ rules
│   │   ├── DEFINITION_OF_DONE.md    # DoD (implemented/tests/smoke/docs/changelog/limitations)
│   │   └── QUALITY_GATES.md         # gated phase workflow: brief->recon->plan->execute->deploy->document
│   ├── pipelines/
│   │   └── trip_summary/            # the runnable example — stdlib-only, no Aimsun (§4)
│   │       ├── trip_summary.pipeline.yml
│   │       ├── trip_summary_config.py       # flat dataclass, from_yaml(), mirrors inputs: decl
│   │       └── steps/
│   │           ├── acquire_trips.py
│   │           ├── analyse_stats.py         # required step, cache_inputs demo
│   │           ├── enrich_geo.py            # OPTIONAL + gated step — exercises skip semantics
│   │           └── export_report.py         # writes manifest + report under run dir
│   ├── shared/                      # backend-LOCAL shared lib — starts near-empty, grows by second-use
│   │   └── result_builder.py        # ~60 lines: build step-result / result.json dicts vs schema
│   ├── runner/
│   │   └── minirunner.py            # ~150-200 stdlib lines: load yml, topo-sort gates, import steps,
│   │                                #   collect results, write result.json, expose run + describe CLI.
│   │                                #   COPY-DON'T-IMPORT (§9 D2)
│   ├── data/trips_sample.csv        # tiny fixture (~200 rows)
│   └── tests/test_self_conformance.py  # runs ../conformance against THIS template
│
└── docs/
    ├── INTEGRATION_PLAN.md          # this file
    ├── HOW_TO_CONFORM.md            # the aimsun-psp path: conforming an EXISTING repo (§6)
    ├── ADR/
    │   ├── ADR-0001-scaffold-not-framework.md
    │   └── ADR-0002-contract-versioning.md
    └── TESTUDO_INTENT.md            # 1 page, intent-only (out of scope, per decision 4)
```

**The keystone CI job of this repo:** run `conformance/` against `template/`. Self-conformance
proves the kit and the template agree and makes the template the kit's own fixture. If the contract
changes and the template doesn't, CI is red — the primary **anti-rot** mechanism.

---

## 3. The contract surface (what is standardized, versioned, checked)

Four artifacts, **one** version number (`contract_version`, starts `"1.0"`, from `contracts/VERSION`,
released as git tag `contract-v1.0`).

### 3.1 Pipeline manifest (`pipeline.schema.json`)

Generalized from `vwe.pipeline.yml` (already ~90% right). Normative core: `pipeline_id` (slug),
`pipeline_name`, `version` (semver), `description`, `domain`; `steps[]` with
`id`/`name`/`title`/`action_module`/`required`/`cache_inputs[]`/`params{}`; `gates[]`
(`{step_id, requires:[ids]}`, DAG validated acyclic); `inputs{required[],optional[]}`;
`outputs[]`. Two normative rules that fix real Testudo scars:

- **No step id may be reserved or interpreted by the runner outside the yml** (bans the "hardcoded
  step id in the presenter" collision that forced a workaround id in VWE).
- **Every declared step must be invocable** — no "declared but not wired" steps without an explicit
  `enabled: false`.

### 3.2 Step/action interface (`STEP_INTERFACE.md` + `step-result.schema.json`) — a SPEC, not a base class

A step module MUST expose `run(config, step_params, run_context) -> dict`, returning a dict that
validates against `step-result.schema.json`:

```json
{ "status": "success|failed|skipped",
  "step_id": 4, "step_name": "import", "message": "…",
  "duration_s": 12.3, "cached": false,
  "artifacts": [{"name": "sections", "path": "geometry/sections.geojson"}],
  "metrics": {}, "error": {"type": "…", "message": "…", "traceback_path": "logs/step4.err"} }
```

Normative behaviours (lifted from proven Testudo/psp invariants): heavy imports inside `run()`;
writes **only** under the run dir; all paths relative to run root; optional steps skip gracefully
(`status: skipped` + reason); **failures return a failure result — they never raise across the
seam**; no silent swallowing. How a backend *dispatches* to `run()` (presenter, work_unit, aconsole)
is explicitly **out of contract**.

### 3.3 The CLI seam (`CLI_SEAM.md`) — what `modeller run` talks to

A conforming backend exposes two subcommands, invocable as a subprocess on whatever interpreter it
needs (Aimsun-embedded Python included — preserves the interpreter separation from ORCHESTRATION §6.1):

```
<backend-cmd> describe [--json]                      # -> backend.json content on stdout
<backend-cmd> run <pipeline_id> --config <cfg.yml> --run-dir <dir>
```

Guarantees: exit `0` iff `result.json.status == "success"`; **`result.json` is written to
`<run-dir>/result.json` in every outcome, including crash-adjacent failure** (the runner's last
act); the **final stdout line is the absolute path to `result.json`**. That last-line rule is the
entire machine-readable stdout contract — everything else on stdout/stderr is human logs.

### 3.4 Run result (`result.schema.json`)

Run-level envelope carrying `contract_version`, `backend_id`, `pipeline_id`, `pipeline_version`,
`run_id`, `status` (`success|partial|failed`), timestamps, `config_path`, `steps[]` (§3.2 objects),
`artifacts[]`, `metrics{}`, `logs[]`, `error{}`. `partial` = all **required** steps succeeded, ≥1
optional step failed/skipped-on-error (matches VWE "decoration best-effort" semantics). Agents and
gates consume **only** this file plus declared artifacts.

### 3.5 Versioning & conformance

- **One number for the whole surface.** Minor = strictly additive (new optional fields); major =
  anything breaking. Per-schema versions are sprawl — refused.
- **Backends declare it twice:** statically in `backend.json`, dynamically in every `result.json`;
  `modeller doctor` cross-checks.
- **Conformance = the pytest kit, run in the backend's CI** against a pinned tag. Static tests
  (schema validation, describe consistency) are mandatory everywhere; the runtime smoke runs where
  the backend's smoke pipeline can run (§6).
- **Support window: N and N-1.** The kit refuses older versions loudly.
- **Cultural rule (ADR-0002):** the contract earns changes **from backends, not from the template**
  — a field enters the schema when a real backend needs it (second-use test applied to the contract).

---

## 4. The example pipeline — `trip_summary`

**What it is:** a CSV of synthetic trips (`vehicle_id, t, x, y, speed`) → 4 steps → a run dir with
`manifest.json`, a `report.html` skeleton, and `result.json`. A genuine miniature of VWE's
acquire → analyse → export shape, but **stdlib-only** (`csv`, `json`, `math`, `argparse`,
`dataclasses`) — no pandas, no Aimsun; runs in <5s on any CI.

**What it must exercise (one pipeline, every contract feature):** required steps; one **optional
gated step** (`enrich_geo`, skips gracefully → `partial`-capable); `cache_inputs` (re-run with the
same input hash ⇒ `cached: true`); a config dataclass mirroring the `inputs:` declaration; the
failure mode (`fixtures/bad_config.yml` ⇒ exit 1 + a valid failed `result.json`); relative artifact
paths; the `describe` / last-stdout-line seam.

**How it runs without a shared framework:** `runner/minirunner.py`, ~150–200 stdlib lines living
*inside the template*. When you copy the template you **own** that file; `aimsun-psp` does **not**
adopt it (it already has a presenter). Guardrails so it never becomes the excluded framework: a
hard 200-line CI-enforced budget; no extension points/hooks/plugins; a "COPY THIS FILE — never
import it across repos" header; and a **black-box conformance kit** (subprocess + file assertions
only, never imports the runner) so runner semantics can't leak into the contract.

**Double duty as conformance fixture:** this repo's CI runs
`pytest conformance --backend-root template --backend-cmd "python template/runner/minirunner.py"`.

---

## 5. Runtime backend registration (how modeller-agents finds & invokes a backend)

Two artifacts: a **manifest owned by the backend**, a **registry owned by the host**.

### 5.1 `backend.json` — at each backend repo root, owned by the backend

```json
{ "backend_id": "aimsun-psp",
  "contract_version": "1.0",
  "runner": { "command": ["python", "-m", "aimsun_psp.cli"],
              "interpreter": "aimsun-embedded", "platform": ["windows"] },
  "pipelines": [ {"id": "vwe", "definition": "pipelines/vwe/vwe.pipeline.yml"} ],
  "smoke_pipeline": "seam_smoke",
  "plugin": ".claude/plugins/aimsun-psp-orchestrator" }
```

Validated by `backend.schema.json`; also emitted live by `describe` (conformance asserts
static == dynamic). The `plugin` field is how routing to `psp-orchestrate` survives de-vendoring:
`modeller` learns where the plugin lives from the registered backend clone, not from a subtree.

### 5.2 `backends.toml` (+ `backends.local.toml`) — in `modeller-agents`

The registry lives in **`modeller-agents`** (host runtime config, like `vendors.toml` is host
vendoring config): a committed `backends.toml` (which backends exist, expected contract, required?)
plus a gitignored `backends.local.toml` (where each backend is on this machine). Not in
modeller-pipelines (a template has no runtime); not global (defer multi-host to v2).

### 5.3 The `modeller run` seam, resolved

`modeller run vwe --config c.yml` → merge `backends.toml` + `backends.local.toml` → read each
root's `backend.json` → find backend(s) declaring pipeline `vwe` (ambiguity ⇒ demand `--backend`) →
check contract compatibility (N/N-1) → subprocess `runner.command + ["run","vwe","--config",…,
"--run-dir",…]` → parse last stdout line → **re-validate** `result.json` against the vendored schema
(trust but verify) → return the path. New v1 host subcommands: `modeller backend list|add|doctor`.

---

## 6. How aimsun-psp conforms without depending

Line: **shared as data = anything read or validated; duplicated as code = anything imported at
runtime.** Three mechanisms, most-binding first:

1. **`contract.lock` + CI-fetched schemas.** `aimsun-psp` commits a one-line `contract.lock`
   (`modeller-pipelines contract-v1.0 <sha>`); its CI checks out `modeller-pipelines` at that pin
   and runs the conformance kit. **Nothing from modeller-pipelines enters aimsun-psp's import graph
   or repo history** — no subtree, no pip dep, no copied schema as source-of-truth.
2. **`backend.json` at repo root** (§5.1) — written once, validated by conformance, consumed by the host.
3. **Convention alignment (soft).** aimsun-psp is already the *origin* of most conventions
   (`*.pipeline.yml` + `*_config.py` + presenter + reuse-first + gated phases). Conforming is mostly:
   (a) expose the §3.3 CLI seam (a thin `run`/`describe` wrapper over the existing presenter/runners);
   (b) emit contract-shaped `result.json` (its richer internal result can be projected to the
   contract file); (c) keep its result-building code **its own** private module, imported from
   nowhere. Duplicating ~100 lines of result-envelope code per backend is the accepted cost of "no
   shared framework"; schema validation in CI keeps the duplicates honest.

**Drift hazard to fix on day one of contract-v1.0:** the `psp-pipeline-schema` skill is currently
the de-facto schema authority. Repoint it — it keeps encoding *how to author* a pipeline, but its
validation target becomes `contracts/schemas/pipeline.schema.json` at the pinned tag. Two
authorities for one schema is how this design dies quietly.

**The Aimsun-runtime problem:** the runtime smoke needs a pipeline that runs in CI, and VWE needs
Aimsun. Rule: **every backend declares one `smoke_pipeline` that runs without licensed/heavyweight
deps** (for aimsun-psp, an Aimsun-free pipeline — even an adapted `trip_summary` — which is a
*better* seam probe than any Aimsun pipeline). Full Aimsun pipelines stay runtime-verified on the
Windows host via the existing `psp-deploy` smoke discipline, outside the conformance kit.

---

## 7. Build sequence

- **P0 — Contracts.** Draft `contracts/` v1.0 from `vwe.pipeline.yml` + the psp conventions (banning
  the known scars). Write the four normative `.md` specs.
- **P1 — Template + example.** `template/` with `minirunner.py` + `trip_summary` + `conventions/`;
  get self-conformance green (`conformance/` vs `template/`).
- **P2 — Tag + integrate.** Tag `contract-v1.0`; subtree into `modeller-agents` (revised A3); wire
  `backends.toml` + `modeller run`/`backend`/`doctor`.
- **P3 — aimsun-psp conformance.** `backend.json` + `contract.lock` + CLI-seam wrapper + Aimsun-free
  smoke + run the kit in aimsun-psp CI. *(Registration gated on O1 — confirm the aimsun-psp remote —
  but contract + template work is NOT blocked by it.)*

---

## 8. Open decisions

- **O1 (shared with the org doc):** confirm the authoritative `aimsun-psp` remote/home. Now blocks
  only **registration** (`backends.toml` / P3), no longer any vendoring — contract work proceeds.
- **Report skeleton format** for the example (`report.html` vs `report.md`) — cosmetic; pick at P1.
- **`domain` field** stays a free string in v1; a controlled vocabulary is deferred.

---

## 9. Hardest decisions — resolved (Fable advisory)

| # | Decision | Call |
|---|---|---|
| **D1** | Scaffold rot: template vs a real backend diverging | **Allowed and expected.** `contracts/` is normative + CI-enforced on every backend; `template/` is illustrative + enforced only against `contracts/` (self-conformance). A backend that passes conformance while looking nothing like the template is fine. **Never add layout-lint to the conformance kit** — that turns the template into a framework by other means. |
| **D2** | The minirunner becoming an embryonic shared framework | **Keep it, fenced:** 200-line CI budget, zero extension points, "copy don't import" + no packaging metadata, black-box conformance. Copy-drift between repos is the system working. Factoring the copies into a package is a *new* explicit decision, not a refactor — today's answer is no. |
| **D3** | Where the backend registry lives | **`modeller-agents`** — committed `backends.toml` (expectations) + gitignored `backends.local.toml` (machine paths). Not modeller-pipelines (no runtime), not global (premature). |
| **D4** | Schemas → aimsun-psp: fetch vs copy vs package | **CI-fetch at pinned tag + `contract.lock`.** No pip package, no committed schema copies in v1. A contracts wheel is the slippery slope back to the excluded shared library. |
| **D5** | Versioning granularity | **One `contract_version` for the whole surface**; additive-minor / breaking-major; N & N-1; stamped in `backend.json` *and* every `result.json`; kit versions via tags; `doctor` warns on mixed majors. |

**Anti-patterns guarded against:** framework-by-stealth (grep CI check for cross-repo imports);
dual schema authority (repoint `psp-pipeline-schema` at contract-v1.0); canonizing VWE quirks (ban
runner-reserved ids; keep `legacy:` non-normative); conformance theater (smoke asserts artifact
existence + relative paths + failure mode); contract creep into backend internals (contract covers
only what crosses the seam). **Lean v1 cuts:** one example pipeline; `backend.json` = pipeline list +
smoke + plugin only; no contracts package; runtime smoke required only for the smoke pipeline; no
UI/dock template; `TESTUDO_INTENT.md` is one page; defer multi-host registry and machine-readable
conventions lint.

> **Superseded in contract-v1.1:** the "no UI/dock template" cut above was a deliberate v1 lean cut,
> not a permanent exclusion. As of contract-v1.1, `modeller-pipelines` adds a second first-class
> artefact type — the **QtDock** — as an explicit, additive-minor reversal of that cut: a versioned
> dock contract (`contracts/DOCK_CONTRACT.md` + `contracts/DOCK_INTERFACE.md` +
> `contracts/schemas/dock.schema.json`), a copyable `template/docks/` (launcher + demo dock + a
> copy-don't-import `lib/`), and Qt-free black-box conformance tests. See
> `docs/ADR/ADR-0003-dock-artefact-seam.md` for the full rationale. Every other v1 lean cut listed
> above is unaffected.

---

## 10. How this connects to the other repos

- **`modeller-agents`** vendors this repo as a **subtree** (`vendor/modeller-pipelines`, pinned in
  `vendors.toml`) — it needs `contracts/` + the conformance kit offline and graph-indexed. It targets
  the contract, resolves backends via `backends.toml`, and validates every `result.json` against the
  vendored schema.
- **`aimsun-psp`** is a **runtime backend** — registered via `backends.toml` → `backend.json`,
  invoked by subprocess, conforming via `contract.lock` + the conformance kit. Never vendored.
- **`modeller-memory`** indexes this repo's subtree as a live-source subtree (recon scope).
- **`Testudo`** is out of scope; `docs/TESTUDO_INTENT.md` records only that its `vwe` pipeline is the
  lineage ancestor of this contract and that a future epic *might* register it — no refactor implied.

See `AItlantis/docs/ORCHESTRATION.md` for the full four-repo picture and run-flow contract.
