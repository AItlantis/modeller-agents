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

