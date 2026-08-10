# N-2 / C1 - Classify + Conflict-Check Runtime Build Plan

**Status:** implemented build plan - **Date:** 2026-07-12; implementation verified 2026-07-14 - **Owner:** `modeller-memory`
**Milestone:** M1 (policy core) + the classify half of M4 (candidate triage), per `docs/INTEGRATION_PLAN.md` sec.7
**Closes (jointly, once built + exercised):**
- Enforcement need **N-2** at *general scope* - `authority_context` completeness/currency validation at **memory conflict-check time** (not only pack-load). Source: `modelling-knowledge/docs/dev/vault-alignment-plan.md` DR-5 / N-2 (~L662, L698-704).
- Decision **0007** condition **C1** - exercise the seam against one real `MemoryCandidate` end-to-end into the vault inbox. Source: `modelling-knowledge/decisions/0007-memory-promotion-coordination.md` (Promotion Gate C1/C2, L33-34; Follow-Up 1).

**Design basis (verified against source):** `docs/ADR/ADR-0004-vault-promotion-seam.md`; `docs/INTEGRATION_PLAN.md` sec.3.1a (L192-256), sec.3.2 (L338-367), sec.4 layout (L444-485), sec.5 (L509-527); `modelling-knowledge/standards/discovery-draft-schema.md`; `modeller-agents/src/modeller/knowledge_packs.py` L309-353 (authority_context completeness pattern) and L387-418 (digest currency pattern).

This document is the historical build plan for the now-implemented Phase 1 candidate runtime. The
current implementation lives under `src/modeller_memory/candidate/`, with companion scaffolding under
`src/modeller_memory/companion/`; the plan remains useful as the boundary rationale and test design.

---

## 0. Boundary guards this plan is built to satisfy (non-negotiable)

| Guard | Source | How this plan complies |
|---|---|---|
| No runtime module outside `tools/vault_doctor/` may contain the string `vault_doctor` | `tests/test_import_guards.py` (substring scan) | The new `policy/`, `candidate/` modules never import from, reference, or name the vault tool. The vault export digest is **passed in** by the caller (see sec.2, sec.3), read from the committed artifact `modelling-knowledge/docs/dev/vault-index.json`, never via `tools/vault_doctor/export.py`. Test files that assert on the digest use a **literal fixture string**, not the exporter. |
| Memory subsystem must not read or write the vault (ADR-0004 AM-01/AM-02) | ADR-0004 Decision sec.1, sec.3 | Classify takes `authority_context` + `current_index_digest` as **inputs**. No filesystem access to the vault. No write path. The runtime returns a typed object; it never touches `inbox/`. |
| Inbox write authority is the `modeller-agents` memory agent only | 0007 L72/78, ADR-0004 sec.1 | The runtime stops at returning `MemoryCandidate(target="vault-inbox")`. The seam boundary (sec.3) is the return of that object; transport/write is `modeller-agents`. |
| Vault must not implement memory runtime | INTEGRATION_PLAN sec.3.2 | All new code lands under `modeller-memory/src/modeller_memory/`; the vault gains nothing. |
| `pydantic` is not a dependency of the light path | `pyproject.toml` L16-18 | The candidate/policy runtime uses stdlib `dataclasses` + `pyyaml` (already a dep). M1 stays stdlib-only so the tool and the classify core share the same light footprint. |

---

## 1. New module layout, responsibilities, and public signatures

All paths under `modeller-memory/src/modeller_memory/`. This realises the PLANNED tree in `INTEGRATION_PLAN.md` sec.4 (L456-473), narrowed to exactly what N-2 + C1 require. Nothing here imports `tools/`.

