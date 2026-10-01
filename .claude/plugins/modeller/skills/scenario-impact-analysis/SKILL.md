---
name: scenario-impact-analysis
description: Match a request to a verified Testudo scenario, gather aligned section, path, OD assignment, and subpath evidence, and produce a confidence-tiered impact handoff. This workflow is read-only and never runs a simulation.
metadata:
  version: 0.3.0
  author: AItlantis
---

# Scenario Impact Analysis

Use this reusable workflow when an operator needs to compare an existing Testudo scenario with its explicitly linked baseline. Testudo owns live chat, package authorization, and viewer actions; this workflow is a bounded analysis adapter, not a chat service.

## Steps

1. Confirm an explicit accepted Testudo package-version ID and read-only query capability. Construct `TestudoScenarioQueryClient` with `activation=true`; never reuse the control-plane POST transport. Configure an `OllayaScenarioMatcher` for the operator's typed decision endpoint with `activation=true`; keep model keys outside prompts and returned handoffs.
2. Run `ScenarioImpactWorkflow.analyze(prompt, intervals=..., requested_profile=..., ollaya_profile=..., ollaya_scenario_type=...)`. The workflow reads `catalog()` and retains only its declared scenario IDs, baseline links, intervention metadata, metric availability, and path references. Treat missing legacy intervention facts as unavailable. A user-requested profile takes priority; otherwise the controller validates a typed profile suggestion against `overview`, `path_impact`, and `od_time_series`, defaulting safely to `overview` when no valid suggestion exists. In live Testudo chat, one Ollaya `/api/decide` call returns typed intent, scenario-type, and analysis-profile choices; those choices remain hints and never authorize reads. Direct skill callers may pass a profile/type hint explicitly, which the deterministic controller still validates.
3. The workflow asks Ollaya to choose from the catalog candidates plus `__no_match__`. It accepts a scenario only when the returned full score distribution is valid, the typed choice agrees with its top score, the top score is at least 0.80, and its lead is at least 0.15. If Ollaya is unavailable, only an unambiguous exact scenario-name phrase can proceed; otherwise return candidates for clarification. Never fuzzy-match or switch a viewer.
4. Read metrics only for the selected scenario and its explicitly linked baseline. Compare the same section IDs at identical absolute result time windows; do not interpolate, pair interval labels, or claim deltas for unmatched periods. Current severity and worsening remain separate rankings, with at least two available metrics required for each composite.
5. `ScenarioAnalysisController` returns a deterministic `analysis_plan` containing only fixed read-only step IDs. It resolves scenario type from authored package metadata first; an Ollaya type suggestion is explicitly unverified. It marks path/OD profiles `needs_evidence` unless the package catalog advertises the required scoped capabilities and OD metrics. For path impact, resolve Aimsun subpaths to path-assignment routes only through the catalog crosswalk; do not equate an Aimsun subpath OID with Testudo's generated `route_id`. For the selected ordered path, query section delay at one interval and sum the returned section values. Preserve order and repeated section occurrences, report expected/observed sections and coverage, and compare against baseline only when the ordered section sequence and returned absolute `time_window` match and both sides have complete coverage. If the absolute window is unavailable, return no delta. Label this as a derived section-delay rollup, never as observed OD journey time. Query `MISUBPATH` journey-time rows separately and call them observed subpath travel-time evidence only after an unambiguous subpath/path/OD match and exact absolute-window alignment.
6. Return a structured handoff with source version, selected scenario, explicit baseline, verified facts, current severity, worsening, exact time windows, affected IDs declared by package metadata, chosen analysis profile and its source, the unverified Ollaya scenario-type suggestion beside package-verified types, path-level evidence when the gated executor ran, the analysis plan, missing evidence, and match-score uncertainty. A plan is not evidence that its steps were executed: `path_impact` is `complete` only when its crosswalk, path assignment, exact-window delay, and subpath journey-time evidence all return; `od_time_series` remains `partial` until its allowlisted executor returns OD-level results. Do not generate viewer commands or simulation requests.

## Output contract

Return the gathered catalog/metric evidence, `analysis_plan`, and an `analysis_status` of `complete`, `partial`, or `needs_clarification`. When the catalog advertises every required capability, `path_impact` executes scoped GET-only queries for affected paths, OD assignment evidence, section-delay rollups, and observed subpath journey time. A selected path's section-delay total remains separate from observed subpath travel time, with missing coverage and absolute-window mismatch reported explicitly. `od_time_series` remains plan-only until Testudo publishes package-version-scoped OD travel-time and delay rows with exact clock windows and the matching executor is implemented. Keep package metadata facts, calculated comparisons, and model inferences separate. Ollaya returns choices and scores only; prose generation remains outside this workflow. This workflow does not host Ollama/Ollaya and must not be called on every live chat turn.

## Python entry point

```python
from modeller.adapters.ollaya_scenario_match import OllayaScenarioConfig, OllayaScenarioMatcher
from modeller.adapters.testudo_scenario_query import ScenarioQueryConfig, TestudoScenarioQueryClient
from modeller.scenario_impact import ScenarioImpactWorkflow

testudo = TestudoScenarioQueryClient(ScenarioQueryConfig(
    base_url="https://testudo.example",
    version_id=accepted_version_id,
    capability_token=read_only_capability,
    activation=True,
))
ollaya = OllayaScenarioMatcher(OllayaScenarioConfig(
    base_url="https://ollaya.example",
    model="laya",
    api_key=ollaya_api_key,
    activation=True,
))
handoff = ScenarioImpactWorkflow(testudo, ollaya).analyze(
    user_question,
    ollaya_profile="od_time_series",  # validated hint; user request can override
    ollaya_scenario_type="roadworks",  # unverified unless package metadata confirms it
)
```

For local development, loopback HTTP URLs are accepted. Remote endpoints must use HTTPS. The query client also exposes GET-only `subpath_crosswalk(scenario_id)`, `od_routes(scenario_id, origin, destination, ...)`, `path_delay(scenario_id, section_ids, interval)`, and `subpath_metrics(scenario_id, subpath_ids, intervals)` calls. Each call stays inside the configured package version and read-only capability. Keep `read_only_capability` and `ollaya_api_key` in the host's secret injection mechanism; never put them in the prompt, package, or handoff.
