# Modeller Pipelines Contract Surface, Product Requirements Document

**Nature:** initial product specification, translating the tagging-and-registry-skew MVP into testable obligations
**Status:** Draft, to be validated by modeller-pipelines maintainers, aimsun-psp maintainers, and modeller-agents registry maintainers
**Version:** 0.1, 25 July 2026
**Upstream documents:** docs/vision/Business-need-design-brief.md
**Consistency matrix:** None exists for this doc set

---

## 1. Purpose and scope

This document translates the Modeller Pipelines Contract Surface Business Need and Design Brief into testable requirements. It forms the basis for the tag-cutting, vendor-subtree population, and registry-correction work the brief scopes as this repository's MVP, and for the optional CI conformance check named as a stretch item.

It does not replace:

- the business-need / design brief, which explains the why and the journeys;
- the detailed architecture decisions (ADR-0001, ADR-0002, and any future ADR governing contract-shape changes);
- the interface specifications (`contracts/PIPELINE_DEFINITION.md`, `STEP_INTERFACE.md`, `CLI_SEAM.md`, `RESULT_CONTRACT.md`);
- the API contracts (`contracts/schemas/*.json`);
- the conformance kit's own technical test plan;
- modeller-agents' and aimsun-psp's own repository governance.

---

## 2. Traceability to upstream documents

| Upstream document | Relevant sections | What this PRD obligates |
|---|---|---|
| Business-need-design-brief.md | §2 (business problem and risks), §3 (product boundaries) | The four core gaps (unfetchable tags, live registry skew, unusable offline verification, no mechanical drift check) become BR/DATA/OBS obligations |
| Business-need-design-brief.md | §4 (users), §5 (MVP journeys) | The three maintainer journeys (backend implementer, registry maintainer, modeller-pipelines maintainer) become FR and HITL obligations |
| Business-need-design-brief.md | §6, §7 (contract-version organization), §10 (evidence and review) | Contract-version identity, tag-to-commit integrity, and bit-for-bit vendor verification become DATA and OBS obligations |
| Business-need-design-brief.md | §11 (cross-cutting MVP capabilities), §12 (parking lot) | Scope boundaries become explicit exclusions (§18) and inform Maturity fields throughout |
| Business-need-design-brief.md | §17 (priority open questions OPN-001..OPN-005) | Requirements whose upstream decision is not yet made trace to §19 Blocking Open Decisions instead of a settled section |

Every requirement below carries a **Source** field pointing back to one of these sections, or to an explicitly logged open question (see §19) when the upstream decision is not yet made.

---

## 3. Normative language

This document uses RFC 2119-style keywords. Each requirement statement uses **exactly one** keyword class to express its obligation:

- **MUST**: obligation required for acceptance of the scope concerned.
- **MUST NOT**: explicitly forbidden behavior.
- **SHOULD**: important requirement; deviation allowed only by documented decision.
- **MAY**: optional or progressive capability.

### Priority

| Priority | Interpretation |
|---|---|
| **P0** | Required to close the three named gaps (unfetchable tags, registry skew, unusable offline verification) that this MVP exists to close |
| **P1** | Important for the MVP to be trustworthy end to end, including the CI stretch item |
| **P2** | Improvement that can be deferred beyond this MVP |

### Status-ladder discipline

- **CURRENT**: the requirement targets a capability that exists in the codebase or design today, but is not yet proven in production use.
- **OPERATIONAL**: the requirement targets a capability already proven in real use; only use this word when there is evidence, not aspiration.
- **EMERGING**: the requirement targets a capability under active but incomplete construction; the requirement text names the gap that keeps it from being CURRENT.
- **TARGET**: the requirement targets a capability planned but not yet started; the requirement text says so (for example, "once the tags are cut, the registry MUST...").
- **PROPOSED**: the requirement targets a capability that is only a candidate direction, not yet committed; treated with the same caution as an open decision (see §19).

Per the brief's own honest framing (§2.1: "solid content, unproven distribution"), most requirements in this PRD are Target or Emerging, not Operational: the tagging mechanism, the vendor subtree, and the registry correction do not exist yet in a working state. Contract *content* (schemas, normative prose, the template pipeline) is Current. No requirement in this document claims Operational status for a capability this brief exists specifically because it is not yet working.

---

## 4. Definitions and actors

| Term | Definition |
|---|---|
| Contract version | One immutable, tagged snapshot of `contracts/` (VERSION file, schemas, normative prose) that a backend can conform to and a registry can pin against. |
| Git tag | The fetchable, immutable pointer to the commit a `contract_version` string corresponds to. Annotated tags `contract-v1.0` and `contract-v1.1` are named throughout this repo's documents but do not yet exist. |
| Backend | A pipeline/dock implementation (concretely aimsun-psp today) that declares conformance to a contract version via its own `backend.json` and `contract.lock`. |
| Vendor subtree | A read-only, pinned, squashed copy of `contracts/` and `conformance/` inside `modeller-agents/vendor/modeller-pipelines/`, letting modeller-agents verify a backend's conformance offline. |
| Registry expectation | modeller-agents' own record (`backends.toml`'s `expected_contract` and `status` fields) of what contract version it expects a given backend to conform to. |
| Conformance kit | The black-box tool under `conformance/` that checks a backend's manifests and results against the schemas and exits 0 (pass) or non-zero (fail), with no silent pass on an unsupported version. |

| Actor | Description |
|---|---|
| Backend implementer | Conforms an existing or new pipeline system to the contract; concretely, aimsun-psp maintainers today. |
| modeller-agents registry maintainer | Owns `backends.toml`, `vendors.toml`, and `reference-packs/modeller-pipelines.toml`; keeps `expected_contract` and `status` current against a backend's actual declaration. |
| modeller-pipelines maintainer | Cuts tags, owns the ADR sequence and `contracts/VERSION`, and (if pursued) the CI workflow. |

