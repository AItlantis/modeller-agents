# modeller-agents — Integration Plan

> **Current implementation note (2026-07-09):** the repository scaffold now follows
> `modelling-knowledge/decisions/0001-local-agents-central-skills.md`: central reusable
> skills, routing, lifecycle gates, reference packs, and backend registry live here;
> repository-local agents remain in their owning repositories. Sections below that discuss
> portable personas or specialist agents are retained as planning history and must be read
> through that accepted boundary.

> **Status:** draft 2026-07-08, revised 2026-07-08 to the org-level orchestration decisions.
> Target shape: a **BMAD-METHOD-style agentic framework** for transport modelling, built with
> the plugin/agent/skill conventions proven in Testudo and consuming `modeller-memory` as its
> memory subsystem.
> Analysis sources: `AItlantis/Testudo` (plugin/agents/skills), BMAD-METHOD (framework shape).
>
> **Locked decisions (see `AItlantis/docs/ORCHESTRATION.md`):** this repo is the **composition
> root**; it consumes `modeller-memory` and the existing `aimsun-psp`/`aimsun_psf` pipelines as
> **read-only git subtrees** under `vendor/` (no `.gitmodules`); orchestration is **Python**
> (`modeller` CLI, uv/hatchling/Typer); every cross-system interaction passes one of three
> contracts (pipeline `result.json`, memory MCP+skills, `vendors.toml`).

---
> consider integrating https://github.com/luongnv89/asm
> consider integrating https://github.com/AFK-surf/open-agent
> consider reuse @~\software\sources\aimsun\aimsun-agents
## 1. What this repo is

A **method framework**, not just a Claude Code plugin. Like BMAD-METHOD it ships:
- **Agents** (specialist roles/personas) with routing metadata,
- **Tasks / workflows** (repeatable gated procedures),
- **Templates** (document/artifact scaffolds),
- **Checklists** (quality gates),
- a **module registry** + an **installer** that vendors the framework into a target project,
- **bundles** for packaging.

…but it reuses Testudo's *concrete, working* conventions for the agent/skill layer (so it also
runs natively as a Claude Code plugin), and it wires `modeller-memory` in as its recon/recall
backend.

**Two proven patterns being fused:**
- **Testudo** gives the *runtime* wiring: `.claude/plugins/<name>/` (agents + skills), a local
  marketplace, `settings.json` discovery, the generic-skill + `references/<domain>.md` split,
  and the orchestrator→specialist routing model.
- **BMAD** gives the *framework* shape: module registry (`bmad-modules.yaml`-style),
  tasks/templates/checklists as first-class citizens, and `npx <tool> install` vendoring.

---

## 2. Proposed repo layout

