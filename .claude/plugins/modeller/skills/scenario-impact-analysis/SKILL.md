---
name: scenario-impact-analysis
description: Gather a Testudo scenario catalog and aligned section metrics, check evidence, and produce a structured scenario impact handoff. This workflow is read-only and never runs a simulation.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Scenario Impact Analysis

Use this reusable workflow when an operator needs to compare an existing Testudo scenario with its explicitly linked baseline. Testudo owns live chat, package authorization, and viewer actions; this workflow is a bounded analysis adapter, not a chat service.

## Steps

1. Confirm an explicit accepted Testudo package-version ID and read-only query capability. Construct `TestudoScenarioQueryClient` with `activation=true`; never reuse the control-plane POST transport. Configure an `OllayaScenarioMatcher` for the operator's typed decision endpoint with `activation=true`; keep model keys outside prompts and returned handoffs.
2. Run `ScenarioImpactWorkflow.analyze(prompt, intervals=..., requested_profile=..., ollaya_profile=..., ollaya_scenario_type=...)`. The workflow reads `catalog()` and retains only its declared scenario IDs, baseline links, intervention metadata, metric availability, and path references. Treat missing legacy intervention facts as unavailable. A user-requested profile takes priority; otherwise the controller validates a typed profile suggestion from its caller against `overview`, `path_impact`, and `od_time_series`, defaulting safely to `overview` when there is no suggestion. The current `OllayaScenarioMatcher.match()` returns only the scenario choice; a caller must not treat absent profile classification as if Ollaya had produced one.
3. The workflow asks Ollaya to choose from the catalog candidates plus `__no_match__`. It accepts a scenario only when the returned full score distribution is valid, the typed choice agrees with its top score, the top score is at least 0.80, and its lead is at least 0.15. If Ollaya is unavailable, only an unambiguous exact scenario-name phrase can proceed; otherwise return candidates for clarification. Never fuzzy-match or switch a viewer.
4. Read metrics only for the selected scenario and its explicitly linked baseline. Compare the same section IDs at identical absolute result time windows; do not interpolate, pair interval labels, or claim deltas for unmatched periods. Current severity and worsening remain separate rankings, with at least two available metrics required for each composite.
5. `ScenarioAnalysisController` returns a deterministic `analysis_plan` containing only fixed read-only step IDs. It resolves scenario type from authored package metadata first; an Ollaya type suggestion is explicitly unverified. It marks path/OD profiles `needs_evidence` unless the package catalog advertises the required scoped capabilities and OD metrics. Never treat path references alone as OD travel-time evidence.
6. Return a structured handoff with source version, selected scenario, explicit baseline, verified facts, current severity, worsening, exact time windows, affected IDs declared by package metadata, the analysis plan, missing evidence, and match-score uncertainty. A plan is not evidence that its steps were executed: deeper profiles remain `partial` until an allowlisted executor returns their results. Do not generate viewer commands or simulation requests.

## Output contract

Return the gathered catalog/metric evidence, `analysis_plan`, and an `analysis_status` of `complete`, `partial`, or `needs_clarification`. The plan names one profile and its bounded steps; it does not execute path or OD queries. In particular, `od_time_series` requires Testudo to publish package-version-scoped OD travel-time and delay rows with exact clock windows, plus path-to-OD lookup capability. Keep package metadata facts, calculated comparisons, and model inferences separate. Ollaya returns choices and scores only; prose generation remains outside this workflow. This workflow does not host Ollama/Ollaya and must not be called on every live chat turn.

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

For local development, loopback HTTP URLs are accepted. Remote endpoints must use HTTPS. Keep `read_only_capability` and `ollaya_api_key` in the host's secret injection mechanism; never put them in the prompt, package, or handoff.
