# modeller-agents

`modeller-agents` is the central routing, reusable-skills, and typed-packs framework for the
modelling ecosystem. It is BMAD-style and follows Testudo plugin conventions: generic skills stay
methods, and all repository- or domain-specific facts live in data packs the router selects.

It is one of three siblings and owns a deliberately narrow slice:

- **`modeller-agents` (this repo)** — pack format and routing, skill selection, knowledge-pack
  generation/validation, route provenance, and the context budget.
- **`modelling-knowledge`** — the knowledge authority (note IDs, metadata, sensitivity, eligibility,
  vault-scope decisions). This repo never owns that.
- **`modeller-memory`** — the memory subsystem and `vault_doctor` tooling. This repo never owns that.

## Purpose

The router resolves a task along **two axes**:

```text
axis 1 (WHERE)  intent.target_repository -> bundles/<target>.bundle.json -> reference packs (kind="repo")
axis 2 (WHAT)   intent.domains[]         -> reference-packs/domains/_registry.toml -> knowledge packs (kind="knowledge")
```

Axis 1 selects the repository bundle and its repo fact packs; the chosen skill must be declared by
the bundle and authorized by at least one selected pack. Axis 2 is additive: when an envelope carries
`intent.domains[]` (or a bundle declares `defaultKnowledge[]`), the router resolves domains through the
registry to knowledge packs.

**The rule that keeps the boundary clean: knowledge packs are references, never copies.** A knowledge
pack lists vault note IDs, a routing `purpose`, and an `authority_context`; it must not embed note
bodies, thresholds, decision text, or acceptance status. `modelling-knowledge` remains the sole
authority for the content behind those IDs, and `modeller-memory` remains the authority for memory and
`vault_doctor`. Copied-knowledge fields are rejected by validation.

The boundary is defined by `modelling-knowledge/decisions/0001-local-agents-central-skills.md`: local
agents stay in the repositories they operate on; reusable skills live here.

### What lives where

```text
src/modeller/                Python CLI (modeller.cli) and structural checks
.claude/plugins/modeller/    Claude/Codex plugin surface for the central skills
method/                      method tasks, templates, workflows, and checklists (incl. source-boundary)
reference-packs/             repo fact packs (kind="repo") + domains/ knowledge packs (kind="knowledge")
bundles/                     repository bundles mapping skills to reference packs
examples/                    sample context envelopes
docs/                        architecture, workflow, readiness, and command references
schemas/                     RunManifest and ContextReceipt JSON Schemas
tools/ · vendor/             tooling and the planned vendor subtree registry surface
tests/                       pytest suite (83 tests)
```

## Installation & usage

Requires Python 3.10+. Zero runtime dependencies. Built with hatchling; the console script `modeller`
maps to `modeller.cli:main`.

Run straight from a source checkout without installing:

```powershell
$env:PYTHONPATH='AItlantis\modeller-agents\src'
python -m modeller.cli doctor --root AItlantis\modeller-agents
```

Or install (editable for development, or a wheel for distribution):

```powershell
pip install -e AItlantis\modeller-agents      # editable
pip install AItlantis\modeller-agents          # or build/install a wheel
modeller doctor --root AItlantis\modeller-agents
```

Wheel builds force-include the plugin surface and runtime assets under `modeller/runtime`, so an
installed `modeller` can install from packaged assets when `--root` is not a source checkout. Target
repositories keep their copied runtime snapshot under `.modeller/runtime/`, not at repository root.

### CLI commands

`--root` selects the repository to inspect and defaults to `.`.

```powershell
# Structural health check. Advisory locally; exits non-zero on errors.
python -m modeller.cli doctor --root . --json          # machine-readable payload
python -m modeller.cli doctor --root . --strict        # CI/release gate (see Features)

# Route a context envelope to a skill + bundle (+ knowledge packs when domains are present).
python -m modeller.cli route --root . --envelope examples/testudo-context-envelope.json
python -m modeller.cli route --root . --envelope <env.json> --run-id <run>   # supply workflow run

# Deterministic artifact-gated workflow.
python -m modeller.cli workflow --root . init   --run-id <run>
python -m modeller.cli workflow --root . status --run-id <run>
python -m modeller.cli workflow --root . check  --run-id <run>
python -m modeller.cli workflow --root . manifest --run-id <run> [--envelope <env.json>]
python -m modeller.cli workflow --root . close    --run-id <run> [--envelope <env.json>]

# Strict-readiness remediation plan (no changes applied).
python -m modeller.cli readiness --root . --json
```

Other surfaces: `skills`, `backends [--check <id>]`, `sync [<vendor>]`, `install <target>
[--apply] [--include-runtime-assets]`, `validate [--backend-json|--result-json]`, `plan`, `run`,
and the `workflow advance` / `complete-artifact` gates. See [docs/COMMANDS.md](docs/COMMANDS.md).

The canonical CLI remains `python -m modeller.cli` / `modeller`. The legacy
`python -m modeller_agents.cli` import path is only a compatibility alias.

### How the assets fit together

`route` reads a **bundle** to pick reference packs and confirm the skill; the selected **reference
packs** authorize the skill; **method** checklists and templates (for example the source-boundary
checklist) drive the workflow. Installing with `--include-runtime-assets` copies `method/`,
`reference-packs/`, `bundles/`, `schemas/`, `backends.toml`, and `vendors.toml` under
`.modeller/runtime/` in a target and records source provenance in `.modeller/install-manifest.json`;
without it, only the plugin wiring is copied.

### Knowledge-pack validation and vault parity

