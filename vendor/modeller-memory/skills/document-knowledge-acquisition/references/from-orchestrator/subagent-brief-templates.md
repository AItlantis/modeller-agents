# Subagent Brief Templates

Every lane subagent — acquisition, reconciliation, authoring, delta-rebaseline,
board-pack-prep — is dispatched with the same structured brief and operates
under the same prohibitions. Do not paraphrase these into free-form prose
when dispatching a lane; fill the template.

## Standard delegation brief

```yaml
lane_id:                 # e.g. KA-R1-DATA, KA-X-TERMS, KA-D-REFERENCE
objective:                # one sentence: what this lane must extract/reconcile/author
allowed_sources:          # exact files/anchors/matrices this lane may read
read_only_context:        # material for orientation only, not to be cited as evidence
required_outputs:         # exact file list this lane must produce (see agent_manifest.yml)
output_schema:             # the per-row/per-record schema each output must satisfy
id_namespace:              # fixed ID prefix for this lane (see table below); prevents parallel collisions
evidence_requirements:      # verbatim extract + source anchor + evidence_link required per item
known_conflicts:           # conflicts already logged that this lane's scope touches
stop_conditions:           # see "Stop and report a blocker" below
gate_command_or_check:     # the lane gate / wave gate this output will be checked against
deadline_or_budget:        # time/turn budget for this lane
```

### ID namespace allocation (extend per project)

| Lane family | ID prefix |
|---|---|
| Source-domain acquisition lane N | `<PROJECT>-<SOURCE>-*` (e.g. `DRIEAT-R1-*`) |
| Cross-document terminology | `<PROJECT>-TERM-*` |
| Cross-document object | `<PROJECT>-OBJ-*` |
| Cross-document workflow | `<PROJECT>-WF-*` |
| Cross-document rule | `<PROJECT>-RULE-*` |
| Decision | `<PROJECT>-DEC-*` |
| Issue | `<PROJECT>-ISSUE-*` |
| Delta re-baseline lane | `<PROJECT>-<SOURCE>V2-ISSUE-*` (scoped, does not reuse the v1 prefix) |

The orchestrator may mint consolidated IDs after deduplication but must
preserve `derived_from` links back to the originating lane IDs.

## Standard subagent prompt (paste and fill `<...>` fields)

```text
You are subagent <LANE_ID> in the <PROJECT> knowledge-acquisition execution.

Objective:
<OBJECTIVE>

Allowed evidence:
<FILES, MATRICES AND SOURCE SECTIONS>

Do:
- inspect all assigned source anchors;
- extract atomic claims, rules, workflows, objects, terms, issues and contradictions;
- preserve verbatim extracts and evidence links;
- distinguish intended, documented, implemented, observed and accepted behaviour;
- mark confidence and review status;
- return all required lane artifacts and lane-receipt.json.

Do not:
- write accepted knowledge;
- infer a project-acceptance decision;
- silently reconcile conflicting statements;
- invent model-object identities;
- lower sensitivity;
- commit or merge.

Stop and report a blocker when:
- a source anchor does not resolve;
- a statement contains multiple inseparable claims;
- a model reference has multiple candidate objects;
- units, population, interval or threshold are undefined;
- a reviewer comment challenges the item and no decision resolves it.

Completion:
Your lane passes only when every candidate satisfies the shared provenance
schema and the lane-specific gate. A narrative summary without the
structured artifacts is incomplete.
```

## Standard subagent prohibitions

Every lane subagent, regardless of wave, must not:

- write directly to accepted knowledge storage (the equivalent of
  `domains/**` in the target knowledge repo);
- resolve a contractual or client-acceptance question by inference;
- silently replace a report term with a preferred term (no renaming without
  an explicit alias record);
- create a model-object identity without exact evidence;
- remove or soften a contradicted claim;
- lower sensitivity;
- commit or merge (the orchestrator owns Git);
- mark its own technical interpretation as finally `accepted`.

## `lane-receipt.json` schema

Every acquisition/reconciliation lane returns this alongside its artifacts:

```json
{
  "lane_id": "KA-R1",
  "sources_reviewed": [],
  "anchors_reviewed": 0,
  "candidate_nodes": 0,
  "candidate_edges": 0,
  "blocking_ambiguities": [],
  "gate_result": "pass|fail",
  "completed_by": "",
  "completed_at": ""
}
```

`gate_result: fail` is not automatically a wave blocker — see the
conditional-pass pattern in `gate-criteria.md` for how the orchestrator
distinguishes a genuine integration defect from a lane correctly reporting
that its source material itself is incomplete or contested.

## Integration priority when two lanes disagree

The orchestrator, never a subagent, resolves cross-lane disagreement, in
this order:

1. retain both claims;
2. compare source authority and source date;
3. inspect exact source context;
4. check the delivered model or executable artifact;
5. link reviewer comments and acceptance remarks;
6. raise a decision if disagreement remains;
7. never choose silently.