---

## 5. Requirement entry format

Every requirement in every family below follows this exact skeleton: an `### ID - Title` heading, then a Statement using exactly one RFC-2119 keyword, a Rationale, a Source pointing to an upstream section or open question, a Priority, Dependencies, a Maturity (naming the blocking dependency if not Operational), a list of observable acceptance criteria, a validation method, related risks, related architecture, related plan items, and a status line. Fields are never omitted; a field that genuinely does not apply is written as "None" rather than deleted, so the Definition of Ready and Definition of Done checks in §16-§17 stay mechanical. IDs are numbered sequentially within each family and are never renumbered across families.

---

## 6. Business requirements (BR)

Product-level obligations that follow directly from the business need: what the tagging-and-registry mechanism must be organized around, and what continuity or traceability it must preserve for anyone who depends on it.

### BR-001 - Tags are the sole trust anchor for a contract version

**Statement:** modeller-pipelines MUST make every reference to `contract-v1.0` and `contract-v1.1` in `CONTRACT_VERSIONS.md`, `CHANGELOG.md`, `ADR-0002`, and downstream configs resolve to a real, annotated git tag on the correct commit.
**Rationale:** every document in this repo already assumes the tags exist; the gap between documented mechanism and actual repository state is the fundamental problem this MVP exists to close (brief §2.2).
**Source:** Business-need-design-brief.md §2.1, §2.2, §3.
**Priority:** P0
**Dependencies:** None
**Maturity:** Target. Blocking dependency: no tag exists yet (`git tag -l` returns nothing); cutting the tags is this MVP's first deliverable.

**Acceptance criteria:**
- `git tag -l` includes both `contract-v1.0` and `contract-v1.1`.
- Each tag's target commit's `contracts/VERSION` content matches the tag name's version.
- `CONTRACT_VERSIONS.md` and `CHANGELOG.md` entries for each version name the tag that now actually resolves.

**Validation method:** `git fetch` against each named tag from a clean clone; diff `contracts/VERSION` at the tag against the tag name.
**Related risks:** Unfetchable references (brief §2.2 risk 1).
**Related architecture:** ADR-0002 (single `contract_version` field discipline).
**Related plan items:** Brief §15 deliverable 1 (two annotated tags).
**Status:** Draft, to be validated

### BR-002 - modeller-pipelines never becomes a runtime dependency