```
src/modeller_memory/
  policy/
    __init__.py
    authority.py          # NEW - authority_context completeness + currency validator (N-2)
    classification.py     # NEW - deterministic candidate -> target decision
  candidate/
    __init__.py
    model.py              # NEW - MemoryCandidate + AuthorityContext + Result dataclasses
    classify.py           # NEW - top-level classify(candidate, authority_context, *, current_index_digest)
  (tools/vault_doctor/ unchanged - do not touch)

schemas/
  memory-candidate.schema.json   # NEW - MemoryCandidate transport contract (JSON Schema 2020-12)

docs/contracts/
  candidate-contract.md          # NEW - prose contract for classify()/the candidate shape (INTEGRATION_PLAN sec.5 candidate side)
```

> Naming note: `INTEGRATION_PLAN.md` sec.4 shows `candidates/` (plural) and `policy/classification.py`. The recon brief suggests `candidate/` (singular) and `candidate/classify.py`. This plan uses **`candidate/`** (singular) as the brief directs and keeps `policy/classification.py` for the classifier policy, with the thin orchestration entrypoint at `candidate/classify.py`. Whichever the team ratifies, keep it consistent across schema `$id`, contract doc, and imports.

### 1.1 `candidate/model.py` - typed records (stdlib dataclasses)

Responsibility: the transport shapes. No I/O, no policy. Frozen dataclasses so a returned candidate is immutable.

```python
@dataclass(frozen=True)
class AuthorityContext:
    vault: str                       # must be "modelling-knowledge"
    domain_registry: str             # ref to registry/knowledge-domains.yml (id or path)
    scope_decision: str              # e.g. "0005-knowledge-vault-domain-scope"
    knowledge_seam_decision: str     # e.g. "0009-vault-side-knowledge-seam"
    coordination_decision: str       # e.g. "0007-memory-promotion-coordination"
    checked_at: str                  # ISO-8601 date/datetime, non-empty
    source_index_digest: str         # vault-index digest the orchestrator pinned at capture (currency anchor)
    accepted_refs: tuple[str, ...] = ()   # accepted-knowledge note ids/paths the candidate is judged against
    source_commit: str | None = None

@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    classification: str              # multi-axis summary label (see sec.1.3)
    claim: str
    provenance: dict                 # {origin_run, source_repository, source_commit, evidence_refs: [...]}
    sensitivity: str                 # public | internal | restricted
    target: str                      # vault-inbox | companion | discard | flag
    confidence: float                # 0.0-1.0
    related_decisions: tuple[str, ...]
    origin_run: str
    conflicting_ref: str | None = None            # set when target in {discard, flag}
    authority_context_refs: tuple[str, ...] = ()  # echoed for the draft front matter

@dataclass(frozen=True)
class Result:
    ok: bool
    errors: tuple[str, ...] = ()     # completeness/currency failure messages (N-2)
    warnings: tuple[str, ...] = ()
```

Rationale: `MemoryCandidate` carries every field ADR-0004 sec.2 lists (`candidate_id, classification, claim, provenance, sensitivity, target, confidence, related_decisions, origin_run`) plus `conflicting_ref` (ADR-0004 sec.3 / INTEGRATION_PLAN sec.3.1a "citing the conflicting ref") and `authority_context_refs` so the transporter can populate the draft `authority_context_refs` field without recomputation.

### 1.2 `policy/authority.py` - the N-2 validator (the load-bearing module)

Responsibility: decide whether an `authority_context` is **trustworthy enough to base a conflict check on**. This is exactly the fence DR-5/N-2 says is missing. Pure function, no I/O.

```python
REQUIRED_FIELDS = (
    "vault", "domain_registry", "scope_decision",
    "knowledge_seam_decision", "coordination_decision", "checked_at",
)
PINNED_VAULT = "modelling-knowledge"

def validate_authority_context(
    ctx: AuthorityContext,
    *,
    current_index_digest: str,
) -> Result:
    """N-2 validator. Returns Result(ok=False, errors=[...]) on any completeness
    or currency failure; Result(ok=True) only when complete AND current."""
```

See sec.2 for the exact rule set. `current_index_digest` is **injected by the caller** - never read from the vault tool.

### 1.3 `policy/classification.py` - deterministic target decision

