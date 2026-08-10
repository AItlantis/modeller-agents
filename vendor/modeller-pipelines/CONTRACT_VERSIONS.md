# Contract Versions

This table maps each published contract version to its git tag and current support status.

| contract_version | git tag         | status  | support           |
|-----------------|-----------------|---------|-------------------|
| 1.2             | contract-v1.2   | current | supported (N)     |
| 1.1             | contract-v1.1   | previous| supported (N-1)   |
| 1.0             | contract-v1.0   | retired | unsupported (N-2) |

---

## Versioning rules

**Minor revision** (e.g. 1.0 → 1.1): strictly additive changes only. New optional fields may be
added to any schema. Existing required fields MUST NOT be removed, renamed, or have their type
changed. A backend conforming to contract version N MUST continue to pass conformance after a minor
revision without modification.

**Major revision** (e.g. 1.x → 2.0): any breaking change — removed fields, renamed keys, changed
field types, altered CLI subcommand signatures, or altered result envelope semantics — requires a
major version bump. Backends MUST explicitly migrate and update their `contract.lock` before the new
major version is considered active for them.

## Support window

The conformance kit and modeller-agents tooling support the **current (N) and previous (N-1)**
contract major versions. When a new major version ships, the N-2 version becomes unsupported.

The conformance kit MUST refuse to run against a backend whose `contract_version` is older than the
N-1 floor, and MUST emit a loud, actionable error message naming the detected version, the minimum
supported version, and a link to the migration guide.

Silence or graceful degradation on unsupported versions is explicitly prohibited.