```
modeller-agents/                     # ★ HOST repo — the composition root
├── README.md
├── LICENSE
├── pyproject.toml                   # Python package `modeller` (CLI + orchestration); uv + hatchling
├── vendors.toml                     # subtree manifest — replaces .gitmodules (see §4 + ORCHESTRATION.md §5)
├── backends.toml                    # runtime backend registry (committed) — which backends exist + expected contract
├── backends.local.toml              # per-machine backend roots (gitignored)
├── modeller-modules.yaml            # module registry (BMAD-style): declares bundles & deps
├── docs/
│   ├── INTEGRATION_PLAN.md          # this file
│   ├── method/                      # narrative of the method (phases, roles, artifacts)
│   └── skills/modeller/             # read-only MIRROR of the plugin (Testudo's drift-gate pattern)
├── src/
│   └── modeller/                    # Python orchestration package (replaces BMAD's npx installer)
│       ├── cli.py                   # `modeller` entrypoint (Typer)
│       ├── install.py  doctor.py  sync.py  bundle.py  run.py   # run.py resolves backends.toml
│       └── plugin_gen/              # personas -> Claude plugin renderer (jinja2)
├── method/                          # THE method (was `core/`; renamed to avoid clash w/ Testudo core/)
│   ├── agents/                      # agent PERSONAS (portable YAML, tool-agnostic) — SOURCE of truth
│   ├── tasks/                       # repeatable gated procedures
│   ├── templates/                   # artifact scaffolds (briefs, PRDs, calibration reports…)
│   ├── checklists/                  # quality gates / definition-of-done
│   └── workflows/                   # multi-agent sequences (wave-based, à la Testudo §4)
├── .claude/
│   ├── settings.json                # discovery wiring (see §4) + memory hooks
│   └── plugins/
│       └── modeller/                # GENERATED from method/agents (committed + drift-gated)
│           ├── .claude-plugin/
│           │   ├── plugin.json       # name/version/description/author/keywords
│           │   └── marketplace.json  # local marketplace, plugins[0].source: "./"
│           ├── README.md             # component index (agents + skills tables)
│           ├── agents/*.md           # frontmatter: name / description(+<example>) / model / color
│           └── skills/<name>/SKILL.md# frontmatter: name / description / metadata{version,author}
│                                     #   + optional references/<domain>.md and scripts/
├── tools/
│   └── skills/                      # asm (Agent Skill Manager) gate — bundle↔mirror drift, port from Testudo
├── bundles/                         # web-bundles equivalent (v2 — cut from lean v1)
└── vendor/                          # everything here is ANOTHER repo's history (subtree, read-only)
    ├── modeller-memory/             #   subtree <- AItlantis/modeller-memory  (memory subsystem)
    └── modeller-pipelines/          #   subtree <- AItlantis/modeller-pipelines (the CONTRACT + conformance kit)
```

**What is vendored vs referenced at runtime (revised 2026-07-08):** we vendor the **contract**
(`modeller-pipelines`: small, stable, needed offline for recon + graph indexing) and reference the
**backend** at runtime (`aimsun-psp`: large, licensed, platform-bound, fast-moving — registered in
`backends.toml`, never a subtree). `aimsun-psp` is **no longer** under `vendor/`.

**One invariant:** everything under `vendor/` is someone else's history; everything outside is
yours. There is no `external/` and no `tools/memory/` — vendored code lives under `vendor/`,
its wiring lives in `src/modeller/`.

Note the **two representations of agents** (intentional, from the fusion):
- `method/agents/` = framework-level personas (portable YAML; source of truth).
- `.claude/plugins/modeller/agents/` = the Claude-Code-native rendering, **generated and
  committed** by `modeller bundle --plugin`. Never hand-edit the generated `.md`; the asm drift
  gate (§5) fails the build if they diverge from `method/agents/`.

---

## 3. Agent & skill conventions (adopt Testudo's verbatim)

**Agent frontmatter** (`.claude/plugins/modeller/agents/<name>.md`):
```yaml
---
name: <slug>                 # bare generic name, matches file
description: |               # prose "use this agent for…" + <example>…<commentary>…</commentary></example>
                             # blocks — these DRIVE routing; invest here
model: <opus|sonnet|haiku>   # opus=orchestrator, sonnet=specialists, haiku=pure-exec/recon
color: <name>                # optional UI color
---
```
- **No `tools:` key.** Tools are inherited; the body tells the agent which
  `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` to open. (Testudo convention.)
