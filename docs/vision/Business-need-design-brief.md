# Modeller Pipelines Contract Surface: Business Need and Design Brief

**Recipients:** modeller-pipelines maintainers, aimsun-psp maintainers, modeller-agents registry maintainers
**Nature:** business framing, bounded MVP scope, and a design mandate for closing the tagging and registry-skew gap
**Status:** Draft for alignment
**Version:** 0.1, 25 July 2026
**Product:** Modeller Pipelines Contract Surface
**Upstream document:** docs/vision/Vision.md
**Downstream document:** docs/vision/Product-requirements-document.md

> This document sets out the business problem, the product vision, the users, the MVP journeys, the role of the contextual AI, the product's boundaries, and the decisions needed for design.
> It does not replace the `Product-requirements-document.md`, which carries the testable obligations, detailed rules, acceptance criteria, and non-functional requirements.

---

## 1. Executive summary

modeller-pipelines is a backend-neutral, versioned contract surface for the modeller ecosystem's pipelines and docks. Its goal is to let any backend, most concretely aimsun-psp today, and prospectively any future backend named in the ecosystem architecture, expose a pipeline, a step, a CLI seam, and a result envelope that means the same thing to every conforming implementer and to modeller-agents, the registry that coordinates work across them, without any of them importing this repo's code at runtime.

The repo lets a backend implementer read normative schemas and prose under `contracts/`, copy the illustrative `template/` pipeline as a starting point, and run the `conformance/` black-box kit against their own manifests and results. A single, visible governance surface, not a runtime service and not an AI agent, supports this work today: the contract's authority sits in versioned documents, ADRs, and a conformance kit, not in a piece of software that executes anything on a backend's behalf.

modeller-pipelines is not meant to replace a backend's own pipeline or dock implementation, and it is not a Testudo concern. aimsun-psp remains the system of authority for how its pipelines actually run; modeller-agents remains the authority over its own routing decisions.

> **Product promise: a pipeline, a step, and a dock mean the same thing to every backend and to the registry that coordinates them, proven by a pinned, versioned contract that nothing needs to import to conform to.**

The MVP succeeds when a backend implementer can fetch a specific, tagged contract version and verify their own conformance against it without reading another backend's source, and when modeller-agents can validate a backend's declared contract version offline, from a vendored copy that actually matches the tag it claims to mirror.

---

## 2. Business problem and opportunity

### 2.1 Current situation

The contract content itself is in reasonably good shape: two commits, a clean working tree, six schemas, five normative documents, and a fully implemented template pipeline exist on disk today. What does not exist is the distribution mechanism the whole design depends on. `CONTRACT_VERSIONS.md`, `CHANGELOG.md`, `ADR-0002`, and modeller-agents' own configuration files all refer to `contract-v1.0` and `contract-v1.1` as git tags a downstream consumer can fetch and pin against. None of those tags exist in this repository. A maintainer, or a downstream tool, trying to act on any of these references today must regularly check:

- whether the tag a document names (`contract-v1.0`, `contract-v1.1`) actually resolves to a commit, or is aspirational text;
- whether aimsun-psp's declared `contract_version` in `backend.json` and `contract.lock` matches what modeller-agents' registry expects for that backend;
- whether the `modeller-agents/vendor/modeller-pipelines/` subtree, meant to let modeller-agents verify conformance offline, actually holds any content;
- whether `README.md`'s own version banner still matches `contracts/VERSION` after a bump (this specific drift, along with the four normative docs' stale `Contract version: 1.0` headers and three schema `$id`s pinned to `.../1.0/...`, has since been corrected to `1.1` consistently; the tag-and-registry gap below remains open).

A significant share of the trust this contract is designed to provide depends on mechanisms that are currently unexercised, so the honest current state is: solid content, unproven distribution.

### 2.2 Current risks

This gap between documented mechanism and actual repository state creates four main risks:

