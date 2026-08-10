# Wave Definitions

Each wave: objective, lanes dispatched, inputs, outputs, gate id + pass
criteria, stop conditions. The orchestrator does not release the next wave
until the current gate passes (or is explicitly ratified as a conditional
pass — see `gate-criteria.md`).

---

## Wave C — Vault creation / scaffolding (Stage A)

**Objective:** stand up a governed, standard-aligned vault so the acquisition
waves have a consistent structure to write into. Fixes the historical gap where
each mission started from an ad-hoc folder.

**Lanes:** orchestrator only (owns Git/integration — not a subagent lane).

**Inputs:** a target directory, a mission/vault name, a default sensitivity
(`restricted` unless the owner sets otherwise), and optionally the source glob.

**Actions:** run `scripts/scaffold_vault.py --target <dir> --vault-name "<name>"
--sensitivity restricted`. It creates the folder skeleton (`corpus/`, `data/`,
`lanes/`, `curation/` incl. `board-packs/` + `promotion/`, `diataxis/{reference,
explanations,how-to,tutorials}/`, `model-checks/`, `templates/`), instantiates
`HOME.md`/`HANDOFF.md`/`plan.md`/`knowledge-graph-ontology.md`/`README.md` from
`references/templates/` with token substitution, drops the per-type note
templates into `<vault>/templates/`, seeds the empty curation registers and CSV
headers, and writes a `.gitignore` (generated artifacts, `__pycache__`, `.obsidian`
workspace state). All templates are aligned to
`modelling-knowledge/standards/knowledge-metadata-standard` so a promoted note maps
1:1 onto the accepted profile.

**Outputs:** the scaffolded vault tree; `curation/acquisition-ledger.md` seeded
with the GC verdict.

**Gate GC:** `scripts/scaffold_vault.py --check <vault>` — skeleton present,
`.gitignore` present, root docs instantiated, every `templates/*.md` parses and
carries `status`/`type`/`authority_level`/`sensitivity`, sensitivity defaulted to
`restricted`. Must pass before Wave 0.

**Stop conditions:** target directory already contains a populated vault (refuse
to overwrite without `--force`); templates directory missing; sensitivity not one
of `public|internal|restricted`.

---

## Wave 0 — Preflight and package validation

**Objective:** confirm the generated/converted package is a reliable
acquisition baseline before any technical interpretation begins.

**Lanes:** orchestrator only (no subagent dispatch).

**Inputs:** raw source documents, converted markdown, generated matrices,
graph nodes/edges/JSON-LD.

**Actions:** record package path, source hashes, generation timestamp,
tool version; run deterministic validators (`validate-source`,
`validate-package`, `vault-doctor check`); confirm every source has a
register entry, converted markdown, stable section anchors, and
comment/table/image records where applicable; compare matrix counts against
source inventory; freeze the baseline digest; create `lane-status.md` with
all lanes `not-started`.

**Outputs:** `curation/acquisition-ledger.md` (baseline digest),
`curation/lane-status.md`.

**Gate G0 — pass when:**
- all sources resolve (hash matches register);
- no blocking provenance error exists;
- every matrix link resolves;
- the JSON-LD file parses;
- default sensitivity is recorded as `restricted`;
- the baseline digest is stored.

**Stop condition:** stop the entire execution if source anchors are missing,
sources cannot be reconciled, or graph generation is nondeterministic.
Repair extraction before dispatching domain lanes.

---

## Wave 1 — Document-domain acquisition lanes

**Objective:** each lane extracts atomic, evidence-backed candidates
(claims, rules, workflows, objects, terms, issues, contradictions) from one
source or tightly-related source family. Lanes do not author accepted
knowledge.

**Lanes (parallel, one per source/domain):** one acquisition lane per
source document or source family (e.g. data/observations, network/coding,
demand, calibration/validation, operations/manual, final-remarks/acceptance,
visual-evidence audit across all sources).

**Inputs:** frozen read-only source snapshot (hashes from Wave 0), a lane
brief (see `subagent-brief-templates.md`), a fixed ID namespace per lane.

**Outputs (per lane, under `lanes/<lane-id>/`):** `findings.md`,
`candidate-claims.md`, `candidate-rules.md`, `candidate-workflows.md`,
`candidate-objects.md`, `candidate-terms.md`, `candidate-issues.md`,
`contradictions.md`, `unresolved-questions.md`, `lane-receipt.json`.

**Lane gate (per lane, self-reported in `lane-receipt.json`):** a second
analyst can identify the source, selection rule, transformation and
limitations for every item the lane covers, or the item is marked a
blocking ambiguity.

**Integration (`PLAN-KA-090`, orchestrator-owned):** verify every lane
receipt; reject free-form conclusions without candidate records; merge
candidates into staging matrices preserving lane provenance; detect
duplicate statements, conflicting thresholds, alias collisions, object-name
collisions, comment-challenged claims, unsupported conclusions; generate the
integration diff + `source-quality-findings.md`; mark nothing `accepted`.