Responsibility: given a candidate and an already-validated authority context, decide the multi-axis `classification` label and the recommended `target`. Deterministic (INTEGRATION_PLAN sec.3.1a "runs deterministic classification"). No I/O.

```python
def classify_target(
    candidate: MemoryCandidate,      # partially-built (claim/provenance/sensitivity known; target unset)
    ctx: AuthorityContext,
) -> tuple[str, str, str | None]:
    """Return (classification_label, target, conflicting_ref).

    Rules (INTEGRATION_PLAN sec.3.1a L240-246, sec.3.2 L340-355):
      - conflicts with an accepted_refs note      -> ("conflict", "discard"|"flag", <ref>)
      - ephemeral / session-project scoped        -> ("ephemeral", "companion", None)
      - durable-candidate (survives-rewrite test  -> ("durable-candidate", "vault-inbox", None)
        AND no conflict in authority_context)
    """
```

Conflict detection is **only** against `ctx.accepted_refs` - never a vault read (AM-02). The from-scratch-rewrite eligibility test (decision 0005) is applied here as a predicate over candidate metadata supplied by the orchestrator; this plan does not re-derive 0005.

### 1.4 `candidate/classify.py` - the public entrypoint (the contract surface)

Responsibility: the single function the `modeller-agents` memory agent / `memory-maintain` skill calls. Composes the N-2 gate then classification. No I/O.

```python
def classify(
    candidate: MemoryCandidate,          # incoming, target unset / "unknown"
    authority_context: AuthorityContext,
    *,
    current_index_digest: str,
) -> MemoryCandidate:
    """The sec.3.1a propose seam entrypoint (INTEGRATION_PLAN sec.5 candidate side:
    classify(candidate, authority_context) -> MemoryCandidate).

    1. gate = validate_authority_context(authority_context,
                                         current_index_digest=current_index_digest)
       if not gate.ok: return candidate with target="flag",
           classification="authority-context-invalid", conflicting_ref=None,
           confidence lowered, and gate.errors surfaced via provenance/evidence.
    2. otherwise label, target, ref = classify_target(candidate, authority_context)
       return candidate with those fields set.

    Reads and writes NOTHING in the vault."""
```

Design point for N-2: an **incomplete or stale** `authority_context` must NOT let a candidate pass as `vault-inbox`. The gate forces `target="flag"` (never `vault-inbox`, never silent `discard`) so a broken fence surfaces to the board/agent rather than silently promoting or silently dropping. This directly answers DR-5 "memory can pass a candidate as no-conflict simply because its input was incomplete."

### 1.5 `schemas/memory-candidate.schema.json`

JSON Schema (draft 2020-12), `$id: "https://modeller-memory/schemas/memory-candidate.schema.json"`. Encodes ADR-0004 sec.2: required `candidate_id, classification, claim, provenance, sensitivity, target, confidence, related_decisions, origin_run`; `target` enum `["vault-inbox","companion","discard","flag"]`; `sensitivity` enum `["public","internal","restricted"]`; `confidence` number 0-1; optional `conflicting_ref`, `authority_context_refs`. This is the machine contract the tests validate the produced candidate against, and the doc `candidate-contract.md` narrates it (INTEGRATION_PLAN sec.5).

---

## 2. What the N-2 validator checks (general scope)

`validate_authority_context(ctx, *, current_index_digest)` mirrors the **completeness** pattern already proven in `modeller-agents/src/modeller/knowledge_packs.py` L342-353 and the **currency** pattern at L387-418, lifted to *conflict-check time*.

