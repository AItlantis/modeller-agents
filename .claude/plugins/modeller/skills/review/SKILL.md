---
name: review
description: Review a diff, plan, or scaffold for bugs, boundary drift, missing verification, and missing tests. Use after implementation and before handoff.
metadata:
  version: 0.1.0
  author: AItlantis
domain_affinity:
  mode: explicit
  domains:
    - accessibility
---

# Review

Prioritize findings by risk:

1. source-boundary violations;
2. behavior bugs or incomplete implementation;
3. missing verification for the changed surface;
4. sensitivity or private-data leakage;
5. stale docs, manifests, or registry entries.

Lead with actionable findings. If no findings are found, state the remaining verification limits.