**Gate G1 — pass when:**
- all lane receipts pass;
- every critical issue from the final-remarks/acceptance material is linked
  to at least one report claim;
- every candidate has provenance;
- duplicate IDs = 0;
- unresolved ambiguities are visible in the decision queue.

**Conditional pass pattern:** a lane self-reporting `fail` because its
*source material* is genuinely incomplete or contested (not because the
acquisition was sloppy) does not block G1 outright — externalise the gap to
the conflict/decision registers and have the knowledge owner ratify a
conditional pass before Wave 2 authoring touches that lane's scope.

**Stop condition:** a source anchor does not resolve, a statement contains
multiple inseparable claims, or a model reference has multiple candidate
objects with no owner decision.

---

## Wave 2 — Cross-document reconciliation lanes

**Objective:** reconcile Wave 1 candidates by knowledge axis rather than by
source document.

**Lanes (parallel where independent):**
- **Terminology/identity** — reconcile aliases, distinguish human label /
  report label / exact model-object name; prohibit silent renaming.
- **Model-object resolution** — resolve scenario/experiment/demand/profile/
  path-assignment/geometry-config/replication/result-database references
  against the approved model; classify each as `resolved`, `ambiguous`,
  `missing`, `obsolete` or `unverified`.
- **Workflow reconstruction** — rebuild the complete operational flow with
  inputs/outputs/preconditions/rerun-conditions/gates; flag where documented
  and operational workflows diverge.
- **Rule formalisation** — for each rule: statement, scope, units,
  population, aggregation, formula, threshold, boundary inclusivity,
  missing-value behaviour, exceptions, test fixture, source evidence,
  approval status.
- **Contradiction/acceptance analysis** — identify report-vs-comment,
  report-vs-report, report-vs-model and criterion-vs-conclusion conflicts;
  distinguish intended/documented/implemented/observed/accepted behaviour;
  draft decision records without deciding.

**Inputs:** all Wave 1 lane packets; the Wave 1 conflict/object/decision
registers.

**Outputs:** reconciled `terminology-matrix`, `object-resolution-register.md`,
reviewed workflow matrix + diagrams, formalised `rule-matrix` with fixtures,
consolidated `conflict-register.md`, `decision-queue.md`.

**Integration (`PLAN-KA-190`, orchestrator-owned):** merge reconciled
outputs; regenerate graph candidates; update the traceability chain
(`source -> claim -> rule/workflow -> model object -> result -> reviewer
challenge -> decision/open question`); classify every candidate as
`ready-for-technical-review`, `ready-for-decision`,
`blocked-by-missing-evidence`, `rejected-as-duplicate` or `historical-only`.

**Gate G2 — pass when:**
- every pilot workflow step has inputs and outputs;
- every pilot rule is executable or explicitly blocked;
- every required object is resolved or in the blocker list;
- all critical remarks/acceptance issues are traceable;
- graph validation has no structural error.

**Conditional pass pattern:** if reconciliation itself is complete but
certification depends on external dependencies (human decisions, live-model
access, board-adopted formulas/thresholds), record the gate as **blocked by
design** rather than failed — the automated pipeline has reached its
ceiling and the remaining work is Wave 3's human gate, not more analysis.

**Stop condition:** multiple candidate objects match one operational
instruction without an owner decision.

---

## Wave 3 — Human review and decision gates

**Objective:** agents prepare evidence; humans approve knowledge. No
automation adjudicates a contested or contractual question.

**Lanes:** `ka-board-pack-prep` builds one evidence pack per review board
(Data, Network/model, Calibration, Validation, DRIEAT-acceptance,
Knowledge). See `board-pack-template.md`.

**Inputs:** `curation/decision-queue.md`, `curation/conflict-register.md`,
`curation/object-resolution-register.md`.

**Outputs:** `curation/board-packs/<board-id>.md` per board; once ruled,
`curation/decision-record.md` (authoritative log) and updated
conflict/object/rule registers.

**Gate G3 — pass when:**
- pilot-critical decisions are accepted;
- deferred items are explicitly scoped out (not silently dropped);
- open items are narrow and flagged, and none block reference authoring.

No Diátaxis operational note is authored until the relevant board decision
is accepted or the note is explicitly scoped as an unresolved explanation.

---

## Wave 4 — Diátaxis authoring lanes

**Objective:** author Diátaxis knowledge candidates in strict dependency
order: reference, then explanation, then how-to. The tutorial stays
deferred.

**Lanes (reference first, then explanation + how-to together):**
- **Reference** — dataset catalogue, terminology reference, model-object
  registry, scenario/experiment matrix, workflow-step register,
  validation-criteria reference, KPI formula reference, horizon
  configuration reference, known-issues reference.
- **Explanation** — architecture/role/purpose narratives. Must introduce no
  new thresholds, names or workflow steps beyond what reference already
  states.