### 2.1 Completeness (the 6 fields, vault pinned) - mirrors knowledge_packs.py L342-353
- Each of the 6 required fields - `vault, domain_registry, scope_decision, knowledge_seam_decision, coordination_decision, checked_at` - must be a **non-empty string**. Missing/blank -> `Result(ok=False)` with `authority_context.<field> must be a non-empty string`.
- `vault` must equal the pinned literal `"modelling-knowledge"` (knowledge_packs.py L352-353). Any other value -> error `authority_context.vault must be 'modelling-knowledge'`.
- `accepted_refs` must be present as a list (may be empty - matching the discovery-draft schema `authority_context_refs: []` allowance). An empty list is allowed but recorded as a **warning** ("conflict check ran against zero accepted references"), because DR-5 concern is precisely a fence that "did not miss a relevant accepted note" - an empty ref set is legal but low-assurance and the board should see it.

### 2.2 Currency (which digest, compared to what, passed in how) - mirrors knowledge_packs.py L387-418
- **Which field:** `ctx.source_index_digest` - the vault-index digest the orchestrator pinned when it assembled the `authority_context` at capture time (baseline-flow step 5, before memory query at step 6). This is the conflict-check-time analogue of the pack `source_domain_notes_digest` (knowledge_packs.py L316, L409).
- **Compared to what:** the caller-supplied `current_index_digest` - the top-level `index_digest` of the current vault index export (`export.build_index(...)["index_digest"]`, export.py L149; committed as `modelling-knowledge/docs/dev/vault-index.json` -> `index_digest`, verified present). If `ctx.source_index_digest != current_index_digest` -> `Result(ok=False)` with `authority_context is stale: source_index_digest does not match current vault index digest` (the conflict-check-time analogue of knowledge_packs.py L409-413).
- **Passed in how (import-guard-safe):** `current_index_digest` is a **keyword-only string argument**. The orchestrator/agent obtains it from the committed `docs/dev/vault-index.json` artifact (the VA3 committed export, produced out-of-band by the vault own tooling) and passes the string in. The N-2 module never imports, names, or calls the vault export tool. This is the seam that keeps `test_import_guards.py` green while still giving a real currency check.
  - **Why whole-index digest, not per-domain here:** at conflict-check time the candidate has no single domain yet (it may be cross-domain or pre-domain), so the general fence pins to the whole-vault `index_digest`. (The pack-load path uses the narrower per-domain `notes_digest`, knowledge_packs.py L402-413, because a pack is domain-scoped; that narrowing is deliberately NOT copied here.)

### 2.3 Result contract
- **Complete AND current** -> `Result(ok=True, warnings=[...])`.
- **Any completeness failure OR stale digest** -> `Result(ok=False, errors=[...])`, which forces `classify()` to return `target="flag"` (never `vault-inbox`).

---

## 3. The end-to-end C1 path and the precise seam boundary

```
[modeller-agents orchestrator]                         PROPOSE (out of scope of this repo)
  captures idea/decision, retrieves accepted knowledge (baseline-flow step 5),
  pins current vault-index digest from modelling-knowledge/docs/dev/vault-index.json,
  builds AuthorityContext(..., source_index_digest=<pinned>) + a partial MemoryCandidate
        |
        v   calls modeller_memory.candidate.classify.classify(
        |        candidate, authority_context, current_index_digest=<pinned digest>)
+---------------------------------------------------------------------------------+
| modeller-memory  (THIS BUILD)                          CLASSIFY  (NO vault I/O)  |
|   1. policy.authority.validate_authority_context(...)  -> N-2 gate              |
|   2. policy.classification.classify_target(...)        -> target decision       |
|   3. returns MemoryCandidate(target="vault-inbox", ...) as a typed object       |
+---------------------------------------------------------------------------------+
        |   <-- SEAM BOUNDARY: modeller-memory STOPS here. It returns the object
        |       and does nothing else. The function return value IS the seam.
        v
[modeller-agents memory agent]                          TRANSPORT (out of scope)
  validates destination/sensitivity, invokes memory-maintain skill,
  WRITES modelling-knowledge/inbox/discovery-drafts/<candidate>.md
  mapping MemoryCandidate -> discovery-draft front matter:
     source: modeller-memory              (classifier = this subsystem)
     owner:  modeller-agents/memory-agent (writer = the agent)
     candidate_id, origin_run, authority_context_refs (from candidate),
     related_decisions, sensitivity, captured_from (from provenance), claim
        |
        v
[modelling-knowledge]                                   GOVERN (out of scope)
  vault_doctor inbox checks validate the draft (checks_inbox.py:
     DISCOVERY_DRAFT_REQUIRED_FIELDS + vocab + sensitivity fence + no authority inflation)
  -> antagonist board accepts / rejects
```

