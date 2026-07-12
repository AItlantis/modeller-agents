---
name: antagonist-review
description: Run an adversarial review of a plan or promoted knowledge before execution. Use for cross-boundary work, sensitive actions, high-risk plans, or any promotion from draft evidence to accepted knowledge.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Antagonist Review

Review the proposal against four lanes:

1. Source boundary: does the target owner actually own the outcome?
2. Evidence quality: are claims proven by source files, decisions, maps, tests, or contracts?
3. Sensitivity: does the proposal leak private data, paths, runtime details, or client/project facts?
4. Architecture fit: does the result belong in this artifact type, or should it stay in source, inbox, a decision, or a contract repo?

Return one of:

- accept;
- accept-with-redaction;
- split;
- keep-in-source;
- draft-to-decision;
- needs-rewrite;
- retire.