- **How-to** — task guides with preconditions, exact inputs, resolved
  objects, actions, outputs, checks, failure modes, rollback, evidence
  produced.
- **Tutorial** — outline only. Full authoring blocked until Wave 6 passes.

**Inputs:** `curation/decision-record.md`, reviewed matrices from Wave 2.

**Outputs:** `diataxis/reference/*.md`, `diataxis/explanations/*.md`,
`diataxis/how-to/*.md`, all `status: proposed`.

**Gate:** no single numbered gate. Each lane carries its own pass
criterion — reference: every value/name links to reviewed evidence or a
decision; explanation: no new thresholds/names/steps introduced; how-to:
every guide has all required sections. The wave as a whole is considered
complete when reference precedes explanation/how-to and nothing is marked
`accepted`.

**Note:** if a revised source arrives during or after this wave, insert the
delta re-baseline sub-wave here before Wave 5 (see `delta-rebaseline.md`).

---

## Wave 5 — Graph integration and deterministic validation

**Objective:** rebuild the knowledge graph from the *reviewed* layer
(curated vault artifacts only — never raw source documents) and run
deterministic validation.

**Lanes:** `ka-graph-validation`, using `scripts/build_reviewed_graph.py`
then `scripts/gate_check.py --gate G5`.

**Inputs:** `data/accepted-layer.csv` (write-back overlay of Wave 3
decisions), `curation/conflict-register.md`, formalised rules, reconciled
objects/terms, the workflow-step register, all Diátaxis front matter.

**Outputs:** `diataxis/graph/reviewed/{nodes.csv,edges.csv,
knowledge-graph.jsonld,graph-validation-report.md,unresolved-relations.md}`.

**Gate G5 — the seven deterministic checks, all must pass:**
1. stable IDs are unique;
2. every accepted/proposed rule has ≥1 evidence edge;
3. every accepted workflow step has input and output edges;
4. every model object resolves or carries an explicit unresolved status;
5. every challenged claim has a conflict or decision edge;
6. no accepted node is linked to an unresolved critical contradiction;
7. JSON-LD export is deterministic (byte-identical nodes/edges/JSON-LD
   hashes across two consecutive runs).

Non-`accepted` states (contested-v2, open, deferred) are allowed in the
graph as long as none of them are the 12 critical-tier conflicts left
unresolved, and none carry an `accepted` status while unresolved.

**Stop condition:** any of the seven checks fails, or a generated artifact
disagrees with the reviewed matrices it was built from.

---

## Wave 6 — Independent reproduction pilot

**Objective:** an independent modeller (not involved in authoring)
reproduces the accepted operational workflow end-to-end without
undocumented expert assistance, using only the how-to guides and reference
material produced so far.

**Roles:** Executor = uninvolved modeller. Observer = orchestrator.
Reviewer = domain/calibration lead.

**Inputs:** accepted workflow chain, resolved objects, the how-to guides,
the reproduction protocol.

**Outputs:** run manifest, object IDs/names/parameters/seed used, start/end
times, produced database/exports, KPI outputs, deviations from baseline,
every undocumented intervention, screenshots of critical model states.

**Gate G6 — pass when:** the independent modeller completes the workflow
without undocumented expert assistance and reproduces the accepted outputs
within approved tolerances. Checked via `gate_check.py --gate G6`, which
also verifies: how-to guides present, reproduction protocol authored, no
`contested-v2` decisions outstanding, and all required objects verified
against the live model.

**Failure handling:** every failure is classified as missing reference
information, incorrect object resolution, incomplete workflow step,
ambiguous rule, model defect, baseline defect, or environmental/software
dependency. The relevant lane is reopened. The tutorial remains blocked.

---

## Wave 7 — Promotion and handoff

**Objective:** package approved knowledge for governed promotion, keeping
project-specific evidence separate from reusable discovery drafts.

**Lanes:** orchestrator + knowledge owner (no further subagent dispatch
beyond `ka-graph-validation` re-running gate checks).

**Actions:** finalise the tutorial (only after Wave 6 passes); package
project-specific knowledge under the restricted audit area; draft reusable
discovery drafts separately; register in the audit registry/index; run
package validators and `vault-doctor check`; produce the final integration
and traceability report; submit discovery drafts to the human promotion
process.

**Gate G7 — pass only when all six hold:**
1. the traceability chain is complete (G5 pass);
2. technical and acceptance decisions are recorded, with no Major-tier
   `contested-v2` items outstanding;
3. independent reproduction passes (G6 pass);
4. sensitivity is explicitly approved (not just left at the default);
5. graph and vault gates pass (G5 pass + `vault-doctor check` run);
6. the knowledge owner explicitly approves promotion (a one-line sign-off
   act, distinct from any board ruling already on record — never inferred).

Checked via `gate_check.py --gate G7`. Until all six close, the promotion
package stays `blocked-pending-G6+approval` and the audit-registry candidate
stays unregistered (`promotion_allowed: false`).