**Seam boundary, stated precisely:** modeller-memory responsibility ends at the `return MemoryCandidate(...)` statement of `candidate/classify.py`. The typed object crossing that `return` is the entire producer-side deliverable. Everything after - destination validation, the inbox write, the front-matter mapping, and acceptance - belongs to `modeller-agents` (transport) and `modelling-knowledge` (govern). The mapping table above is documented in `candidate-contract.md` as guidance for the transporter but is **not implemented** in this repo.

**C1 proof shape:** the C1 test (see sec.4) constructs one realistic `MemoryCandidate` input, runs the real `classify()`, asserts `target == "vault-inbox"`, then renders the ADR-0004 -> discovery-draft field mapping into an in-memory/fixture draft and asserts it satisfies the `checks_inbox.py` blocking-check field set (`DISCOVERY_DRAFT_REQUIRED_FIELDS`, vocab literals, no forbidden authority fields). That demonstrates a real subsystem output flows end-to-end into an inbox-valid draft - the "H.4 used a memory-agent-shaped draft, not a live subsystem output" gap 0007 C1 calls out. The actual on-disk write and board acceptance remain the agent/board job.

---

## 4. Test plan

New tests under `modeller-memory/tests/candidate/` and `modeller-memory/tests/policy/`. None imports `tools/`; the digest is a **literal fixture constant**, keeping `test_import_guards.py` green.

### 4.1 N-2 proof - `tests/policy/test_authority.py`
- `test_rejects_incomplete_authority_context` - for each of the 6 required fields, drop/blank it -> assert `Result.ok is False` and the field name appears in `errors`.
- `test_rejects_wrong_vault_pin` - `vault="something-else"` -> `ok is False`, error names the pin rule.
- `test_rejects_stale_digest` - `ctx.source_index_digest="sha256:OLD"`, `current_index_digest="sha256:NEW"` -> `ok is False`, error mentions stale/digest mismatch.
- `test_accepts_complete_and_current` - all 6 fields present, vault pinned, `source_index_digest == current_index_digest` -> `ok is True`.
- `test_empty_accepted_refs_warns_but_passes` - legal-but-low-assurance path produces a warning, still `ok is True`.

### 4.2 N-2 at the entrypoint - `tests/candidate/test_classify_authority_gate.py`
- `test_invalid_authority_context_flags_never_inbox` - a durable-looking candidate + incomplete/stale context -> returned `MemoryCandidate.target == "flag"` (proves an invalid fence can never yield `vault-inbox`; the core DR-5 guarantee).

### 4.3 Classification - `tests/candidate/test_classification.py`
- `test_conflict_recommends_discard_or_flag_with_ref` - candidate contradicting an `accepted_refs` entry -> `target in {"discard","flag"}`, `conflicting_ref` set.
- `test_ephemeral_recommends_companion`.
- `test_durable_no_conflict_recommends_vault_inbox`.

### 4.4 C1 proof - `tests/candidate/test_c1_end_to_end.py`
- `test_one_real_candidate_reaches_inbox_valid_draft`:
  1. build one realistic input candidate + complete/current `AuthorityContext`;
  2. call the real `classify(...)` -> assert `target == "vault-inbox"`;
  3. validate the produced candidate against `schemas/memory-candidate.schema.json`;
  4. map to discovery-draft front matter and assert it carries every required draft field, `status == "draft"`, `type == "discovery-draft"`, `source == "modeller-memory"`, and NO forbidden authority field.

