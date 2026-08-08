# Boundaries

`modeller-agents` exists to centralize reusable agent methods without centralizing repository-local authority.

## Owns

- Central reusable skills.
- Runtime routing and workflow gates.
- Backend runtime registry.
- Reference pack format and bundle manifests.
- Plugin wiring for the central skill surface.

## Does Not Own

- Testudo product UI, permissions, or runtime behavior.
- Aimsun PSP backend implementation.
- Pipeline contract schemas owned by `modeller-pipelines`.
- Generated memory indexes or memory storage internals owned by `modeller-memory`.
- Durable curated knowledge owned by `modelling-knowledge`.
- Repository-local agents.

## First Runtime Chain

```text
context envelope
  -> repository selection
  -> skill selection
  -> knowledge retrieval
  -> optional memory query
  -> source-boundary check
  -> proposal or bounded action
  -> structured result
```

## Typed Packs & Knowledge Axis (implemented, currently deactivated)

A second, orthogonal knowledge axis runs alongside the repository-selection axis: routing resolves
`intent.domains[]` against a data-only domain registry to load knowledge packs that link into
`modelling-knowledge` by note id — without adding domain names to code or growing skill count.
Knowledge packs are **references, never copies** (route retrieves note ids/metadata only, no bodies).

Status as of 2026-07-14: the axis and the `accessibility` pilot pack
(`reference-packs/domains/accessibility.toml`) are implemented and test-covered, but the vault has
**deactivated domain routability (F-A)** — `modelling-knowledge/registry/knowledge-domains.yml` marks
`product`/`accessibility`/`transport` `draft`/`routable:false`. So the pilot pack is **rejected at
route**, while `modeller.cli doctor` reports the mirrored disabled state as a normal development
warning. Re-activation is gated on this repo accepting the D3–D6 conditions at general scope
(decision 0010, still `proposed`) and the vault-side DR-1 attribution cure.

See `docs/architecture/typed-packs-knowledge-axis.md` (design), `docs/architecture/typed-packs-open-decisions.md`
(D3–D6 rulings, pilot-scope), and `modelling-knowledge/decisions/0005-knowledge-vault-domain-scope.md`
(**accepted** vault-scope ruling).

## Addendum: Mission/Task/Checkpoint/Dispatch-Grant Contracts (TESTUDO-P1-modeller-agents)

Added under the "Owns: Runtime routing and workflow gates" heading above, as part of hardening the
orchestration/dispatch control-plane surface for future Testudo-side consumption
(`reference-packs/testudo.toml`, `bundles/testudo.bundle.json`):

- `ArtifactLineageDigest`, `MissionIdentity`, `CheckpointAuthorization`, `CheckpointReceipt`,
  `IdentityValidation` dataclasses and `validate_mission_identity()` / `validate_checkpoint_receipt()`
  in `src/modeller/contracts.py`, with schemas `schemas/mission-identity.schema.json` and
  `schemas/checkpoint-receipt.schema.json`.
- `CapabilityGrant` dataclass and `validate_dispatch_request()` / `validate_dispatch_identity_binding()`
  (plus path-containment helpers) in `src/modeller/contracts.py`, binding capability grants
  (role/provider/tools/write_scope) to dispatched subagent work orders.
- Checkpoint-gated workflow resume support (`CheckpointVerification`, `write_task_checkpoint`,
  `verify_task_checkpoint`, `resume_workflow_from_checkpoint`) in `src/modeller/workflow.py`, and
  mission-identity binding plus checkpoint-gated persist/ingest on subagent lane receipts in
  `src/modeller/subagents.py`.

These contracts describe *how* work orders, checkpoints, and dispatch grants are structured and
validated inside `modeller-agents`. They do not implement, call, or depend on any Testudo API,
PostgreSQL, or DuckDB integration — no such gateway exists yet, and building one remains explicitly
out of scope for this mission.

**Pipeline-schema-ownership boundary is unchanged.** No file under this mission touched
`PipelineDefinition`, `PipelineCapabilityProfile`, `PipelinePlan`, `PipelineRunRequest`,
`PipelineRunReceipt`, `CanonicalDatasetManifest`, or `ArtifactManifest`, nor any schema owned by
`modeller-pipelines`. This reaffirms `AGENTS.md`'s Forbidden list verbatim:

> Forbidden:
>
> - move repository-local agents into this repository;
> - copy backend implementation from `aimsun-psp`;
> - copy Testudo product UI/runtime logic;
> - define pipeline schemas owned by `modeller-pipelines`;
> - store generated memory indexes as authority;
> - edit vendored subtrees by hand.