1. **Unfetchable references**: every document that tells a reader to `git fetch` or pin against `contract-v1.0` or `contract-v1.1` is currently pointing at something that does not exist, which breaks the quick-start instructions in `README.md` and the conformance path in `docs/HOW_TO_CONFORM.md` the moment someone actually tries them.
2. **Live registry skew**: aimsun-psp's `backend.json` and `contract.lock` both declare `contract-v1.1`, while modeller-agents' `backends.toml` still expects `contract-v1.0` with `status = "planned"`, and both `vendors.toml` and `reference-packs/modeller-pipelines.toml` still pin `ref = contract-v1.0`. This is not a hypothetical drift scenario; it is a currently measurable mismatch between what one real backend declares and what the registry expects of it.
3. **Unusable offline verification**: the `modeller-agents/vendor/modeller-pipelines/` subtree exists as a directory but is completely empty, so the one mechanism designed to let modeller-agents check a backend's conformance without a live fetch or a read of the backend's own source is not actually usable today.
4. **No mechanical check against this drift**: no CI workflow exists in modeller-pipelines to run the conformance kit against the template on every change, so nothing catches a future divergence between the schemas and the template automatically, and nothing today caught the tag-and-registry gap before it accumulated.

> **Fundamental problem: the contract's value depends entirely on a distribution mechanism, pinned tags and an offline-verifiable vendor copy, that has never actually been exercised end to end, and a live skew between a real backend's declaration and the registry's expectation already exists as a direct result.**

### 2.3 Opportunity with modeller-pipelines closing this gap

The opportunity here is deliberately narrow: it is not new schema content and not a second backend. It is making the existing, already-documented mechanism actually work for the one real backend that already depends on it.

| Today | With the gap closed |
|---|---|
| `git tag -l` returns nothing, despite four documents assuming `contract-v1.0` and `contract-v1.1` exist as tags | Annotated tags `contract-v1.0` and `contract-v1.1` exist on the correct commits and resolve for anyone who fetches them |
| aimsun-psp declares `contract-v1.1`; modeller-agents' `backends.toml` expects `contract-v1.0` with `status = "planned"` | `backends.toml`'s `expected_contract` reads `1.1` and `status` reflects that a real backend already conforms |
| `vendors.toml` and `reference-packs/modeller-pipelines.toml` both pin `ref = contract-v1.0` | Both configs pin `ref = contract-v1.1`, matching aimsun-psp's actual declaration |
| `modeller-agents/vendor/modeller-pipelines/` is an empty directory | The subtree holds the pinned `contract-v1.1` content, so modeller-agents can verify offline |
| No CI workflow runs the conformance kit against the template | A CI job proves, on every change, that the template and the schemas still agree |
| ~~`README.md` header read `contract-v1.0` while `contracts/VERSION` read `1.1`~~ (fixed) | The header, all four normative docs, and all schema `$id`s now agree at `1.1` |

---

## 3. Product vision and product boundaries

modeller-pipelines becomes the single, trustworthy reference point a backend implementer or a registry maintainer can point at and know it has not silently changed underneath them. It is a governance and verification surface, not a runtime dependency of anything it describes, and not an AI-driven product: there is no contextual agent in this repo today, and none is proposed for the MVP scope in this brief. What the contract offers is a versioned, tagged, mechanically checkable definition of shape; it replaces neither a backend's own pipeline logic, nor modeller-agents' own routing judgement, nor a human maintainer's decision about when to bump a contract version.

### Product boundaries

For the MVP, modeller-pipelines:

- cuts and publishes annotated git tags `contract-v1.0` and `contract-v1.1` on the commits that already correspond to those documented versions;
- populates the `modeller-agents/vendor/modeller-pipelines/` subtree from the pinned `contract-v1.1` tag, so offline conformance verification becomes possible for the first time;
- corrects `modeller-agents/backends.toml` (`expected_contract` from `1.0` to `1.1`, `status` updated to reflect that aimsun-psp already conforms) and `reference-packs/modeller-pipelines.toml` (`ref` from `contract-v1.0` to `contract-v1.1`), so the registry's stated expectation matches aimsun-psp's actual declaration;
- adds a CI workflow, as a reasonable stretch item since no `.github/` directory exists yet, that runs the conformance kit against the template pipeline on every change to `contracts/` or `template/`.

