# ADR-0002: One contract_version for the whole surface

**Status:** accepted  
**Date:** 2026-07-09

## Context

We need a versioning scheme for the contract surface (pipeline.schema.json, step-result.schema.json, result.schema.json, backend.schema.json, run-config.schema.json). Options considered:
1. Per-schema versions (e.g. `pipeline_schema_version: "1.2"`, `result_schema_version: "1.0"`).
2. One `contract_version` covering all schemas simultaneously.

Per-schema versions create sprawl: a backend must track five version numbers, compatibility checks become cross-product logic, and it becomes unclear which combinations are valid.

## Decision

One `contract_version` string covers the entire surface. Current version: `"1.0"`.

- **Minor bump** (e.g. `"1.0"` → `"1.1"`) = strictly additive: new optional fields only. Backends pinned to `"1.0"` continue to pass conformance against `"1.1"` schemas.
- **Major bump** (e.g. `"1.0"` → `"2.0"`) = anything breaking: renamed fields, removed fields, changed semantics.
- **Support window:** N and N-1. The conformance kit refuses backends declaring a version older than N-1 with a loud error.
- **Declared twice:** statically in `backend.json`, dynamically in every `result.json`. `modeller doctor` cross-checks them.
- **Released as git tags:** `contract-v1.0`, `contract-v1.1`, etc. Backends pin in `contract.lock`.

## Cultural rule

The contract earns changes **from backends, not from the template**. A field enters a schema when a real backend needs it (second-use test applied to the contract itself). The template's `trip_summary` pipeline does not drive schema evolution; real backends do.

## Consequences

- Simpler compatibility checking: one number to compare, not five.
- A single `modeller doctor` command checks all surfaces at once.
- Schema evolution is conservative by design — the second-use test prevents speculative fields.
- Tradeoff: a minor change to one schema bumps the version for all schemas, even those that didn't change. Accepted cost for simplicity.