**Statement:** modeller-pipelines MUST NOT introduce any code, tag, or configuration change in this MVP that a backend imports or executes at runtime.
**Rationale:** ADR-0001 (scaffold-not-framework) is the repo's founding boundary; the tagging and registry-correction work is a governance fix, not an opportunity to quietly add a runtime coupling.
**Source:** Business-need-design-brief.md §3 ("must not... become a shared runtime library").
**Priority:** P0
**Dependencies:** None
**Maturity:** Current. This is an existing, honored invariant (`template/runner/minirunner.py` is copied, never imported, per `reference-packs/modeller-pipelines.toml`'s `minirunner_max_lines=200`); this requirement obligates that the MVP not regress it.

**Acceptance criteria:**
- No tag, CI workflow, or registry correction in this MVP adds an import path from any backend into `modeller-pipelines`.
- `template/runner/minirunner.py` remains at or under 200 lines after this MVP lands.
- No new `package.json`/`pyproject.toml`/equivalent dependency declaration names `modeller-pipelines` as an installable runtime package.

**Validation method:** Static review of the MVP's diff against ADR-0001's stated boundary; line-count check on `minirunner.py`.
**Related risks:** None additional beyond the founding architectural risk ADR-0001 already closes.
**Related architecture:** ADR-0001.
**Related plan items:** None specific; a standing constraint on every deliverable in §15 of the brief.
**Status:** Draft, to be validated

### BR-003 - Contract-shape changes stay outside this MVP

**Statement:** modeller-pipelines MUST NOT bundle any new schema content, new normative document, or new contract minor or major version into the tag-cutting and registry-correction work.
**Rationale:** the brief is explicit that the opportunity here is narrow: making an existing, already-documented mechanism work, not adding scope (brief §2.3, §3).
**Source:** Business-need-design-brief.md §2.3, §3, §16 ("confirmation that no schema or normative-prose change is bundled into this MVP").
**Priority:** P0
**Dependencies:** BR-001
**Maturity:** Current. This is a scope boundary to hold, not a capability to build.

**Acceptance criteria:**
- The commits the `contract-v1.0` and `contract-v1.1` tags point to are pre-existing commits, not new commits created to accompany the tag.
- No pull request in this MVP touches `contracts/schemas/*.json` or the normative `.md` files under `contracts/` for content reasons (only `contracts/VERSION` and `README.md`'s banner, per BR-004, are in scope).
**Validation method:** Diff review of every PR in this MVP against `contracts/schemas/` and normative-prose paths.
**Related risks:** None additional.
**Related architecture:** ADR-0002.
**Related plan items:** Brief §16 "Product and business" input item.
**Status:** Draft, to be validated

### BR-004 - Version banners stay internally consistent

**Statement:** modeller-pipelines MUST keep `README.md`'s version banner equal to `contracts/VERSION`'s content at all times after this MVP lands.
**Rationale:** a reader trusting the README's stated version while `contracts/VERSION` disagrees is exactly the kind of small, undetected drift this MVP exists to eliminate (brief §2.1, §2.2 risk 4).
**Source:** Business-need-design-brief.md §2.1, §2.2, §15 deliverable 2.
**Priority:** P1
**Dependencies:** None
**Maturity:** Target. Blocking dependency: as of this PRD, `README.md` reads `contract-v1.0` while `contracts/VERSION` reads `1.1` (confirmed live mismatch).

**Acceptance criteria:**
- `README.md`'s header version string equals the content of `contracts/VERSION`.
- The correction lands as its own reviewable change, not bundled silently into a tag-cutting commit.

**Validation method:** String comparison of the README banner against `contracts/VERSION` in CI or by manual check before each release.
**Related risks:** Minor doc drift (research finding 5).
**Related architecture:** None.
**Related plan items:** Brief §15 deliverable 2.
**Status:** Draft, to be validated

---

## 7. Functional requirements (FR)

User-facing (here: maintainer-facing) capabilities, each mapped to a step of one of the three MVP journeys named in the business-need brief §5.

### FR-001 - Backend implementer can fetch a pinned contract version

**Statement:** A backend implementer MUST be able to fetch the schemas and normative prose for a named `contract_version` (for example `contract-v1.1`) from its cut tag, rather than reading an unpinned working-tree copy.
**Rationale:** this is step 2 of the backend implementer's journey (brief §5.1) and the first mechanical promise the whole contract design depends on.
**Source:** Business-need-design-brief.md §5.1 steps 1-2, §13 (success measure: "whether `git fetch` against the named tag succeeds").
**Priority:** P0
**Dependencies:** BR-001
**Maturity:** Target. Blocking dependency: BR-001 (the tags do not exist yet).

**Acceptance criteria:**
- `git fetch origin contract-v1.1` (or an equivalent clone-and-checkout) succeeds from a clean environment.
- The fetched content's `contracts/VERSION` reads `1.1` and matches the tag name.
- `docs/HOW_TO_CONFORM.md`'s instructions for this step, once followed literally, succeed without manual correction.

**Validation method:** End-to-end fetch test from a clean clone, following `HOW_TO_CONFORM.md` verbatim.
**Related risks:** Unfetchable references (brief §2.2 risk 1).
**Related architecture:** None.
**Related plan items:** Brief §15 deliverable 1.
**Status:** Draft, to be validated

### FR-002 - Conformance kit gives a loud, actionable result

**Statement:** The conformance kit MUST report a pass or fail result against a backend's `backend.json`, `contract.lock`, manifests, and results, and MUST refuse to run silently against a `contract_version` older than the documented N-1 support floor.
**Rationale:** this is step 5-6 of the backend implementer's journey (brief §5.1) and a standing prohibition already stated in `CONTRACT_VERSIONS.md` against silent degradation.
**Source:** Business-need-design-brief.md §5.1 steps 5-6, §10 ("the kit's own loud, actionable error message on an unsupported version").
**Priority:** P0
**Dependencies:** None
**Maturity:** Current. The kit's exit-code and JSON-report mechanism already exists; this requirement obligates that this MVP not weaken it, and confirms it is sufficient as a CI gate (brief §16 Technology).

**Acceptance criteria:**
- A conforming backend's run exits 0 with a report confirming conformance.
- A non-conforming backend's run exits non-zero with a report naming the specific schema or prose rule violated.
- A backend declaring a `contract_version` older than the supported floor produces an explicit, named error, never a silent pass.

**Validation method:** Run the conformance kit against aimsun-psp's real manifests (pass case) and a deliberately malformed manifest (fail case); run it against a pre-floor version string (rejection case).
**Related risks:** No mechanical check against drift (brief §2.2 risk 4).
**Related architecture:** `conformance/` kit.
**Related plan items:** None specific; a precondition for FR-003.
**Status:** Draft, to be validated

### FR-003 - CI runs the conformance kit against the template on every change (stretch)

**Statement:** modeller-pipelines MAY add a CI workflow that runs the conformance kit against `template/` on every change to `contracts/` or `template/`.
**Rationale:** named as a "reasonable stretch item" in the brief precisely because no `.github/` directory exists yet and it is not required to close the three core gaps.
**Source:** Business-need-design-brief.md §2.3, §3, §15 deliverable 5, §17 OPN-003.
**Priority:** P1
**Dependencies:** FR-002
**Maturity:** Proposed. Blocking dependency: OPN-003 (whether this is in scope for this MVP or a follow-on step) is an open question the brief itself flags as unresolved; no `.github/` directory exists in this repo today.

**Acceptance criteria:**
- If pursued, a `.github/workflows/` file exists that invokes the conformance kit against `template/` on every push or pull request touching `contracts/` or `template/`.
- The workflow's most recent run status (pass/fail) is visible on the pull request that triggered it.
- A failing run blocks merge or is clearly flagged, per the maintainers' branch-protection choice.

**Validation method:** Trigger a deliberate template/schema mismatch on a branch and confirm the workflow fails visibly; confirm a clean template passes.
**Related risks:** No mechanical check against drift (brief §2.2 risk 4).
**Related architecture:** `conformance/` kit, new `.github/workflows/`.
**Related plan items:** Brief §15 deliverable 5.
**Status:** Draft, to be validated

---

## 8. Integration requirements (INT)

Cross-repository integration: how modeller-agents' registry and vendor subtree stay aligned with what a backend actually declares. There is no AI orchestration surface in this repo (brief §9); this family covers the registry/vendor-subtree boundary instead.

### INT-001 - Vendor subtree mirrors the pinned tag bit-for-bit

**Statement:** modeller-agents' `modeller-agents/vendor/modeller-pipelines/` subtree MUST be populated from the `contract-v1.1` tag via a read-only, squashed `git subtree` pull, and MUST match that tag's content bit-for-bit.
**Rationale:** this is the one mechanism designed to let modeller-agents verify a backend's conformance offline, without a live fetch or a read of the backend's own source; it is currently an empty directory (brief §2.2 risk 3).
**Source:** Business-need-design-brief.md §2.2 risk 3, §3, §5.2 steps 2 and 4, §7 ("vendor subtree" core relationship).
**Priority:** P0
**Dependencies:** BR-001 (the tag must exist before it can be pulled)
**Maturity:** Target. Blocking dependency: BR-001, and the subtree directory itself is confirmed empty today (research finding 3).

**Acceptance criteria:**
- `modeller-agents/vendor/modeller-pipelines/` contains `contracts/` and `conformance/` content after the pull.
- A file-by-file, byte-for-byte comparison between the vendored subtree and the `contract-v1.1` tag's tree shows no difference.
- `vendors.toml`'s existing `squash = true`, `writable = false` declaration is honored by the actual pull invocation used.

**Validation method:** Bit-for-bit diff between the vendored subtree and a fresh checkout of the `contract-v1.1` tag.
**Related risks:** Unusable offline verification (brief §2.2 risk 3).
**Related architecture:** `modeller-agents/vendor/modeller-pipelines/`, `vendors.toml`.
**Related plan items:** Brief §15 deliverable 3.
**Status:** Draft, to be validated

### INT-002 - Registry expectation reconciled with backend declaration

**Statement:** The modeller-pipelines maintainer and the modeller-agents maintainer MUST jointly resolve the skew between aimsun-psp's declared `contract.lock` version (`1.1`) and modeller-agents' `backends.toml` expectation (`1.0`, `status = "planned"`), before `backends.toml` marks aimsun-psp `active`. This repo MUST NOT unilaterally assert which side moves: raising `backends.toml`'s `expected_contract` to `1.1`, or aimsun-psp lowering its own declaration to `1.0`, are both live options until the two maintainers agree.
**Rationale:** this is the live, currently measurable skew the brief names as its second core risk: aimsun-psp declares `contract-v1.1` in its own `backend.json` and `contract.lock`, while the registry still expects `1.0` and treats the backend as merely planned. aimsun-psp's own PRD (INT-002) frames this identically as a joint, currently-open decision, not a unilateral correction; this requirement is written to agree with that framing rather than presume an outcome modeller-pipelines does not have sole authority to set.
**Source:** Business-need-design-brief.md §2.2 risk 2, §3, §5.2 step 3, §13 (success measure).
**Priority:** P0
**Dependencies:** INT-001 (the corrected `ref` in `reference-packs/modeller-pipelines.toml` and `vendors.toml` should land alongside whichever resolution is agreed)
**Maturity:** Target. Blocking dependency: OPN-004 (which side moves, what the corrected `status` value should be, and whether modeller-agents has a defined status vocabulary) is an open question the two maintainers must resolve first.

**Acceptance criteria:**
- `backends.toml`'s `expected_contract` for aimsun-psp and aimsun-psp's own `contract.lock` value agree, whichever side moved to reach that agreement.
- The agreed resolution direction is recorded with sign-off from both the modeller-pipelines and modeller-agents maintainers (see NFR-002, "Registry correction requires prior agreement, not unilateral edit").
- `backends.toml`'s `status` field for aimsun-psp no longer reads `"planned"` and instead reflects a value from an agreed vocabulary (see OPN-004).
- `vendors.toml` and `reference-packs/modeller-pipelines.toml` pin `ref` to whichever contract version the two sides agreed on.

**Validation method:** Direct comparison of `backends.toml`'s `expected_contract` against aimsun-psp's `contract.lock` value after the correction lands, plus review-trail inspection confirming both maintainers signed off on the resolution direction.
**Related risks:** Live registry skew (brief §2.2 risk 2); cross-repo authority confusion if one side asserts the outcome unilaterally.
**Related architecture:** `modeller-agents/backends.toml`, `vendors.toml`, `reference-packs/modeller-pipelines.toml`; aimsun-psp's `backend.json`, `contract.lock`.
**Related plan items:** Brief §15 deliverable 4.
**Status:** Draft, to be validated

---

## 9. Data requirements (DATA)

Identity and provenance of a contract version: what makes a version citable, immutable, and traceable to the maintainer who approved it.

### DATA-001 - `contract_version` is the sole versioning field

**Statement:** Every backend's `contract.lock` and `backend.json` MUST declare conformance using exactly one `contract_version` field, with no per-schema version sprawl.
**Rationale:** ADR-0002's founding discipline; this MVP's tag and registry corrections must not introduce a second, competing versioning mechanism.
**Source:** Business-need-design-brief.md §7 ("contract_version: the single field, per ADR-0002...").
**Priority:** P0
**Dependencies:** None
**Maturity:** Current. This is an existing, honored invariant; this requirement obligates that the MVP not regress it while correcting registry fields.

**Acceptance criteria:**
- aimsun-psp's `backend.json` and `contract.lock` each carry exactly one `contract_version` field.
- No schema under `contracts/schemas/` is individually versioned outside the single `contract_version` string.

**Validation method:** Schema and config inspection against ADR-0002.
**Related risks:** None additional.
**Related architecture:** ADR-0002.
**Related plan items:** None specific.
**Status:** Draft, to be validated

### DATA-002 - A contract version is immutable once tagged

**Statement:** Once `contract-v1.0` or `contract-v1.1` is cut as an annotated tag, modeller-pipelines MUST NOT move, delete, or force-update that tag to point at a different commit.
**Rationale:** the brief treats a tag as the trust anchor the whole distribution design depends on (brief §17 OPN-002); an immutable tag is the only way a downstream consumer's pin stays meaningful over time.
**Source:** Business-need-design-brief.md §8 step 3 ("since a tag is meant to be immutable once published"), §17 OPN-002.
**Priority:** P0
**Dependencies:** BR-001
**Maturity:** Target. Blocking dependency: BR-001; the immutability obligation cannot be tested until the first tag is cut and its permanence is exercised over time.

**Acceptance criteria:**
- No `git tag -f` or force-push of `contract-v1.0`/`contract-v1.1` occurs after initial publication.
- A downstream consumer that pinned `contract-v1.1` at time T continues to resolve to the same commit at any later time.

**Validation method:** Periodic re-verification that the tag's target commit hash is unchanged; a repository rule or documented convention prohibiting tag force-updates.
**Related risks:** None additional beyond trust-anchor integrity.
**Related architecture:** None.
**Related plan items:** Brief §15 deliverable 1.
**Status:** Draft, to be validated

### DATA-003 - Every version entry names a real, fetchable tag

**Statement:** `CONTRACT_VERSIONS.md` and `CHANGELOG.md` MUST name a git tag for every version entry, and that tag MUST resolve to a commit whose `contracts/VERSION` content matches the entry.
**Rationale:** direct re-statement of the brief's own consolidated need (§18): "every contract version must remain linked to a real, fetchable tag."
**Source:** Business-need-design-brief.md §10, §18.
**Priority:** P0
**Dependencies:** BR-001
**Maturity:** Target. Blocking dependency: BR-001.

**Acceptance criteria:**
- Each row in `CONTRACT_VERSIONS.md` and each entry in `CHANGELOG.md` names a tag that `git tag -l` confirms exists.
- The tag's target commit's `contracts/VERSION` matches the version the entry describes.

**Validation method:** Cross-check every `CONTRACT_VERSIONS.md`/`CHANGELOG.md` entry against `git tag -l` and the tagged commit's `contracts/VERSION`.
**Related risks:** Unfetchable references (brief §2.2 risk 1).
**Related architecture:** `CONTRACT_VERSIONS.md`, `CHANGELOG.md`.
**Related plan items:** Brief §15 deliverable 1.
**Status:** Draft, to be validated

---

## 10. Security requirements (SEC)

The MVP's security surface is narrow: this repo has no runtime, no authentication boundary, and no user-facing data plane. The one applicable concern is write-boundary discipline on the vendored, read-only subtree, and the trust question of tag signing.

### SEC-001 - Vendor subtree stays read-only from modeller-agents' side

**Statement:** modeller-agents MUST NOT write back into `modeller-pipelines` through the vendored subtree; the subtree pull MUST remain one-directional and read-only, per `vendors.toml`'s own `writable = false` declaration.
**Rationale:** a write-back path would silently turn a governance mirror into a second, uncontrolled source of contract-shape change, defeating the ADR process this repo relies on for any real contract edit.
**Source:** Business-need-design-brief.md §7 ("vendor subtree: a read-only, pinned, squashed copy..."), Testable-boundaries research finding ("modeller-agents vendors this repo read-only via git subtree... it must never write back").
**Priority:** P0
**Dependencies:** INT-001
**Maturity:** Current. `vendors.toml` already declares `writable = false`; this requirement obligates that the population work in this MVP not violate that declaration in practice.

**Acceptance criteria:**
- No commit originating in `modeller-agents/vendor/modeller-pipelines/` is ever merged back into `modeller-pipelines`'s own history.
- `vendors.toml`'s `writable` field for this vendor entry remains `false` after this MVP lands.

**Validation method:** Repository history review confirming no subtree-push operation has ever targeted `modeller-pipelines` from the vendor copy.
**Related risks:** None additional.
**Related architecture:** `modeller-agents/vendor/modeller-pipelines/`, `vendors.toml`.
**Related plan items:** Brief §15 deliverable 3.
**Status:** Draft, to be validated

### SEC-002 - Tag signing decision is explicit, not silently defaulted

**Statement:** modeller-pipelines maintainers MUST explicitly decide, and record, whether `contract-v1.0` and `contract-v1.1` are cut as signed annotated tags before publishing them, given tags are this design's trust anchor.
**Rationale:** the brief flags this as a genuinely open question (OPN-002) with direct impact on the level of assurance a downstream consumer gets; defaulting silently to unsigned tags without a recorded decision would understate the risk.
**Source:** Business-need-design-brief.md §16 (Technology: "whether the annotated tags should be signed"), §17 OPN-002.
**Priority:** P1
**Dependencies:** BR-001
**Maturity:** Proposed. Blocking dependency: OPN-002 is unresolved; this requirement obligates a recorded decision, not a specific signing outcome.

**Acceptance criteria:**
- A recorded decision (for example, an ADR or a note in `CONTRACT_VERSIONS.md`) states whether the tags are signed and why.
- If signed, the signing key and verification instructions are documented alongside the tag.

**Validation method:** Review of the decision record before the tags are cut.
**Related risks:** Trust-anchor assurance level (OPN-002).
**Related architecture:** None.
**Related plan items:** Brief §17 OPN-002, owner: modeller-pipelines maintainer.
**Status:** Draft, to be validated

---

## 11. Non-functional requirements (NFR)

### NFR-001 - No silent degradation on an unsupported contract version

**Statement:** The conformance kit MUST fail loudly, with an actionable message naming the detected and minimum supported contract versions, rather than passing silently or degrading gracefully when a backend declares a `contract_version` below the supported floor.
**Rationale:** `CONTRACT_VERSIONS.md` already prohibits silent degradation explicitly; this MVP must not weaken that guarantee while correcting the registry around it.
**Source:** Business-need-design-brief.md §10 ("distinguish a passing conformance-kit run from a failing one, with the kit's own loud, actionable error message"), §11 (cross-cutting capability: "understandable conformance-kit error messages naming the detected and minimum supported versions").
**Priority:** P0
**Dependencies:** FR-002
**Maturity:** Current. The prohibition is already documented policy; this requirement obligates it stays honored as the registry and tags around it change.

**Acceptance criteria:**
- Running the conformance kit against a `contract_version` string older than N-1 produces a non-zero exit and a message naming both the detected version and the minimum supported version.
- No configuration path causes the kit to exit 0 on an unsupported version.

**Validation method:** Run the kit against a deliberately pre-floor `contract_version` string and confirm the failure message's content.
**Related risks:** No mechanical check against drift (brief §2.2 risk 4).
**Related architecture:** `conformance/` kit.
**Related plan items:** None specific.
**Status:** Draft, to be validated

### NFR-002 - Registry correction requires prior agreement, not unilateral edit

**Statement:** A modeller-pipelines maintainer proposing a `backends.toml` correction SHOULD obtain explicit agreement from a modeller-agents maintainer on the resolution direction and the resulting `expected_contract` and `status` values before those files are edited, rather than editing another repository's registry unilaterally.
**Rationale:** `backends.toml`, `vendors.toml`, and `reference-packs/modeller-pipelines.toml` are owned by modeller-agents, not modeller-pipelines; the brief is explicit that agreement precedes the edit (brief §16 Product and business). This also holds for the resolution direction itself (INT-002): neither repo may presume which side moves without the other's sign-off.
**Source:** Business-need-design-brief.md §16 ("agreement from modeller-agents maintainers on the corrected expected_contract and status values before those files are edited").
**Priority:** P1
**Dependencies:** INT-002
**Maturity:** Target. Blocking dependency: OPN-004 (the correct post-`"planned"` status value) must be resolved as part of reaching that agreement.

**Acceptance criteria:**
- The pull request correcting `backends.toml` carries an explicit sign-off or review approval from a modeller-agents maintainer before merge.
- No modeller-pipelines-originated commit merges directly into modeller-agents' registry files without that review.

**Validation method:** Pull request review-trail inspection.
**Related risks:** Live registry skew (brief §2.2 risk 2), cross-repo authority confusion.
**Related architecture:** `modeller-agents/backends.toml`.
**Related plan items:** Brief §15 deliverable 4.
**Status:** Draft, to be validated

### NFR-003 - Each correction is independently reviewable

**Statement:** The tag-cutting, vendor-subtree population, and registry-field corrections SHOULD each land as separate, independently reviewable pull requests, rather than a single combined change.
**Rationale:** the brief names this discipline explicitly in both the vision (§6.6) and the MVP journeys (§5.3), and it keeps each maintainer's review scoped to what they actually have authority over (Section 4's responsibility matrix).
**Source:** Business-need-design-brief.md §6.6 ("each independently reviewable, as separate, small pull requests"), §15 deliverable 4 ("each independently reviewable").
**Priority:** P1
**Dependencies:** None
**Maturity:** Target. Blocking dependency: none technical; this is a process discipline to be followed once BR-001/INT-001/INT-002 work begins.

**Acceptance criteria:**
- The tag-cutting change, the vendor-subtree pull, and each registry-file correction appear as distinct pull requests with distinct review histories.
- No single pull request spans both a modeller-pipelines-owned file and a modeller-agents-owned file.

**Validation method:** Pull request history inspection across both repositories.
**Related risks:** None additional.
**Related architecture:** None.
**Related plan items:** Brief §15 deliverables 1, 3, 4.
**Status:** Draft, to be validated

---

## 12. Observability requirements (OBS)

### OBS-001 - Tag-to-commit-to-version agreement is confirmable

**Statement:** modeller-pipelines MUST make it possible to confirm, at any time, that a named tag resolves to a commit and that the commit's `contracts/VERSION` content matches the tag name.
**Rationale:** direct re-statement of the brief's evidence requirements (§10); without this, a maintainer cannot distinguish a real tag from aspirational text.
**Source:** Business-need-design-brief.md §10 ("confirm that a named tag... actually resolves to a commit, and that the commit's contracts/VERSION content matches the tag name").
**Priority:** P0
**Dependencies:** BR-001, DATA-003
**Maturity:** Target. Blocking dependency: BR-001.

**Acceptance criteria:**
- A single command or documented procedure lets any maintainer verify tag-to-commit-to-version agreement for both `contract-v1.0` and `contract-v1.1`.
- The procedure is documented in `README.md` or `docs/HOW_TO_CONFORM.md`.

**Validation method:** Follow the documented verification procedure from a clean clone and confirm it produces the expected result.
**Related risks:** Unfetchable references (brief §2.2 risk 1).
**Related architecture:** None.
**Related plan items:** Brief §15 deliverable 1.
**Status:** Draft, to be validated

### OBS-002 - Backend-versus-registry agreement is confirmable

**Statement:** modeller-agents MUST make it possible to confirm, at any time, whether a backend's declared `contract_version` (in `backend.json` and `contract.lock`) and the registry's `expected_contract` value for that backend currently agree.
**Rationale:** direct re-statement of the brief's evidence requirements (§10); this is the mechanical check that would have caught the current skew before it accumulated.
**Source:** Business-need-design-brief.md §10 ("confirm that a backend's declared contract_version... and the registry's expected_contract value for that backend agree"), §7 ("the active context must always let a maintainer understand which contract version a given backend declares, which version the registry expects of it, and whether those two currently agree").
**Priority:** P0
**Dependencies:** INT-002
**Maturity:** Target. Blocking dependency: INT-002 (the correction itself has not landed yet).

**Acceptance criteria:**
- A documented procedure or check compares aimsun-psp's `contract.lock` value against `backends.toml`'s `expected_contract` and reports agreement or disagreement.
- The check is re-runnable after any future registry or backend-declaration change, not a one-time manual confirmation.

**Validation method:** Run the comparison procedure immediately after INT-002 lands, and again on a deliberately reintroduced mismatch to confirm it is detected.
**Related risks:** Live registry skew (brief §2.2 risk 2).
**Related architecture:** `modeller-agents/backends.toml`.
**Related plan items:** Brief §15 deliverable 4.
**Status:** Draft, to be validated

### OBS-003 - Vendor-subtree fidelity is confirmable offline

**Statement:** modeller-agents MUST make it possible to confirm, without a live fetch, that the vendored subtree's content matches the tagged content it claims to mirror.
**Rationale:** direct re-statement of the brief's evidence requirements (§10) and the whole point of the vendor subtree existing at all (brief §2.2 risk 3).
**Source:** Business-need-design-brief.md §10 ("confirm that the vendored subtree in modeller-agents matches the tagged content bit-for-bit, not merely that a directory exists").
**Priority:** P0
**Dependencies:** INT-001
**Maturity:** Target. Blocking dependency: INT-001.

**Acceptance criteria:**
- A documented, offline-runnable comparison (for example, a checksum manifest committed alongside the subtree pull) confirms bit-for-bit fidelity without requiring network access.
- The comparison flags a mismatch clearly rather than passing on a partially-populated subtree.

**Validation method:** Run the offline comparison against a deliberately corrupted or partial vendor copy and confirm it fails visibly.
**Related risks:** Unusable offline verification (brief §2.2 risk 3).
**Related architecture:** `modeller-agents/vendor/modeller-pipelines/`.
**Related plan items:** Brief §15 deliverable 3.
**Status:** Draft, to be validated

---

## 13. Human-in-the-loop requirements (HITL)

There is no AI agent surface in this repo's MVP (brief §9); the human-confirmation gates that exist are maintainer-to-maintainer review gates on irreversible or cross-repository actions.

### HITL-001 - A human confirms the target commit before a tag is cut

**Statement:** A modeller-pipelines maintainer MUST confirm which existing commit corresponds to each of the `contract-v1.0` and `contract-v1.1` states described in `CONTRACT_VERSIONS.md` and `CHANGELOG.md` before cutting the annotated tag on it.
**Rationale:** a tag is meant to be immutable once published (DATA-002); confirming the target commit is the one human-judgment step that prevents a wrong, permanent trust anchor.
**Source:** Business-need-design-brief.md §5.3 step 1, §8 step 3 ("before cutting a tag or editing a registry file, the maintainer confirms the commit or the declared version it targets is correct").
**Priority:** P0
**Dependencies:** BR-001, DATA-002
**Maturity:** Target. Blocking dependency: BR-001; this gate has not yet been exercised because no tag has been cut.

**Acceptance criteria:**
- A documented confirmation step (commit hash cross-referenced against `CONTRACT_VERSIONS.md`/`CHANGELOG.md`) precedes each `git tag` invocation.
- The confirming maintainer's identity is recorded, for example in the pull request or tag-cutting commit message.

**Validation method:** Review of the tag-cutting pull request for an explicit commit-confirmation step and reviewer identity.
**Related risks:** Wrong, permanent trust anchor.
**Related architecture:** None.
**Related plan items:** Brief §15 deliverable 1.
**Status:** Draft, to be validated

### HITL-002 - A human with file authority merges each correction

**Statement:** Every tag, vendor-subtree pull, and registry-field correction MUST be merged only by a maintainer with authority over the file in question (modeller-pipelines maintainer for tags and `README.md`; modeller-agents maintainer for `backends.toml`, `vendors.toml`, and `reference-packs/`).
**Rationale:** direct re-statement of the brief's need-to-result cycle (§8 step 6) and its user/responsibility matrix (§4); no automated execution surface exists, and none should be introduced to bypass this.
**Source:** Business-need-design-brief.md §4 (responsibility matrix), §8 step 6 ("a maintainer with authority over the relevant file... merges the change").
**Priority:** P0
**Dependencies:** None
**Maturity:** Target for the registry-correction and vendor-pull cases (not yet exercised); Current as a general repository-governance practice for tag and README changes within modeller-pipelines itself.

**Acceptance criteria:**
- Every pull request in this MVP that touches a modeller-agents-owned file is merged by a modeller-agents maintainer, not a modeller-pipelines maintainer.
- Every pull request that touches a modeller-pipelines-owned file (tags, `README.md`, `contracts/VERSION`) is merged by a modeller-pipelines maintainer.

**Validation method:** Merge-authorship review across both repositories' pull request history for this MVP's changes.
**Related risks:** Cross-repo authority confusion.
**Related architecture:** None.
**Related plan items:** Brief §15 deliverables 1-4.
**Status:** Draft, to be validated

---

## 14. Verification requirements (TEST)

### TEST-001 - End-to-end fetch-and-conform test from a clean clone

**Statement:** The MVP's completion test MUST include a clean-clone run of the full backend implementer's journey (brief §5.1): fetch the tagged contract, copy the template, author `backend.json`/`contract.lock`, run the conformance kit, and confirm the result.
**Rationale:** this is the reference journey the whole product promise depends on; nothing less than an end-to-end run from a clean environment proves the tag-and-fetch mechanism actually works.
**Source:** Business-need-design-brief.md §5.1 (full journey), §1 ("the MVP succeeds when a backend implementer can fetch a specific, tagged contract version and verify their own conformance against it").
**Priority:** P0
**Dependencies:** FR-001, FR-002, BR-001
**Maturity:** Target. Blocking dependency: BR-001 and FR-001; the test cannot run until the tags exist.

**Acceptance criteria:**
- A clean-clone test fetches `contract-v1.1`, copies `template/`, and runs the conformance kit against aimsun-psp's real (or a synthetic conforming) `backend.json`/`contract.lock`, exiting 0.
- The same test, run against a deliberately non-conforming manifest, exits non-zero with an actionable message.

**Validation method:** Scripted end-to-end test executed from a fresh clone, ideally the same script later wired into FR-003's CI workflow if pursued.
**Related risks:** Unfetchable references, no mechanical check against drift.
**Related architecture:** `conformance/` kit, `template/`.
**Related plan items:** Brief §15 deliverable 5 (if CI is pursued, this becomes its core test).
**Status:** Draft, to be validated

### TEST-002 - Registry-and-vendor agreement test

**Statement:** The MVP's completion test MUST include a check that, after INT-001 and INT-002 land, aimsun-psp's declared contract version, the registry's expected contract, and the vendored subtree's content all agree.
**Rationale:** this is the modeller-agents registry maintainer's journey (brief §5.2) proven end to end, and the direct test of the live skew this MVP exists to close.
**Source:** Business-need-design-brief.md §5.2 (full journey), §13 (success measures for the registry maintainer).
**Priority:** P0
**Dependencies:** INT-001, INT-002, OBS-002, OBS-003
**Maturity:** Target. Blocking dependency: INT-001 and INT-002 have not yet landed.

**Acceptance criteria:**
- A single check (script or documented procedure) confirms three-way agreement: `contract.lock`'s value, `backends.toml`'s `expected_contract`, and the vendored subtree's `contracts/VERSION`.
- Running the check today (before this MVP lands) demonstrably fails, evidencing the currently real skew.
- Running the check after INT-001/INT-002 land passes.

**Validation method:** Run the three-way agreement check both before and after the registry correction lands, and record both results.
**Related risks:** Live registry skew (brief §2.2 risk 2), unusable offline verification (brief §2.2 risk 3).
**Related architecture:** `modeller-agents/backends.toml`, `modeller-agents/vendor/modeller-pipelines/`.
**Related plan items:** Brief §15 deliverables 3, 4.
**Status:** Draft, to be validated

---

## 15. Minimal traceability

The expected traceability chain is:

```text
Business need
-> Shared concept
-> Requirement
-> Architecture component
-> Delivery batch
-> Acceptance criterion
-> Test
-> Controlled risk
```

Each P0 requirement above links to a section of the Business-need-design-brief, an owning maintainer role (§4 of this document), the file(s) it corrects, a deliverable from the brief's §15, and either an acceptance test in §14 or a named validation method inline. No formal risk register exists upstream of this repo; each requirement's "Related risks" field names the corresponding risk from the brief's §2.2 instead.

---

## 16. Definition of Ready for a requirement

A requirement is **Ready** when:

- its statement uses exactly one clear normative modality (MUST / MUST NOT / SHOULD / MAY);
- the source and owner are identified, and it traces to a business-need section or a logged open question;
- dependencies and risks are known;
- the acceptance criteria are testable;
- the necessary business decisions are made, or explicitly flagged as blocking (§19);
- its Maturity field is set and, if not Operational, names the blocking dependency;
- the impact on permissions, audit, and accessibility is analyzed (for this repo, this reduces to: which maintainer role has merge authority, per §13 HITL-002).

## 17. Definition of Done for a requirement

A requirement is **Done** when:

- the implementation is delivered in the target environment (the correct repository: modeller-pipelines for tags, modeller-agents for registry and vendor files);
- the acceptance criteria are satisfied;
- the applicable automated and manual tests pass;
- the necessary logs and metrics exist (for this repo: the tag, the corrected file, and the pull request review trail stand as the evidence);
- the user and technical documentation is updated (`README.md`, `CONTRACT_VERSIONS.md`, `HOW_TO_CONFORM.md` as applicable);
- approved deviations are recorded (for example, a decision not to sign tags, recorded against SEC-002);
- the owner accepts the result.

---

## 18. Current exclusions

Out of the normative scope of this version:

- new schema content, new normative documents, or a new contract minor or major version (see BR-003);
- onboarding or scaffolding a second conforming backend beyond aimsun-psp; `HOW_TO_CONFORM.md`'s path remains available to read but is not actively exercised by a second implementer in this MVP;
- any Testudo-facing consumption path or surface; this repository remains explicitly not a Testudo concern per `README.md` and `AGENTS.md`;
- any AI-driven or AI-assisted capability (a conformance advisor, an automated drafting tool); no such surface exists today and none is proposed by this PRD;
- automated drift detection across every consuming repository beyond the CI stretch item scoped to this repo's own `template/`;
- automatic publication of contract changes without human review (HITL-002 stands against this permanently, not only for this MVP);
- a dashboard of registry-to-backend conformance state across the ecosystem.

---

## 19. Blocking open decisions

| ID | Decision | Affected requirements |
|---|---|---|
| OPN-001 | Which remote is aimsun-psp's authoritative one for the purpose of a `curl`-fetchable schema URL in `README.md`'s quick-start section (open decision O1 named in the Vision)? | FR-001, OBS-001 |
| OPN-002 | Should the annotated tags be signed, given they are the trust anchor the whole contract-distribution design depends on? | SEC-002, BR-001 |
| OPN-003 | Is the CI workflow running the conformance kit against the template in scope for this MVP, or a follow-on step, given no `.github/` directory exists yet? | FR-003 |
| OPN-004 | Once `backends.toml`'s `status` is corrected away from `"planned"`, what is the correct value, and does modeller-agents have a defined status vocabulary already? | INT-002, NFR-002 |
| OPN-005 | Should a second conforming backend be actively pursued once this MVP closes, or does the ecosystem wait for organic demand? | None in this MVP; parked per Current exclusions (§18) |

---

## 20. Requirement family summary

| Family | Count | ID range |
|---|---|---|
| BR (Business requirements) | 4 | BR-001 to BR-004 |
| FR (Functional requirements) | 3 | FR-001 to FR-003 |
| INT (Integration requirements) | 2 | INT-001 to INT-002 |
| DATA (Data requirements) | 3 | DATA-001 to DATA-003 |
| SEC (Security requirements) | 2 | SEC-001 to SEC-002 |
| NFR (Non-functional requirements) | 3 | NFR-001 to NFR-003 |
| OBS (Observability requirements) | 3 | OBS-001 to OBS-003 |
| HITL (Human-in-the-loop requirements) | 2 | HITL-001 to HITL-002 |
| TEST (Verification requirements) | 2 | TEST-001 to TEST-002 |
| **Total** | **24** | |