In the MVP, modeller-pipelines must not:

- introduce new schema content, new normative documents, or a new contract minor or major version;
- onboard or scaffold a second conforming backend; `HOW_TO_CONFORM.md`'s path remains unexercised by anyone other than aimsun-psp until a future step chooses to pursue that;
- become a Testudo-facing surface, or expose any consumption path for Testudo; this remains explicitly out of scope per `README.md` and `AGENTS.md`;
- become a shared runtime library; nothing added during this MVP may be imported at runtime by any backend, per ADR-0001.

---

## 4. Users, responsibilities and access

The MVP is designed first for the **backend implementer conforming an existing pipeline system to the contract**, concretely the aimsun-psp maintainers today. The **modeller-agents registry maintainer**, who owns `backends.toml`, `vendors.toml`, and `reference-packs/`, is the second primary user for this MVP: closing the registry-skew gap is squarely their responsibility to review and merge. The **modeller-pipelines maintainer**, who cuts the tags and owns the ADR and versioning process, is the third. The following matrix is a working basis for design; it will need to be confirmed in the product requirements document.

| User | Main goal | Can do in the MVP | Cannot do by default | Authority or approval |
|---|---|---|---|---|
| **Backend implementer (aimsun-psp today)** | Fetch and verify a pinned contract version without reading another backend's source | Fetch a tagged contract version, run the conformance kit against their own manifests, confirm their `contract.lock` matches a real tag | Change contract shape unilaterally; publish a new contract version | aimsun-psp maintainers, within their own repo only |
| **modeller-agents registry maintainer** | Keep `expected_contract` and `status` current for every registered backend | Correct `backends.toml`, `vendors.toml`, `reference-packs/modeller-pipelines.toml` to match a backend's actual declaration; pull the vendored subtree from a pinned tag | Change modeller-pipelines' own contract content | modeller-agents maintainers, for their own registry files |
| **modeller-pipelines maintainer** | Make the documented tag-and-fetch mechanism real | Cut annotated tags on existing commits; add a CI workflow running the conformance kit against the template | Modify `contracts/` shape without going through the ADR process | modeller-pipelines maintainers, via the existing ADR sequence |
| **Future backend implementer (prospective)** | Evaluate whether to conform a new backend to the contract | Read `HOW_TO_CONFORM.md` and the tagged contract; not yet exercised in the MVP | Rely on a second real worked example beyond aimsun-psp | Out of MVP scope; parked for a later step |

### Project responsibilities

| Project responsibility | Expected role |
|---|---|
| **Tag cutting and contract versioning** | modeller-pipelines maintainer, following the ADR-0002 single `contract_version` field discipline |
| **Vendor subtree population and upkeep** | modeller-agents maintainer, via `git subtree` pull from the pinned tag, read-only |
| **Registry declaration accuracy (`expected_contract`, `status`)** | modeller-agents maintainer, kept current against each backend's actual `contract.lock` |
| **Backend-side conformance (`backend.json`, `contract.lock`)** | Each backend's own maintainers, aimsun-psp today |

---

## 5. MVP user journeys

### 5.1 Backend implementer's main journey

1. Reads `docs/HOW_TO_CONFORM.md` to understand what conforming to a specific contract version requires.
2. Fetches the schemas for the target `contract_version` from the newly cut tag, for example `contract-v1.1`, instead of reading an unpinned working-tree copy.
3. Copies the relevant `template/` files as an illustrative starting point, understanding that `template/` is never normative.
4. Authors or updates their own `backend.json` and `contract.lock` declaring the contract version they conform to.
5. Runs the conformance kit against their own CLI seam and result envelope.
6. Confirms the conformance kit's report matches what they expect, with no silent pass on an unsupported version.
7. Confirms their declared `contract_version` in `contract.lock` corresponds to a real, fetchable tag, not an aspirational version string.

