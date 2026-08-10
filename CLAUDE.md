# Claude Guide — modeller-memory

Read [`AGENTS.md`](AGENTS.md) first; it is the canonical guide. This file adds
only what is Claude-specific.

**Persistent memory.** Cross-session notes for this repo and its sibling
`modeller-agents` live under
`C:\Users\jean-noel.diltoer\.claude\projects\C--Users-jean-noel-diltoer-software-sources\memory\`
(see `project_modeller_repos.md`). Check it for plan/status context before
assuming AGENTS.md is the whole story.

**One-line reminder:** never add a `vault_doctor` import to any runtime
module outside `src/modeller_memory/tools/vault_doctor/` — the import-guard
test (`tests/test_import_guards.py`) will fail the build.
