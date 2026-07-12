---
name: source-boundary-check
description: Verify that a proposed write, backend call, or knowledge promotion targets the repository that owns the outcome. Use before any cross-repository write or sensitive action.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Source Boundary Check

Answer these questions before writes or backend invocation:

1. What outcome is being changed?
2. Which repository owns that outcome?
3. Is the target path inside that repository?
4. Is the target artifact authoritative or generated?
5. Does the change duplicate implementation, contracts, memory, or durable knowledge from another owner?
6. Is confirmation or antagonist review required?

Block the action if the target repository does not own the outcome.