### 5.2 modeller-agents registry maintainer's journey

1. Reviews the current, live mismatch between aimsun-psp's declared `contract-v1.1` and the registry's `expected_contract = 1.0`.
2. Pulls the pinned `contract-v1.1` tag into the `modeller-agents/vendor/modeller-pipelines/` subtree.
3. Corrects `backends.toml`'s `expected_contract` and `status` fields, and `vendors.toml` and `reference-packs/modeller-pipelines.toml`'s `ref` fields, so they match aimsun-psp's actual declaration.
4. Confirms, offline, that the vendored subtree content matches the tagged content it claims to mirror.

### 5.3 modeller-pipelines maintainer's journey

1. Confirms which existing commits correspond to the `contract-v1.0` and `contract-v1.1` states already described in `CONTRACT_VERSIONS.md` and `CHANGELOG.md`.
2. Cuts annotated tags on those commits.
3. Adds a CI workflow that runs the conformance kit against `template/` on every change to `contracts/` or `template/`, if this is judged in scope for the MVP. (The `README.md` version-banner drift this step originally also covered is already fixed; see Section 2.1.)

The MVP must demonstrate the continuity of these three journeys: a tag that exists, a registry that reflects it, and a template that a CI job keeps honest. It must not be designed as three independent, uncoordinated fixes.

---

## 6. How modeller-pipelines supports the work

Sections 5.1 through 5.3 already state the concrete path for each user (fetch a pinned tag, correct the registry, cut the tags). Two points those journeys don't state explicitly: there is no long-running execution or AI-generated interpretation anywhere in this MVP, the conformance kit runs synchronously and reports pass/fail against schema and prose, nothing more; and every contract change stays attributable to a commit, a version bump, and, once this MVP lands, a tag, with an unreleased schema draft never something a backend can conform to.

---

## 7. Organization of a modeller-pipelines contract version

A contract version, in this repo's model, represents one immutable, tagged snapshot of `contracts/` that a backend can conform to and a registry can pin against. It contains at minimum:

- a `contracts/VERSION` file stating the current version string;
- a set of JSON Schemas under `contracts/schemas/` (`pipeline.schema.json`, `step-result.schema.json`, `result.schema.json`, `backend.schema.json`, `run-config.schema.json`);
- normative prose documents (`PIPELINE_DEFINITION.md`, `STEP_INTERFACE.md`, `CLI_SEAM.md`, `RESULT_CONTRACT.md`);
- an entry in `CONTRACT_VERSIONS.md` naming its git tag and support status;
- an entry in `CHANGELOG.md` describing what changed since the prior version;
- an annotated git tag, once this MVP closes the current gap, that a downstream consumer can fetch.

### Core relationships

- **contract_version**: the single field, per ADR-0002, that every backend's `contract.lock` and `backend.json` declares; there is no per-schema version sprawl.
- **git tag**: the fetchable, immutable pointer to the commit that a `contract_version` string corresponds to; currently missing for both published versions.
- **backend.json / contract.lock**: a backend's own declaration of which contract version it conforms to, owned entirely by the backend's repository.
- **expected_contract / status (modeller-agents registry)**: the registry's own record of what it expects from a given backend, which must be kept in sync with the backend's actual declaration by the registry's maintainers, not automatically.
- **vendor subtree**: a read-only, pinned, squashed copy of `contracts/` and `conformance/` inside modeller-agents, letting it check a backend's conformance without a live fetch.

The active context must always let a maintainer understand which contract version a given backend declares, which version the registry expects of it, and whether those two currently agree.

---

## 8. Need-to-result cycle

