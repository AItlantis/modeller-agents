# Process references (mirrored from `knowledge-vault-orchestrator`)

These are the **corpus-agnostic process references** for the knowledge-acquisition
lifecycle, mirrored here so the memory-side `document-knowledge-acquisition` skill
carries the same gate/wave/board context it produces evidence for.

> **Source of truth:** the `knowledge-vault-orchestrator` skill
> (`.skills/knowledge-vault-orchestrator/skills/knowledge-vault-orchestrator/references/`).
> These are mirrored copies — do not edit here; change them at the source and re-copy.
> Ownership: the orchestration/skill is agents-side; `modeller-memory` owns only the
> extraction/validation tooling. This mirror is for reader/agent convenience, not a fork.

| File | What it covers |
|---|---|
| `vault-creation.md` | Stage A / Wave C — scaffolding a governed vault from templates. |
| `template-catalog.md` | The per-type note + root-doc templates and the candidate→accepted front-matter contract. |
| `wave-definitions.md` | Per-wave objective/inputs/outputs/gate (WC, W0–W7). |
| `gate-criteria.md` | Gate pass conditions (GC, G0–G7) and the conditional-pass pattern. |
| `board-pack-template.md` | Wave 3 human-decision board pack shape. |
| `subagent-brief-templates.md` | Lane brief templates for dispatched subagents. |
| `delta-rebaseline.md` | Handling a revised source mid-acquisition. |
| `obsidian-vault-linking.md` | Post-wave wikilinking / map-of-content regeneration. |
| `progress-artifact.md` | Progress visualisation of vault progression. |

The Aimsun-specific model-probe references (`model-probe.md`, `ka-model-probe.agent.md`,
`model-screenshots-investigation.md`, `expect/`) are intentionally **not** mirrored here —
they belong with the orchestrator/`aimsun-console` tooling, not the corpus-agnostic memory seam.
