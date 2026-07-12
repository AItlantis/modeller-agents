---
workflow_id: modeller-agents-build
run_id: orchestration-readiness-001
artifact: handoff
step: handoff
status: complete
updated_by: orchestrator
updated_at: 2026-07-10T20:57:33Z
---










# Handoff

## Purpose

Purpose: Handoff final state for deterministic modeller-agents orchestration after packaging/runtime asset hardening.
## Evidence

Evidence: Final state now includes packaging metadata doctor validation, wheel force-include mappings for plugin/runtime assets, installer fallback from source checkout to packaged modeller/runtime assets, UTF-8 TOML parser support for inline tables and quoted keys used by pyproject, and README first-run command alignment. Verification commands run: modeller-agents pytest 41 passed, normal doctor JSON passed, readiness JSON still reports the current 10 blockers, py_compile passed, modeller-pipelines conformance passed, and template tests passed. Subagent findings from Nietzsche identified wheel runtime asset omission, missing build/install smoke, and README first-run ambiguity; runtime asset packaging and README ambiguity were addressed, while real wheel build smoke remains unproven because local build/hatchling tooling is not installed.
## Decisions Or Outputs

Output: Updated files include pyproject.toml, src/modeller/install.py, src/modeller/doctor.py, src/modeller/toml_compat.py, tests/test_doctor_cli.py, README.md, docs/COMMANDS.md, and this handoff artifact. Residual risks remain: strict readiness blockers are unchanged, and a real wheel/editable install smoke still needs build tooling. Next actions are to install/provision build tooling for a real package build smoke, then execute the readiness action plan for vendor pins, backend smoke, and pack promotion.
## Verification

Verification: workflow gate terms covered: final state, verification, residual risks, next actions, and subagent findings. The workflow gate will be checked after this artifact write.

## Closure Update - 2026-07-11

Final state now also includes the requested global architecture/workflow document and vault-wide `modeller-agents` reference reconciliation. `modeller-agents/docs/architecture/ARCHITECTURE_AND_WORKFLOW.md` describes the current architecture, CLI surfaces, install model, routing model, deterministic workflow, backend seam, readiness modes, evidence commands, residual risks, and next actions. `modelling-knowledge` now records `modeller-agents` as an active scaffolded runtime rather than a nonexistent future plan, with `asm` and `open-agent` treated as superseded ideas.

Subagent findings incorporated: Peirce identified the architecture/workflow overview shape and readiness invariants; Hume identified stale modelling-knowledge reference targets; Epicurus independently confirmed stale source-of-truth references; Popper updated the historical baseline and inventory slice. Residual risks remain: strict readiness is still blocked by draft packs, planned vendors/backends, schema fallback, and missing real backend smoke/build-install evidence. Next actions remain pack activation/retirement, vendor pinning/sync, schema vendoring, and real backend smoke once build/runtime prerequisites are available.

Final verification: `python -m pytest` in `modeller-agents` passed 41 tests; `python -m pytest -q -p no:cacheprovider conformance` in `modeller-pipelines` passed 24 tests; `python -m pytest template\tests` in `modeller-pipelines` passed 9 tests; normal `modeller.cli doctor --json` passed; `modeller.cli readiness --json` failed as expected with 10 known blockers; stale-reference searches found no remaining stale `modeller-agents` nonexistent/future/current-asm claims; generated test caches were removed.