Sections 5.1 through 5.3 state this cycle in full, per user. The one point worth adding here: every step is a small, reviewable, human-authored change with no automated execution surface, and a tag is meant to be immutable once published, so confirming the target commit before cutting it matters more than for an ordinary edit. This cycle replaces a set of documents that describe a mechanism that does not yet work with a mechanism that has actually been exercised once, end to end, for the one real backend that depends on it.

---

## 9. The contextual AI agent

There is no contextual AI agent in this repo's MVP scope, and none is proposed by this brief. modeller-pipelines is a governance and verification surface, schemas, prose, a conformance kit, and (with this MVP) tags and a CI check; every action in Sections 5 through 8 is performed by a human maintainer following documented steps, not by an assistant.

Sections 9.1 through 9.5 of the template this brief is built from do not apply to this MVP and are intentionally omitted rather than filled with placeholder content. If a future contract version, or a future companion tool in this ecosystem, introduces an AI-assisted conformance advisor (for example, one that drafts a `backend.json` from an existing pipeline's structure), that capability would need its own business-need treatment at that time; it is explicitly not part of the scope this brief mandates.

---

## 10. Evidence, review and publication

Every tag cut and every registry correction must remain linked to the context that justified it: the commit it targets, the `CONTRACT_VERSIONS.md` and `CHANGELOG.md` entries it corresponds to, and the specific mismatch it closes.

The MVP must make it possible to:

- confirm that a named tag (`contract-v1.0`, `contract-v1.1`) actually resolves to a commit, and that the commit's `contracts/VERSION` content matches the tag name;
- confirm that a backend's declared `contract_version` (in `backend.json` and `contract.lock`) and the registry's `expected_contract` value for that backend agree;
- confirm that the vendored subtree in modeller-agents matches the tagged content bit-for-bit, not merely that a directory exists;
- distinguish a passing conformance-kit run from a failing one, with the kit's own loud, actionable error message on an unsupported version, per `CONTRACT_VERSIONS.md`'s explicit prohibition on silent degradation;
- retain, in each pull request that cuts a tag or corrects a registry file, the identity of the maintainer who approved it.

Advanced features such as automated drift detection across every consuming repo, and a dashboard of registry-to-backend conformance state, are out of MVP scope. The MVP must nonetheless clearly flag, rather than silently ignore, a tag that does not exist, a registry field that does not match a backend's declaration, or an empty vendor subtree, exactly the three conditions this brief exists to close.

---

## 11. MVP functional scope by user

| User | Actions covered by the MVP |
|---|---|
| **Backend implementer (aimsun-psp)** | Fetch a real, tagged contract version; confirm `contract.lock` matches a fetchable tag; run the conformance kit against their own manifests |
| **modeller-agents registry maintainer** | Correct `backends.toml`, `vendors.toml`, and `reference-packs/modeller-pipelines.toml`; populate the vendor subtree from the pinned tag |
| **modeller-pipelines maintainer** | Cut annotated tags `contract-v1.0` and `contract-v1.1`; optionally add a CI workflow running the conformance kit against the template (the version-banner correction this row previously named is already done) |
| **Future backend implementer (prospective)** | None in this MVP; `HOW_TO_CONFORM.md`'s path remains available to read but is not actively onboarded here |

### Cross-cutting MVP capabilities

The contract surface must also provide: a version history that names a real, fetchable tag for every entry in `CONTRACT_VERSIONS.md` and `CHANGELOG.md`, a registry whose `expected_contract` and `status` fields are demonstrably current against at least the one real backend, an offline-verifiable vendor subtree, understandable conformance-kit error messages naming the detected and minimum supported versions, and, if the CI stretch item is pursued, a check that runs on every change to `contracts/` or `template/` rather than only on request.

---

## 12. Parking lot

The following items are kept as future directions but must not shape this MVP.

| Deferred feature | Main reason | Condition for reconsideration |
|---|---|---|
| A second conforming backend beyond aimsun-psp | The Vision's suggested first step explicitly scopes this MVP to closing the tagging and registry gap, not onboarding a new implementer | Once the tag-and-fetch mechanism and the registry correction are proven end to end for aimsun-psp |
| Automated drift detection across every consuming repo | No such mechanism exists today, and building one before the basic tag-and-vendor mechanism works would be premature | Once CI runs the conformance kit against the template reliably and the registry stays manually current for at least one full contract version cycle |
| An AI-assisted conformance advisor for new backend implementers | No AI surface exists in this repo today; the MVP is a governance and tagging fix, not a new product capability | Only after a second real backend implementer's manual experience with `HOW_TO_CONFORM.md` surfaces a concrete need |
| Automatic publication of contract changes without review | Incompatible with expected human control over what becomes an accepted contract version | No reconsideration planned without a governance change |
| Silent modification of contract shape outside the ADR process | Trust and traceability risk; contract-shape decisions must stay attributable to a recorded ADR | Must remain prohibited |

---

## 13. Expected outcomes and success measures

The measures must compare the MVP to the current situation. Target values will be defined after observing real workflows; no target figures are set here in advance.

| User | Key action | Expected outcome | Candidate indicator |
|---|---|---|---|
| Backend implementer (aimsun-psp) | Fetch a tagged contract version | The tag resolves and matches the commit `CONTRACT_VERSIONS.md` describes | Whether `git fetch` against the named tag succeeds and `contracts/VERSION` at that tag matches the tag name |
| modeller-agents registry maintainer | Verify a backend's declared contract version offline | Verification succeeds without a live fetch and without reading aimsun-psp's source | Whether the vendored subtree content matches the tagged content bit-for-bit |
| modeller-agents registry maintainer | Keep `expected_contract` current | The registry's stated expectation matches aimsun-psp's actual declaration | Whether `backends.toml`'s `expected_contract` equals aimsun-psp's `contract.lock` value after the correction |
| modeller-pipelines maintainer | Run the conformance kit against the template in CI | Every change to `contracts/` or `template/` is checked automatically | Whether a CI job exists and its most recent run passed |

---

## 14. UI objective

Not applicable in the conventional sense: modeller-pipelines has no graphical interface, dashboard, or visual workspace, and none is proposed by this MVP. The relevant surfaces are text documents (`README.md`, `CONTRACT_VERSIONS.md`, `CHANGELOG.md`), configuration files (`backends.toml`, `vendors.toml`, `reference-packs/modeller-pipelines.toml`), and command-line output from the conformance kit and from `git tag` or `git subtree` operations.

The design work this MVP does require resolves as a priority:

- making every version reference in `README.md`, `CONTRACT_VERSIONS.md`, and `CHANGELOG.md` point at something that actually fetches;
- making the registry's `expected_contract` and `status` fields demonstrably traceable to a backend's real declaration;
- making the vendor subtree's content verifiably identical to the tag it claims to mirror;
- if pursued, presenting the CI conformance check's pass or fail state clearly on a pull request, with an actionable message on failure.

---

## 15. Expected deliverables from design

For this MVP, "design" work is documentation and configuration correctness work, not visual or interaction design. The team closing this gap must produce:

1. two annotated git tags (`contract-v1.0`, `contract-v1.1`) on the correct, verified commits;
2. a populated `modeller-agents/vendor/modeller-pipelines/` subtree, pulled from the pinned `contract-v1.1` tag with `squash = true`, matching `vendors.toml`'s declared `writable = false`;
3. corrected `backends.toml`, `vendors.toml`, and `reference-packs/modeller-pipelines.toml` entries in modeller-agents, each independently reviewable;
4. if pursued as the stretch item, a `.github/` CI workflow running the conformance kit against `template/` on every relevant change, with its configuration and first passing run as evidence.

(The `README.md` version banner correction originally listed here is already done; see Section 2.1.)

---

## 16. Expected input from product and technology

### Product and business

Confirmation of which commits correspond to the `contract-v1.0` and `contract-v1.1` states described in `CONTRACT_VERSIONS.md` and `CHANGELOG.md`; resolution of open decision O1 (aimsun-psp's authoritative remote), since a tag's usefulness depends on which remote is treated as canonical; agreement from modeller-agents maintainers on the corrected `expected_contract` and `status` values before those files are edited; confirmation that no schema or normative-prose change is bundled into this MVP, since that would require a new ADR and a new version, not just a tag.

### Technology

`git tag` and `git subtree` mechanics, including whether the annotated tags should be signed; the exact `squash = true`, `writable = false` subtree-pull invocation modeller-agents' `vendors.toml` already declares as its intended contract; a bit-for-bit comparison method to confirm the vendored subtree matches the tagged content; availability of a `.github/` Actions runner if the CI stretch item is pursued; confirmation that the conformance kit's existing exit-code and JSON-report behavior is sufficient for a CI pass or fail gate without modification.

---

## 17. Priority open questions

| ID | Question | Main impact | Suggested owner |
|---|---|---|---|
| **OPN-001** | Which remote is aimsun-psp's authoritative one for the purpose of a `curl`-fetchable schema URL in `README.md`'s quick-start section (open decision O1 named in the Vision)? | Whether the quick-start fetch instructions in `README.md` are actually correct once tags exist | modeller-pipelines maintainer, with aimsun-psp maintainers |
| **OPN-002** | Should the annotated tags be signed, given they are the trust anchor the whole contract-distribution design depends on? | Level of assurance a downstream consumer gets when fetching a tag | modeller-pipelines maintainer |
| **OPN-003** | Is the CI workflow running the conformance kit against the template in scope for this MVP, or a follow-on step, given no `.github/` directory exists yet? | Whether this brief's MVP includes a new CI surface or stays limited to tags and registry correction | modeller-pipelines maintainer, with alignment from recipients |
| **OPN-004** | Once `backends.toml`'s `status` is corrected away from `"planned"`, what is the correct value, and does modeller-agents have a defined status vocabulary already? | Whether the registry correction in this MVP is internally consistent with modeller-agents' own conventions | modeller-agents registry maintainer |
| **OPN-005** | Should a second conforming backend be actively pursued once this MVP closes, or does the ecosystem wait for organic demand? | Whether `HOW_TO_CONFORM.md`'s path gets a second worked example soon, or stays a documented-but-unexercised path | modeller-pipelines maintainer, with ecosystem sponsors |

---

## 18. Consolidated statement of need

modeller-pipelines must let a backend implementer, concretely aimsun-psp's maintainers today, fetch a real, tagged, immutable contract version and verify their own conformance against it without reading another backend's source. It must let modeller-agents' registry maintainers correct a live, currently measurable skew between what aimsun-psp declares (`contract-v1.1`) and what the registry expects (`contract-v1.0`, `status = "planned"`), and it must let modeller-agents verify a backend's declared contract version offline, from a vendor subtree that actually holds the pinned content it claims to mirror.

There is no contextual AI agent in this MVP's scope. Every action, cutting a tag, pulling a subtree, correcting a registry field, is a human-authored, individually reviewable change performed by the maintainer with authority over the file in question. modeller-pipelines does not decide what a backend should do or how it should model; it only makes the shape it exposes, and the version it declares, mechanically checkable.

Every contract version must remain linked to a real, fetchable tag and an identifiable maintainer's approval to publish it. This MVP does not add new schema content, does not onboard a second backend, and does not introduce a Testudo-facing surface. It closes exactly the three gaps the Vision's own suggested first step names: cutting the tags, populating the vendor subtree, and correcting the registry's expected contract value, so that the mechanism this repo's entire design already assumes is finally something a maintainer can point at and trust, rather than a description of something that has not yet happened.
