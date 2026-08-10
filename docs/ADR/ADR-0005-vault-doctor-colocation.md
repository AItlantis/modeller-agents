# ADR-0005 — vault_doctor co-location in modeller-memory

**Status:** accepted
**Date:** 2026-07-11
**Owner:** `modeller-memory` (personal identity: jnd.diltoer@hotmail.fr)
**Related:** [`docs/INTEGRATION_PLAN.md`](../INTEGRATION_PLAN.md) §3, §3.2, §4 (layout), §7 (orthogonal track);
sibling [`ADR-0002`](ADR-0002-skill-ownership.md) (the skill-ownership boundary this tool respects — it ships no skill)
and [`ADR-0004`](ADR-0004-vault-promotion-seam.md) (the discovery-draft promotion seam whose inbox drafts `vault_doctor` validates);
[`modelling-knowledge/docs/dev/vault-alignment-plan.md`](../../../modelling-knowledge/docs/dev/vault-alignment-plan.md) ("Validation Additions / vault_doctor",
"Vault Index Contract", "Vault Eligibility", and the 2026-07-12 Antagonist Direction Review findings **DR-6 / N-3** targeting this ADR);
`modelling-knowledge/docs/dev/vault-optimisation-plan.md` Phase E / Phase G;
`modelling-knowledge/standards/knowledge-metadata-standard.md`;
`modelling-knowledge/docs/dev/vault-index-schema.md`

> **N-3 — SATISFIED (2026-07-12):** `modelling-knowledge`'s antagonist review required a machine-enforced
> guarantee that **no memory runtime module imports `tools/vault_doctor`**. This is now enforced by
> `tests/test_import_guards.py::test_runtime_modules_do_not_import_vault_doctor` (scans all of
> `src/modeller_memory/` except `tools/vault_doctor/` and asserts zero `vault_doctor` references) —
> the isolation this ADR argues in prose is now machine-checked, not just documented.

## Context

The `modelling-knowledge` vault-optimisation plan (Phase E) calls for a `vault_doctor`
validation-and-export tool that enforces the vault's own declared metadata rules and emits the
`vault-index.json` / `knowledge-domains.json` exports (Phase G / VA3). The plan sketches it as
`scripts/vault_doctor.py` living inside the vault repo, but a per-user decision instead co-locates
the implementation in **`modeller-memory`**, where the Python packaging, tests, and CI already have
a home.

This raises a boundary concern. `modeller-memory`'s INTEGRATION_PLAN is emphatic that the memory
subsystem has **no read or write path into the vault** and is **never an authority over vault
metadata**:

> "Memory reads nothing from the vault — no read path exists or is planned … Memory never writes
> to the vault and is never authoritative over accepted knowledge." (INTEGRATION_PLAN §3.2)

> "must not let its own domain taxonomy become a second write authority over vault-scoped subjects."
> (INTEGRATION_PLAN §3, Knowledge row)

A vault validator that parses the vault and emits its index could, if wired into the memory
runtime, become exactly the vault-authority path the plan forbids. This ADR records why co-locating
the tool here does **not** breach that boundary.

## Decision

1. **`vault_doctor` is host-agnostic vault-validation tooling, co-located in this repo by user
   decision — not part of the memory subsystem.** It lives under
   `src/modeller_memory/tools/vault_doctor/` — a `tools/` namespace deliberately **separate** from
   the memory runtime (`adapters/`, `policy/`, `candidates/`, `mcp/`, `integration/`).

2. **It is NOT on the memory authority surface.** No memory runtime module imports `vault_doctor`,
   and `vault_doctor` is never wired into memory retrieval, candidate classification, the code
   graph, companion recall, or the MCP tool surface. It is a standalone CLI (`vault-doctor` console
   entry point) and a set of importable functions, invoked by a human or by CI — not by the memory
   engine. The retrieval runtime described in INTEGRATION_PLAN §2 and §3.2 still has **no vault read
   path**; that statement remains true after this ADR.

3. **It takes the vault as an explicit argument.** The vault location is a `--vault-path` CLI
   argument (default: discover a sibling `../modelling-knowledge`; no absolute path is hardcoded).
   The vault is **not** vendored, subtree'd, or indexed by memory — `vault_doctor` is a CLI *pointed
   at a path*, exactly like any external linter. This is distinct from memory's index scope, which
   is the host working tree plus the two `vendor/` prefixes only (ORCHESTRATION D3); the vault is
   never in that scope.

4. **It is strictly read-only against the vault.** `vault_doctor` parses, validates, and exports.
   It never writes, moves, or deletes any file under the vault. The two exports it can produce
   (`vault-index.json`, `knowledge-domains.json`) are emitted to stdout or to a caller-chosen path
   outside the vault; the tool never creates files inside `modelling-knowledge/`.

5. **The vault remains the authority of record.** `vault_doctor` only enforces rules the vault
   *itself declares* — the controlled vocabularies, the four metadata profiles, the stable-identity
   rules, the sensitivity/exposure model, the registry↔map and decision-index parity — all sourced
   from `modelling-knowledge/standards/knowledge-metadata-standard.md`, the vault-alignment-plan,
   and the vault-optimisation-plan. If those declared rules change, this tool is updated to track
   them. The tool does not originate vault policy and does not decide whether a note is accepted,
   authoritative, current, or exposable — it reads and checks the vault's own declarations.

## Consequences

- The vault plan's `scripts/vault_doctor.py` location is superseded (for the implementation) by
  `modeller-memory/src/modeller_memory/tools/vault_doctor/`. The vault repo may still choose to
  invoke or vendor the CLI later; the ownership of vault *rules* stays with `modelling-knowledge`.
- Because the tool is isolated in `tools/`, the memory subsystem can be built, tested, and shipped
  without `vault_doctor`, and `vault_doctor` can be run without the memory runtime. The two share
  only the Python package namespace and the packaging/CI scaffold.
- CI for `vault_doctor` runs the fixture-based test suite only; it does **not** run `check` against
  the real vault (that repo is not present in this repo's CI). Running against the real vault is a
  local/manual step, and any blocking finding it surfaces is a *vault-side* finding reported back to
  `modelling-knowledge` — never a reason for this tool to modify the vault.

## Boundary restatement (for the record)

- Memory runtime → vault: **no read path, no write path.** Unchanged by this ADR.
- `vault_doctor` → vault: **read-only, explicit path, host-agnostic, outside the memory authority
  surface.** Enforces the vault's declared rules; originates none of them.
- Authority of record over vault metadata: **`modelling-knowledge`.** Unchanged.
