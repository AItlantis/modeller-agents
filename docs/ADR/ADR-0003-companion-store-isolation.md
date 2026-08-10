# ADR-0003 — Companion-store isolation

**Status:** accepted
**Date:** 2026-07-11
**Owner:** `modeller-memory`
**Related:** [`docs/INTEGRATION_PLAN.md`](../INTEGRATION_PLAN.md) §6.2, §6.3; sibling
[`ADR-0001`](ADR-0001-generated-memory-layers.md) (companion is the tier-4 layer this ADR isolates)
and [`ADR-0004`](ADR-0004-vault-promotion-seam.md) (a promotion candidate originates from the
companion store this ADR scopes); antagonist finding AM-08; ORCHESTRATION O2

## Context

The earlier plan recommended a single global companion store (`~/.modeller-memory/`) without a
namespace or isolation model. A global store can mix different clients, projects, public and
restricted repositories, personal preferences, and commercial modelling evidence — a
cross-project / cross-client leakage risk.

## Decision

1. **Scoped store topology.** The store is namespaced, not flat:
   ```text
   ~/.modeller-memory/
   ├── stores/
   │   ├── user/
   │   ├── organizations/<organization-id>/
   │   └── projects/<project-id>/
   ├── indexes/
   └── config/
   ```
2. **Every record carries scope metadata:** `tenant_id`, `project_id`, `repository_id`,
   `sensitivity`, `visibility_scope`.
3. **Retrieval requires an explicit scope.** `memory.search(query, tenant_id=…, project_id=…,
   allowed_sensitivity=[…])`. **With no explicit project/tenant scope, retrieval returns nothing.**
   Unrestricted global semantic search is never the default.
4. **Governance operations are mandatory** (not just decay): `create · read · search · correct ·
   supersede · expire · delete · export · purge-project · purge-tenant`, with retention-by-scope,
   user-requested deletion, project-close pruning, false-memory correction, sensitivity up/downgrade,
   promotion trace, encryption decision, backup, crash recovery, concurrency handling, and
   conversation-material sanitisation before write.

## Consequences

- Global-by-default is rejected; O2 resolves toward scoped isolation, decided at M5.
- Companion recall cannot leak across projects/tenants/sensitivity by construction — enforced by the
  default-empty scope rule and verified by the M6/M7 evaluation gates (zero cross-project/
  restricted-scope leakage).
