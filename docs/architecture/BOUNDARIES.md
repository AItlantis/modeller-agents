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

## Proposed: Typed Packs & Knowledge Axis (draft)

A second, orthogonal knowledge axis is proposed alongside today's repository-selection axis: routing would also resolve `intent.domains[]` against a data-only registry to load knowledge packs that link into `modelling-knowledge`, without adding domain names to code or growing skill count. See `docs/architecture/typed-packs-knowledge-axis.md` for the draft design and `modelling-knowledge/decisions/0005-knowledge-vault-domain-scope.md` (pending) for the related vault-scope ruling.