- Model tiering: one `opus` orchestrator; `sonnet` specialists; `haiku` for pure execution and
  read-only recon sub-agents. (Matches the user's saved preference: haiku recon, sonnet plan/impl.)

**Skill frontmatter** (`.claude/plugins/modeller/skills/<name>/SKILL.md`):
```yaml
---
name: <skill>
description: <what + explicit "Use when…" trigger; name sibling skills it composes/differs-from>
metadata:
  version: 1.0.0             # semver; asm eval treats a MISSING version as an ERROR
  author: AItlantis (Jean-Noel Diltoer)
---
```
- Generic method in `SKILL.md`; all domain-specifics in `references/<domain>.md` with headings
  mirroring the steps 1:1. Executable helpers in `scripts/` (`.py`/`.mjs`/`.sh`), referenced by
  repo-absolute path. (Testudo's reusability split — the reason its skills work outside Testudo.)

**Candidate starter agents** (transport-modelling specialists, orchestrator-routed):
`orchestrator` (opus) · `model-builder` · `calibration` · `scenario-analyst` · `data-import`
· `qa` (report-only) · `publisher` (haiku). Refine against the actual modelling method in
`docs/method/`.

**Candidate starter skills:** `orchestrate`, `workflow` (gated multi-file changes),
`memory-recon` + `memory-maintain` (thin wrappers over `modeller-memory`'s skills),
`review`, `debug`, plus domain skills (`build-model`, `run-calibration`, `compare-scenarios`).

---

## 4. Discovery / wiring (Testudo's exact mechanism)

`.claude/settings.json` — the two keys that make the plugin discoverable + active:
```jsonc
{
  "extraKnownMarketplaces": {
    "modeller-marketplace": {
      "source": { "source": "directory", "path": ".claude/plugins/modeller" }
    }
  },
  "enabledPlugins": { "modeller@modeller-marketplace": true },
  "hooks": {
    "SessionStart": [ /* modeller-memory guardrails (ponytail) — guarded by `command -v node` */ ],
    "SubagentStart": [ /* same */ ]
  }
}
```
- Agents/skills are **auto-discovered by folder convention** (`agents/*.md`, `skills/*/SKILL.md`).
  Do NOT enumerate them in the manifest — Testudo doesn't, and its README count already drifted
  from the on-disk count. Prefer a generator/gate over a hand-kept index.
- Marketplace `name`, the `@`-suffix in `enabledPlugins`, and `plugin.json.name` must all agree.
- MCP (memory) is wired separately via `.mcp.json` (ship `.mcp.json.example`), provided by the
  embedded `modeller-memory` subsystem.

---

## 5. Skill governance (port Testudo's asm gate)

Adopt `asm` (Agent Skill Manager) via `tools/skills/`:
- `check_skills.sh` — repo-scoped inventory + audit + **bundle↔mirror drift** (`.claude/plugins/modeller/skills` vs `docs/skills/modeller/skills`). Exit `0` clean · `2` drift · `3` security · `77` asm-absent.
- Run at the end of the `workflow` skill and **before pushing to the default branch**.
This keeps the docs mirror honest and each `SKILL.md` best-practice-scored (`metadata.version` required).

---

## 6. How the four repos connect

```
modeller-agents  ──subtree──▶  vendor/modeller-memory      (pinned in vendors.toml, `modeller sync`)
     │           ──subtree──▶  vendor/modeller-pipelines   (the CONTRACT + conformance kit)
     │
     │ memory-recon / memory-maintain skills  ──▶  modeller-memory's generic skills
     │ agents call them during RECON/DOCUMENT       (code graph + companion recall + guardrails)
     │
     │ `modeller run <pipeline>` resolves backends.toml + backend.json
     │        ──subprocess──▶  aimsun-psp (RUNTIME BACKEND, not vendored) -> result.json
     │        host re-validates result.json against vendor/modeller-pipelines schema
     ▼
  .mcp.json  ◀── generated from modeller-memory's mcp.json.example by `modeller install`
```
The framework never re-implements memory or pipelines. It **vendors the contract**
(`modeller-pipelines`) and **references the backend** (`aimsun-psp`) at runtime, talking to
everything only through named contracts (memory MCP+skills; pipeline `result.json` validated against
the vendored schema; `vendors.toml`; `backends.toml`). It supplies only the per-host
`references/modeller.md` (project ids, live-source subtrees for archive-pollution scoping —
`vendor/modeller-memory` + `vendor/modeller-pipelines` — and domain taxonomy bindings).
See `AItlantis/docs/ORCHESTRATION.md` §4 + §6.4 for the full run-flow and backend-registration contract.

---

## 7. Build sequence

- **A0 — Method first.** Write `docs/method/` (phases, roles, artifacts) — the framework exists to encode a modelling method; agents/skills are its rendering. (BMAD is method-led.)
- **A1 — Plugin skeleton + Python CLI.** `.claude/plugins/modeller/` with `plugin.json` + `marketplace.json` + `settings.json` wiring; `pyproject.toml` + `src/modeller/` with `install`/`doctor`/`sync`; one `orchestrator` agent + `orchestrate`/`workflow` skills. Verify Claude Code discovers it.
- **A2 — Specialists + domain skills.** Add modelling specialist agents and their skills using the generic-method + `references/modeller.md` split.
- **A3 — Subtree modeller-memory.** `modeller sync` it under `vendor/`; add the thin `memory-recon`/`memory-maintain` wrapper skills + `.mcp.json` generation; wire guardrail hooks.
- **A3b — Subtree modeller-pipelines (contract) + backend registry + run seam.** `modeller sync` **`modeller-pipelines`** under `vendor/` (the contract + conformance kit, *not* aimsun-psp); add `backends.toml` / `backends.local.toml`; wire `modeller run`/`backend`/`doctor` to resolve a backend via its `backend.json` and validate `result.json` against the vendored schema; route pipeline-domain tasks to `psp-orchestrate` via the registered backend's `backend.json.plugin` pointer (do not duplicate it). *(Registering aimsun-psp is blocked on O1 — confirm its remote; the contract subtree + wiring are not.)*
- **A4 — Framework layer.** `method/` (tasks/templates/checklists/workflows) + `modeller-modules.yaml` registry. `method/` holds **zero** executable pipeline knowledge (§ decision below).
- **A5 — asm gate + dogfood.** `tools/skills/` drift gate (bundle↔mirror + generated-plugin drift + `vendors.toml`↔split-SHA); dogfood by `modeller install` into a scratch target. `bundles/` + web packaging deferred to v2.

---

## 8. Resolved decisions & remaining open items

**Resolved (see `ORCHESTRATION.md` §9):**
- **Host language → Python.** `modeller` CLI via uv + hatchling + Typer; `uvx modeller` replaces
  `npx`. modeller-memory's `embed`/`doctor` become an importable `modeller_memory` package; the
  ponytail reuse-ladder is ported to a small Python hook (drops the last Node dependency).
- **Persona authoring → generate + commit + drift-gate.** `method/agents/*.yaml` is the source;
  `modeller bundle --plugin` renders the committed `.claude/plugins/modeller/agents/*.md`.
- **Plugin coexistence.** The `modeller` plugin lives alongside the `aimsun-psp-orchestrator`
  plugin — two plugins, one marketplace registry; `modeller` **routes** to `psp-orchestrate` via the
  registered backend's `backend.json.plugin` pointer.
- **Method vs pipelines (anti-duplication).** `method/` contains no executable pipeline knowledge:
  tasks/templates/checklists define gates, artifacts, decision procedures and quality criteria; the
  "how a step works" lives only in the backend, reached via the `modeller run` subprocess seam. The
  *shape* of a pipeline (schema, step interface, result.json) is owned by `modeller-pipelines/contracts/`.
- **Pipeline topology (revised 2026-07-08).** `modeller-agents` vendors the **contract**
  (`modeller-pipelines`) as a subtree and targets it; `aimsun-psp` is a **runtime backend** registered
  in `backends.toml`, **not** vendored. Supersedes the earlier "vendor/aimsun-psp subtree" plan.

**Still open:**
- **O1 — aimsun-psp remote/home.** No `aimsun-psp` dir exists under `AItlantis/` yet; the concrete
  pipeline reference currently lives in Testudo (`vwe.pipeline.yml`, `actions/`, `pipeline/`).
  Confirm the authoritative remote before **registering** it in `backends.toml` (A3b). No longer
  blocks vendoring — the `modeller-pipelines` contract subtree proceeds independently.
- **Plugin name:** `modeller` assumed; confirm vs `aitlantis`. Drives marketplace + enabledPlugins keys.
- **Scope of v1:** lean v1 = Python CLI (`install`/`doctor`/`sync`) + both subtrees + plugin skeleton
  (orchestrator + `workflow` + memory skills) + `result.json` contract + gates. Defer bundles/web,
  subtree-push automation, federated multi-repo index, mempalace activation (wired but flag-off).
