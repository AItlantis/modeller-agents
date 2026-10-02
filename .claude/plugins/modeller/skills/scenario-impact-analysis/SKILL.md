---
name: scenario-impact-analysis
description: Match a request to a verified scenario, gather aligned section, path, OD assignment, and travel-time evidence, and produce a confidence-tiered impact handoff. This workflow is read-only and never runs a simulation.
metadata:
  version: 0.3.0
  author: AItlantis
---

# Scenario Impact Analysis

Use this reusable workflow when an operator needs to compare an existing scenario with its explicitly linked baseline. The host application owns live chat, data authorization, and viewer actions; this workflow is a bounded analysis adapter, not a chat service. Resolve repository-specific identity rules, query limits, and evidence sources from the selected reference pack before querying.

## Steps

1. Confirm an explicit immutable data-version ID and read-only query capability. Use the selected integration's read-only query adapter; do not reuse a control-plane write transport. Configure the typed scenario matcher separately and keep model credentials outside prompts and returned handoffs.
2. Run `ScenarioImpactWorkflow.analyze(prompt, intervals=..., requested_profile=..., ollaya_profile=..., ollaya_scenario_type=...)`. Retain only catalog-declared scenario IDs, baseline links, intervention metadata, metric availability, and path references. Treat missing legacy facts as unavailable. A user-requested profile takes priority; otherwise validate the typed profile suggestion against `overview`, `path_impact`, and `od_time_series`, defaulting safely to `overview`. Matcher choices remain hints and never authorize reads.
3. Match only among catalog candidates plus `__no_match__`. Accept a scenario only when the returned score distribution is valid, the typed choice agrees with its top score, and the configured score and margin gates pass. If the matcher is unavailable, proceed only for an unambiguous exact scenario-name phrase; otherwise return candidates for clarification. Never fuzzy-match or switch a viewer.
4. Read metrics only for the selected scenario and its explicitly linked baseline. Compare the same section IDs at identical absolute result time windows; do not interpolate, pair interval labels, or claim deltas for unmatched periods. Keep current severity and worsening rankings separate, and require at least two available metrics for each composite.
5. The deterministic controller returns an `analysis_plan` containing fixed read-only step IDs. Prefer authored intervention metadata over model suggestions. Mark path/OD profiles `needs_evidence` unless the catalog advertises required capabilities. For path impact, resolve assignments only through the selected integration's verified crosswalk and follow that pack's identity rules and request caps. Preserve section order and repeated occurrences, report expected/observed sections and coverage, and compare only when the ordered path identity, complete coverage, and exact absolute time window match. Keep derived section-level metrics separate from observed OD travel times. Surface ambiguity rather than selecting an arbitrary identity.
6. Return a structured handoff with source version, selected scenario, explicit baseline, verified facts, current severity, worsening, exact time windows, metadata-backed affected IDs, chosen analysis profile and source, unverified model suggestions clearly labeled, path-level evidence when the gated executor ran, missing evidence, and match-score uncertainty. A plan is not evidence that its steps executed. Do not generate viewer commands or simulation requests.

## Output contract

Return the gathered catalog/metric evidence, `analysis_plan`, and an `analysis_status` of `complete`, `partial`, or `needs_clarification`. When the selected integration advertises every required capability, `path_impact` executes its scoped read-only queries for affected paths, assignment evidence, section-level rollups, and observed OD travel time. Keep section-level calculations separate from OD outcomes, and report missing coverage and absolute-window mismatches. Keep metadata facts, calculations, and model inferences distinct. Typed model choices and scores do not authorize data access or prose generation. This workflow does not host model services and should not be called on every live chat turn.

## Python entry point

```python
from modeller.scenario_impact import ScenarioImpactWorkflow

query_client = selected_reference_pack.read_only_query_client(config)
scenario_matcher = selected_reference_pack.typed_scenario_matcher(config)
handoff = ScenarioImpactWorkflow(query_client, scenario_matcher).analyze(
    user_question,
    ollaya_profile="od_time_series",  # validated hint; user request can override
    ollaya_scenario_type="roadworks",  # unverified unless package metadata confirms it
)
```

The selected integration pack defines endpoint, identity, transport, and secret-injection requirements. Every query stays inside the configured immutable data version and read-only capability. Never put credentials in prompts, packages, or handoffs.