> Import-guard note: `test_import_guards.py` only scans `src/modeller_memory/` (not `tests/`). To avoid coupling C1 to the tool, the C1 test **re-declares the required-field tuple as a local fixture** mirroring `discovery-draft-schema.md` sec.2 / `checks_inbox.py` L57-70, and pins the standard as source of truth via a comment. This keeps the proof anchored to the *published standard*, not the tool implementation, and never imports the tool from a src module.

### 4.5 Keeping `test_import_guards.py` green
- No file under `src/modeller_memory/policy/` or `src/modeller_memory/candidate/` contains the substring the guard scans for. Digest input is a plain string arg; the currency comparison is string equality.
- Add `tests/candidate/__init__.py` and `tests/policy/__init__.py` as needed; no change to `conftest.py` (its `src/` path insertion already covers the new packages).

---

## 5. Risk / sequencing

### 5.1 What must land first (ordering)
1. **`candidate/model.py`** (types) - everything depends on it.
2. **`schemas/memory-candidate.schema.json`** + **`docs/contracts/candidate-contract.md`** - the machine + prose contract; land with the model so tests can validate.
3. **`policy/authority.py`** (N-2 validator) + its unit tests (sec.4.1) - highest-value, self-contained; reviewable in isolation.
4. **`policy/classification.py`** + **`candidate/classify.py`** + tests (sec.4.2-4.4).
5. Run the full `tests/` suite; confirm `test_import_guards.py` and the 24 vault-tool tests still pass unchanged.

### 5.2 What stays open (explicitly NOT in this build)
- **Transport + inbox write** - owned by `modeller-agents` (memory agent + `memory-maintain` skill). C1 *on-disk* write and board acceptance are proven there, not here.
- **Companion recall / mempalace (M5-M7)** - flag-off; "capture now, promote later" (0007 L77). Not touched.
- **Metadata-only vault read for conflict pre-checks** - ADR-0004 sec.3 "future optimisation"; explicitly out of v1.
- **N-1 recurring** (synthetic supersession/move/stale fixtures) - vault-side, separate need.

### 5.3 Doc flips in `modelling-knowledge` that become valid ONLY AFTER this runtime lands (and C1 is exercised)
This plan does not make these; it records the precondition:
- **`modelling-knowledge/docs/dev/vault-alignment-plan.md`** - N-2 wording (L698-704, L725-735): flip "MET for the VA5 accessibility pilot scope ... still open for the general VA8 gate" to N-2 satisfied at general scope, citing this runtime + its `validate_authority_context` currency-against-`index_digest` check. Valid only after sec.4.1/sec.4.2 tests are green in CI.
- **`modelling-knowledge/decisions/0007-memory-promotion-coordination.md`** - the Promotion Gate (L27-36): flip **C1** to met once sec.4.4 exercises a real `MemoryCandidate` end-to-end into an inbox-valid draft, and **C2** to met once N-2 general scope is recorded (sec.4.1). When **both** C1 and C2 are met, `content_promotion: BLOCKED` may move to unblocked. Neither flip is valid before this runtime exists.
- **`modelling-knowledge/decisions/0007` Follow-Up item 1** - mark exercised, referencing the C1 test.

### 5.4 Residual risks
- **Required-field drift.** The discovery-draft required set is defined in three places (`discovery-draft-schema.md` sec.2, `checks_inbox.py` L57-70, and the C1 test fixture). Mitigation: the C1 test comment pins the standard as source of truth; a future shared fixture (like N-1 `eligibility-conformance.json`) could unify them, out of scope here.
- **Digest source trust.** Currency is only as good as the pinned `index_digest` the orchestrator supplies. This plan validates *parity*, not *freshness of the committed artifact vs vault HEAD* - that remains a cross-repo Close-phase rule (INTEGRATION_PLAN L42-52). Documented, not silently assumed.
- **Naming ratification.** `candidate/` vs `candidates/` and `classification.py` placement must be fixed before merge to keep schema `$id`, contract doc, and imports consistent (sec.1 note).
