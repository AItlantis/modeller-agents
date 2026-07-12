# modeller plugin

This plugin exposes central reusable skills for modelling work.

It intentionally does not include repository-local agents from Testudo, Aimsun PSP, or other source repositories. Local agents stay in their owning repositories and call these reusable skills.

## Runtime Agent

- `orchestrator`: central router for choosing a repository boundary and reusable skill.

## Seed Skills

- `workflow`
- `orchestrate`
- `source-boundary-check`
- `antagonist-review`
- `review`
- `memory-recon`
- `backend-contract-check`
- `backend-scaffold`
- `backend-align`
- `pipeline-fix`
- `pipeline-review`
- `pipeline-smoke`
