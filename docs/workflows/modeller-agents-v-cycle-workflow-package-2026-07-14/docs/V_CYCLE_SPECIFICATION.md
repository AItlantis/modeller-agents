# V-Cycle Workflow Specification

## 1. Architecture decision

Add `v-cycle` as a first-class workflow family in `modeller-agents`.

It is not one rigid linear workflow. It is a selectable stage catalog with prerequisites, paired verification links, traceability and human gates.

```text
modeller-agents
  owns: workflow family, reusable skill, stage contracts, vigilance policy, schemas and gates

source repositories
  own: repository-local agents, implementation, local tests and local technical facts

modelling-knowledge
  may own: curated explanatory methodology, never executable workflow logic
```

## 2. User interaction

The user may ask for the whole cycle or one stage:

- clarify the business need;
- review functional requirements;
- compare architecture options;
- prepare detailed design;
- implement an approved design;
- prepare or review unit/integration/system tests;
- prepare acceptance;
- prepare deployment and rollback;
- produce operations analysis or REX;
- support transversal project governance.

The Companion resolves the internal stage ID and presents prerequisites, outputs, paired verification and required human roles.

## 3. Stage catalog

### Descending branch

1. `opportunity-analysis`
2. `needs-analysis`
3. `functional-specification`
4. `general-design`
5. `detailed-design`

### Point of the V

6. `implementation`

### Ascending branch

7. `unit-testing`
8. `integration-testing`
9. `system-validation`
10. `acceptance-qualification`

### Post-cycle

11. `deployment`
12. `operations-rex`

### Transversal

13. `project-governance`

## 4. V-pair contract

```text
needs-analysis             <-> acceptance-qualification
functional-specification   <-> system-validation
general-design              <-> integration-testing
detailed-design             <-> unit-testing
implementation              <-> executable verification evidence
opportunity-analysis        <-> operations-rex and measured value
```

Every stage records upstream inputs, downstream obligations, paired-stage links and trace gaps.

## 5. Invocation modes

### `full`

Runs or governs the complete V-cycle and pauses at human gates.

### `stage`

Runs only the requested stage. A prerequisite audit classifies inputs as:

```text
available | missing | stale | contradictory | not-applicable
```

The AI must not invent missing baselines. It may draft a candidate, expose a gap or request a confirmed assumption.

### `paired-review`

Read-only by default. Checks alignment between paired artifacts, for example functional requirements against system-validation evidence.

## 6. Common stage lifecycle

```text
intake -> recon -> draft -> machine-check -> awaiting-human-review
       -> approved | rework | rejected -> closed
```

No AI or subagent may set `approved`.

## 7. Gate types

| Gate | Purpose | Authority |
|---|---|---|
| Machine | schema, traceability, tests, currency, coverage | deterministic tool/runtime |
| Expert review | domain correctness, feasibility, completeness, interpretation | qualified human |
| Decision | scope, architecture, risk, GO/NO-GO, acceptance, cutover | accountable human |

## 8. Stage use cases and human controls

| Stage | AI support | Human-owned decision |
|---|---|---|
| Opportunity | research, scenarios, sensitivity, drafting | proceed / stop and business-case approval |
| Needs | synthesize workshops, find implicit/conflicting needs | needs baseline |
| Functional specification | extract/check requirements, dependencies, testability | wording, scope, prioritization |
| General design | compare options, impacts, interfaces, risk draft | architecture compromise and risk rating |
| Detailed design | specifications, diagrams, traceability, test preparation | technical feasibility and model approval |
| Implementation | code/config generation, explanation, refactoring, documentation | peer review and code acceptance |
| Unit testing | test generation, edge cases, diagnosis | relevance and test adoption |
| Integration testing | scenarios, degraded modes, automation, anomaly triage | scope and root-cause confirmation |
| System validation | coverage, regression priorities, campaign synthesis | regression scope and GO/NO-GO |
| Acceptance | user cases, anomaly assistance, draft minutes/reservations | sign-off and reservation closure |
| Deployment | checklists, risks, rollback preparation | cutover and rollback |
| Operations/REX | trends, support classification, REX draft | critical escalation and publication |
| Governance | planning, reporting, risks, minutes, document checks | estimates, ratings, decisions and single truth |

## 9. Required artifacts

Every non-trivial run produces or references:

```text
BRIEF.md
RECON.md
workflow plan
stage artifact
v-trace.json
machine evidence
human-review receipt
handoff
```

Stage-only work does not create unrelated stage artifacts.

## 10. Traceability

`v-trace.json` links:

```text
need -> requirement -> design -> implementation -> test case
     -> test result -> acceptance evidence -> human decision
```

Gaps are allowed only when explicit.

## 11. Estimated gains

The source document's percentages are advisory estimates at task level, not project commitments. Runtime metadata may preserve them for prioritization, but generalization requires measured before/after evidence.

```yaml
benefit:
  estimate_status: advisory
  baseline_measurement: null
  assisted_measurement: null
  generalization_decision: pending
```

## 12. Mandatory AI disclosure

Every deliverable records whether AI was used, for which activities, with which approved tool, and whether human review is complete.