Knowledge-pack validation runs during both `doctor` and `route`. When a domain pack exists, the CLI
invokes `modelling-knowledge`'s `vault_doctor export-index` / `export-domains` (through the sibling or
vendored `modeller-memory`) and checks **digest parity**: a pack's `source_domain_notes_digest` and
`source_domains_digest` must match the current vault export, every referenced note ID must exist in the
live index, and superseded/deprecated/non-exposable/over-sensitivity notes are rejected. An `active`
pack requires current exports; if the vault is unreachable, validation says so rather than passing
blind. This is how the pack layer stays a live reference to the authority instead of a stale copy.

## Features

- **Deterministic workflow gate.** Routing to `orchestrate` (or any envelope with
  `execution_policy.requires_workflow: true`) requires a named, initialized workflow run whose current
  artifact gate passes; otherwise `route` returns `ok: false`. The `requirements` and
  `orchestration-design` steps require their artifacts' `## Evidence` to cite subagent/agent
  provenance. See [docs/workflows/DETERMINISTIC_WORKFLOW.md](docs/workflows/DETERMINISTIC_WORKFLOW.md).
- **Run traceability surface.** `workflow manifest` emits a `RunManifest` referencing workflow state,
  artifacts, gates, and optional `ContextReceipt` data by path and SHA-256 digest. `workflow close`
  writes `.modeller/runs/<run_id>/run-manifest.json` and fails unless the workflow is complete, the
  full artifact gate passes, the implementation evidence gate passes, and all workflow artifact
  references include digests.
- **Strict readiness (`doctor --strict`).** The release/CI gate promotes planned vendors, unpinned
  vendors, draft reference packs, and sibling-schema fallback to hard failures, and requires a real
  backend smoke through the contract seam. It emits stable `readiness_blockers[]` codes for CI.
  **Strict readiness is currently blocked** — the four bundle reference packs are still `draft`, the
  `modeller-memory` / `modeller-pipelines` vendors are planned/unpinned, and schemas resolve via the
  sibling fallback. See [docs/readiness/STRICT_READINESS.md](docs/readiness/STRICT_READINESS.md) for
  each blocker and its exact remediation.
- **Source-boundary checklist.** `method/checklists/source-boundary.md` enforces that a write, backend
  call, or knowledge promotion targets the repository that owns the outcome (surfaced by the
  `source-boundary-check` skill). See [docs/architecture/BOUNDARIES.md](docs/architecture/BOUNDARIES.md).
- **Typed-packs knowledge axis.** Reference packs carry `kind = "repo"` or `kind = "knowledge"`.
  Knowledge packs (`reference-packs/domains/<domain>.toml`) point into the vault by note ID only. See
  [docs/architecture/typed-packs-knowledge-axis.md](docs/architecture/typed-packs-knowledge-axis.md).
- **Domain affinity `none | explicit | routed` (D4).** A skill's `domain_affinity` declares which
  knowledge it may consume. Wildcards (`*` / `all` / `any`) are rejected; `explicit` allows only listed
  domains; `routed` performs no inference and consumes only what routing already authorized.
- **Context-budget contract (D3).** Selection is bounded and audited: `max_knowledge_packs = 3`,
  `max_required_notes = 8`, `max_optional_notes_loaded = 4`, `max_full_notes = 2`, with bundle
  `defaultKnowledge[]` capped at 2. Request and bundle domains form an **ordered union with per-domain
  `source` provenance** (`request` / `bundle-default`), so audit can distinguish asked-for from
  silently-added.
- **Vault-export digest parity for active packs (D5).** As described under *usage* above — active packs
  are validated against live `vault_doctor` exports on every `doctor`/`route`.
- **Accessibility knowledge-pack pilot — currently NOT routing (by design).**
  `reference-packs/domains/accessibility.toml` is the first `kind = "knowledge"` pilot pack. Because the
  vault deactivated domain routability (F-A), the domain is not active/routable in the current vault
  export, so the pilot does **not** route today. `modeller.cli doctor` reports the disabled axis as a
  normal development warning; explicit routes for `intent.domains=["accessibility"]` fail with a
  disabled-domain result and select zero knowledge packs. The pack is structurally ready and will route
  once the vault restores routability.

## Future features

Planned, tracked in [docs/architecture/typed-packs-open-decisions.md](docs/architecture/typed-packs-open-decisions.md)
and the cross-repo coordination decision `modelling-knowledge/decisions/0010`:

- **Re-activate knowledge-pack routing** once the vault restores domain routability — gated on
  `0010` general acceptance and the DR-1 cure. This lifts the F-A deactivation and lets the
  accessibility pilot (and future domains) route live.
- **General-scope N-1 / N-2 enforcement** — extend the shared eligibility conformance and
  `authority_context` currency validators beyond the single VA5 pilot to all active packs.
- **Domain inference (VA6)** — let orchestration infer candidate domains from task context and
  re-invoke routing with explicit domains; the inference must be auditable and never silent inside
  `route.py`.
- **Defaults + routed affinity (VA7)** — ship the ordered-union defaults and the bounded `routed`
  selection policy as the general path, once their conditions hold at scale.
- **Promote typed packs from draft to active architecture (VA8)** — move the knowledge axis out of
  pilot/draft status and make the reference packs and vendors release-ready (which also clears the
  strict-readiness blockers above).

---

For the global architecture and deterministic-workflow overview, see
[docs/architecture/ARCHITECTURE_AND_WORKFLOW.md](docs/architecture/ARCHITECTURE_AND_WORKFLOW.md).
