# V-Cycle Vigilance and Human Review

## 1. Principle

Vigilance is an executable workflow policy, not a note attached to the end of a report.

It determines:

- allowed and forbidden AI actions;
- required evidence;
- required human role;
- blocking review conditions;
- review invalidation after material change.

## 2. Vigilance levels

| Level | Meaning | Required human control |
|---|---|---|
| `V0` | formatting, search, summarization | review before external use |
| `V1` | consistency, traceability, comparison, diagnosis | expert validates findings |
| `V2` | generated requirements, design, tests, code | qualified reviewer mandatory |
| `V3` | scope, priority, risk, GO/NO-GO recommendations | named approver mandatory |
| `V4` | deployment, acceptance, contractual or external effect | explicit signatory/action approval |

## 3. Human-only decisions

The runtime must block agent approval of:

- business-need baseline;
- scope and prioritization;
- architecture selection;
- risk criticality;
- code acceptance;
- regression-scope reduction;
- campaign GO/NO-GO;
- acceptance and reservation closure;
- deployment/cutover and rollback;
- critical-incident disposition;
- contractual publication.

## 4. Review receipt

A human gate advances only with a valid receipt bound to the current artifact digest.

```yaml
review_id: review-...
run_id: run-...
stage_id: system-validation
artifact_digest: sha256:...
review_type: approval
reviewer:
  id: human-...
  role: quality-lead
  actor_type: human
decision: approved | approved-with-reservations | changes-requested | rejected
reservations: []
accepted_risks: []
reviewed_at: ...
```

## 5. Invalidation

A receipt is invalidated when a material change affects scope, requirement meaning, architecture, interfaces, risk, acceptance criteria, tested behavior, external action or the approved artifact digest.

## 6. Source and tool vigilance

Before project data enters an AI tool, verify:

- tool approval;
- compatible data classification;
- minimal permission scope;
- known retention and destination;
- allowed external transmission;
- source and licence obligations.

## 7. Escalation triggers

Human escalation is mandatory when sources conflict, confidence is low on a material decision, sensitive data may be exposed, security/compliance is affected, a GO/NO-GO criterion is ambiguous, production or contractual action is requested, or a critical incident occurs.

## 8. Measurement

Use-case estimates must be replaced progressively by measured duration, correction/rework rate and defect/omission evidence over comparable occurrences. No estimated productivity range can authorize automation by itself.
