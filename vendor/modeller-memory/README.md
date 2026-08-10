# modeller-memory

The memory subsystem for the modelling ecosystem, and — today — the home of
**`vault_doctor`**, the read-only, host-agnostic validator and index exporter for the
`modelling-knowledge` vault.

Agent-facing guidance (boundaries, authority routing, what's actually built) lives in
[`AGENTS.md`](AGENTS.md), with a short Claude-specific addendum in
[`CLAUDE.md`](CLAUDE.md). This README stays human-facing.

Be clear about what ships versus what is designed: **`vault_doctor` is the mature,
tested tool** in this repository. The **Phase 1 memory runtime** now includes the
candidate classification seam (`AuthorityContext`, `ContextReceipt`,
`MemoryCandidate`, `validate_authority_context()`, `classify()`, and the candidate
event ledger value objects). The **Phase 6 companion scaffold** includes an
explicitly instantiated, scoped in-memory `MemoryProvider`; persistent storage,
standing recall, and backend adapters remain future work. See
[Future features](#4-future-features).

## 1. Purpose

`modeller-memory` is the embeddable **memory subsystem** for the modelling ecosystem. Its
Phase 1 runtime can *propose* — classify a captured observation into a typed
`MemoryCandidate` and hand it off — while never becoming an authority over accepted
knowledge. It sits alongside two sibling repositories:

- **`modelling-knowledge`** — the vault: the authority of record for accepted knowledge,
  its metadata standard, controlled vocabularies, and the knowledge-domain registry.
- **`modeller-agents`** — owns the executable skills and the memory *agent* that
  *transports* a candidate (validates the destination and performs the inbox write). It
  also owns **routing**; `modeller-memory` implements none.

`vault_doctor` is co-located here **by user decision, but kept strictly outside the memory
runtime's authority surface** (see [`docs/ADR/ADR-0005-vault-doctor-colocation.md`](docs/ADR/ADR-0005-vault-doctor-colocation.md)).
The isolation is not just documented — it is **machine-enforced**:
[`tests/test_import_guards.py`](tests/test_import_guards.py) scans every module under
`src/modeller_memory/` except `tools/vault_doctor/` and fails if any of them so much as
names `vault_doctor`. The memory runtime can therefore be built, tested, and shipped
without the tool, and the tool runs without the runtime; they share only the Python
package namespace and the packaging/CI scaffold.

Boundaries that hold across the whole repository:

- **Reads only the metadata index of `modelling-knowledge`.** The memory runtime has no
  vault read or write path (ADR-0004). `vault_doctor` reads the vault *files* read-only via
  an explicit `--vault-path`, and never writes, moves, or deletes anything inside it.
- **Owns no knowledge authority.** The vault declares the rules; `vault_doctor` only
  enforces what the vault already declares. Acceptance of knowledge is the board's alone.
- **Implements no routing.** That belongs to `modeller-agents`.

## 2. Installation & usage

The repository is a standard `setuptools` Python package (see
[`pyproject.toml`](pyproject.toml)), targeting **Python ≥ 3.10** with **`pyyaml`** as its
only runtime dependency. (`pydantic` is deliberately *not* a dependency — `vault_doctor`
stays stdlib + `pyyaml`.)

```bash
# from the repository root
python -m pip install -e .            # runtime deps
python -m pip install -e ".[dev]"     # + pytest, for running the tests
```

Installing also registers a `vault-doctor` console script. Either invocation form works:

```bash
# via the module (no install required, from the repo root)
python -m modeller_memory.tools.vault_doctor.cli <cmd> --vault-path <vault>

# via the installed console script
vault-doctor <cmd> --vault-path <vault>
```

`--vault-path` is optional; it defaults to a sibling `../modelling-knowledge`.

### Commands

```bash
# Validate the vault. Exits non-zero on any blocking finding.
python -m modeller_memory.tools.vault_doctor.cli check --vault-path ../modelling-knowledge
# Treat warnings as failures too (off by default — warnings never fail a run):
python -m modeller_memory.tools.vault_doctor.cli check --vault-path ../modelling-knowledge --warnings-as-errors

# Emit the deterministic vault-index JSON (stdout, or -o PATH).
python -m modeller_memory.tools.vault_doctor.cli export-index --vault-path ../modelling-knowledge -o vault-index.json

# Emit the deterministic knowledge-domains JSON.
python -m modeller_memory.tools.vault_doctor.cli export-domains --vault-path ../modelling-knowledge -o knowledge-domains.json
```

Exit codes for `check`: `0` pass, `1` blocking failure (or a warning under
`--warnings-as-errors`), `2` the vault path does not exist.

### Tests

```bash
python -m pytest tests -q                        # full suite
python -m pytest tests/test_import_guards.py -q  # the isolation guard alone
python -m pytest tests/policy tests/candidate tests/companion -q # runtime + companion scaffold
```

The **import-guard test**
(`test_runtime_modules_do_not_import_vault_doctor`) is the machine-enforced boundary from
ADR-0005: it asserts that **no module outside `src/modeller_memory/tools/vault_doctor/`
imports or names `vault_doctor`**, so the memory runtime can never take a
dependency on the vault tool.

### Decisions and contracts

Ratified decisions live in [`docs/ADR/`](docs/ADR/) (ADR-0001 generated-memory
non-authority, ADR-0002 skill ownership, ADR-0003 companion-store isolation, ADR-0004
vault promotion seam, ADR-0005 `vault_doctor` co-location). The runtime API surface those
decisions authorize is specified in [`docs/contracts/`](docs/contracts/README.md)
(`candidate-contract.md` implemented, `companion-contract.md` an in-memory scaffold, the
rest planned). Milestones and cross-repo status are tracked in
[`docs/INTEGRATION_PLAN.md`](docs/INTEGRATION_PLAN.md).

### Other tooling in this repository

- **`skills/document-knowledge-acquisition/`** — a repo-local skill (not an
  ecosystem-shared one; see ADR-0002) for staging document corpora (DOCX/PDF report
  sets) into Markdown, evidence matrices, and discovery drafts for `modelling-knowledge`.
- **`src/modeller_memory/tools/drieat_import/`** — the CLI that skill documents for the
  DRIEAT report corpus (`build`, `validate-source`, `install`, `validate-package`).

## 3. Features

Everything below is implemented and tested today, in
`src/modeller_memory/tools/vault_doctor/`. `vault_doctor` walks the vault read-only,
parses YAML front matter, builds the wikilink / relative-markdown link graph, and runs a
registry of blocking and warning checks.

**Validation (`check`):**

- **Metadata / profile validation** — classifies each note into a metadata profile
  (context, accepted-knowledge, governance, planning-evidence, discovery-draft) and
  enforces the required-field set for authority-bearing (accepted/active) notes, plus YAML
  front-matter parse errors.
- **Controlled-vocabulary checks** — `status`, `authority_level`, `sensitivity`, and
  profile-scoped `type` must be valid; transitional sensitivity labels are flagged for
  normalization.
- **Note-id resolution & duplicate detection** — authority-bearing notes must carry a
  stable `id`; duplicate ids and (as a warning) duplicate filenames are reported; internal
  wikilinks and relative markdown links must resolve (broken-link check).
- **Parity checks** — the decisions-index status column must match each decision note's
  own status, and `registry/repositories.yml` must be in one-to-one parity with
  `repository_maps/`.
- **Active-domain registry gates & eligibility rules** — active/routable knowledge-domain
  entries must satisfy the VA2 gate (stable id, aliases, sensitivity ceiling, resolvable
  accepted index note, at least one eligible accepted non-index note); accepted notes must
  declare a registered domain; domain aliases must be collision-free. Note eligibility for
  a domain is decided by `_eligible_for_domain` (profile, status, authority level, id,
  supersession, sensitivity ceiling, allowed types).
- **Sensitivity fence** — public notes may not link to, embed, or declare derivation from
  restricted content without a passing redaction review.
- **Inbox discovery-draft validation** — drafts under `inbox/discovery-drafts/` are checked
  against the discovery-draft contract: required fields, `status: draft` / `type:
  discovery-draft` vocabularies, sensitivity set, **no accepted-authority inflation** (a
  draft must never masquerade as accepted), and an **inbound sensitivity fence** (a draft
  referencing restricted evidence must itself be classified `restricted`). Stale drafts are
  a warning.
- **Forbidden Obsidian files** — personal `.obsidian/*.json` workspace files must not be
  git-tracked.

**Exports (`export-index` / `export-domains`, VA3):** deterministic, **byte-identical**
JSON for an unchanged vault — notes sorted by id, keys sorted, volatile fields (e.g.
`generated_at`) omitted by default. Each export carries a content digest; `export-domains`
computes a **per-domain** notes digest so a knowledge pack pinned to one domain is not
invalidated by unrelated vault edits.

**Shared eligibility conformance:** the test suite consumes the **N-1
`eligibility-conformance.json` fixture** published by the sibling vault
(`modelling-knowledge/docs/dev/fixtures/`) to assert that `vault_doctor`'s eligibility rule
agrees with the vault's own conformance cases; it skips gracefully when the sibling vault
is not present.

## 4. Runtime and Future Features

The Phase 1 candidate runtime is implemented and tested. It is specified in
[`docs/INTEGRATION_PLAN.md`](docs/INTEGRATION_PLAN.md),
[`docs/ADR/ADR-0004-vault-promotion-seam.md`](docs/ADR/ADR-0004-vault-promotion-seam.md),
and the build-ready plan
[`docs/dev/N2-C1-classify-runtime-plan.md`](docs/dev/N2-C1-classify-runtime-plan.md).

- **`MemoryCandidate` model** — a typed, immutable transport record
  (`candidate_id`, `classification`, `claim`, `provenance`, `sensitivity`, `target` ∈
  `vault-inbox | companion | discard | flag`, `confidence`, `related_decisions`,
  `origin_run`) plus its `AuthorityContext` input, backed by
  `schemas/memory-candidate.schema.json` and `docs/contracts/candidate-contract.md`.
- **`ContextReceipt` model** — records retrieval query, searched domains, candidate notes,
  selected notes, excluded notes and reasons, algorithm version, budget, ranking,
  permissions, receipt digest, and optional authority-context digest.
- **Candidate event ledger** — immutable, JSONL-friendly transition events
  (`CandidateLedgerEvent`, `CandidateEventLedger`, `record_candidate_transition()`) with
  digest chaining. The ledger is pure runtime state and performs no vault or file I/O.
- **`classify_with_ledger(...)`** — an opt-in helper that returns the classified candidate,
  the candidate ledger event, and the updated in-memory ledger. `classify()` itself still
  returns only `MemoryCandidate`, preserving the transport contract.
- **`classify(candidate, authority_context, *, context_receipt=None, current_index_digest,
  current_authority_context_digest=None)`** — the single propose-seam entrypoint. It runs
  the **N-2 authority-context validator** first: completeness checks, vault pinning to
  `modelling-knowledge`, receipt checks, and digest currency checks against caller-supplied
  strings. Incomplete or stale context forces `target="flag"`, never `vault-inbox` or
  silent discard. Contradictions also flag and carry the conflicting reference.
- **The vault-inbox promotion seam (decision 0007 C1)** — `modeller-memory`
  *proposes* and stops at returning the typed `MemoryCandidate`; `modeller-agents`
  *transports* (validates and writes the discovery draft into `inbox/discovery-drafts/`);
  `modelling-knowledge` *governs* (board acceptance). The return value **is** the seam; this
  repo never writes to the inbox.
- **Scoped companion memory scaffold** — `MemoryProvider`, `MemoryScope`,
  `CompanionRecord`, and `InMemoryMemoryProvider` provide process-local, explicit-scope
  storage for generated context. Blank scope returns no results, sensitivity filters apply,
  and no promotion or vault write path exists. Persistent JSONL/storage adapters, standing
  recall, and backend integration remain deferred.

Additional planned contracts and schemas (query, health/readiness, manifest, index-scope)
are indexed as **planned M0 deliverables** in `docs/contracts/README.md` and
`schemas/README.md`.

Current companion scope is intentionally narrow: the in-memory provider is useful for interactive
companion tests and workflow feedback, but it does not persist records, perform standing recall, or
promote anything into the vault. Those paths stay behind future backend/adaptor work.
