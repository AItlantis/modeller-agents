---
name: orchestrate
description: Classify a modelling task, identify the source-of-truth repository, and select the correct reusable skill. Use before planning or editing when ownership is not already proven.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Orchestrate

Resolve three things before acting:

1. the user outcome;
2. the source-of-truth repository for that outcome;
3. the reusable skill that should handle the work.

Use `registry/repositories.yml`, repository maps, decisions, and reference packs as evidence. Memory or prior conversation may help locate evidence, but cannot be the authority.

If the task belongs to a repository-local agent, route to that repository instead of recreating that local authority here.

