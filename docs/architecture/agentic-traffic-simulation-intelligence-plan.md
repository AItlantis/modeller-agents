# Agentic Traffic Simulation Intelligence — Implementation Plan

**Status:** Proposed; reviewed by 6.1-Sol, pending maintainer decisions  
**Version:** 0.1 · **Date:** 2026-10-08  
**Scope:** First exported-results PoC and its path to governed agentic investigation

## 1. Objective

Build an evidence-led investigation capability that moves from a user’s transport question to verified simulation evidence. Deterministic services calculate and validate metrics. The agent selects investigations, challenges hypotheses, and explains supported findings. It does not calculate engineering KPIs from prose, issue unrestricted database queries, or present hypotheses as facts.

The PoC reads existing exported results. It does not modify Aimsun models or launch simulations.

## 2. Ownership and boundaries

- **Llumen** owns the decision interface, user context, and governed access.
- **Testudo** owns scenario analytics, network/path investigation, evidence generation, and technical visualization. Its analytics service may be a separately packaged domain module with a stable API.
- **modeller-agents** owns reusable investigation methods, bounded orchestration, tool policies, and workflow/evidence gates. It must not become a second traffic-analytics authority.
- **Aimsun / aimsun-psp** remains the authority for models, assignment, simulation, and technical outputs.
- **Canonical data** begins as versioned, normalized exported snapshots. Do not introduce a separate database platform until the PoC demonstrates that the snapshot model is inadequate.

The Oct 3, 2026 scenario-impact implementation in modeller-agents is a prototype and compatibility reference. Preserve its useful behavior—read-only access, explicit baselines, path/OD evidence, exact time-window alignment, ambiguity handling, and partial results—while deciding where each algorithm belongs. Do not maintain two authoritative implementations after migration.

## 3. Delivery sequence

### Phase 0 — Reconnaissance and migration map

Inventory recent and legacy code, skills, adapters, tests, contracts, and consumers. Mark each **keep**, **adapt/migrate**, or **deprecate**, with an owner and replacement path. Record local changes before any edits. Preserve repository governance, workflow gates, and release evidence where they continue to protect boundaries or reproducibility.

**Gate:** analytics ownership, initial API boundary, and migration approach are recorded before expanding the prototype.

### Phase 1 — Data readiness and Scenario Assessment

Define a versioned `ScenarioSnapshot`, `SectorDefinition`, `AssessmentConfiguration`, and `ScenarioAssessment`. Ingestion/readiness must establish source version, run validity, network and OD identities, coordinate system, units, time windows, and metric availability before calculating findings.

Produce one-scenario results for network context, key corridors and junctions, demand, path structure, supported traffic conditions, critical locations, provenance, quality status, and evidence references. Missing inputs return explicit `unavailable` or `partial` states. Assessment is useful independently of comparison.

**Acceptance:** an exported Actual scenario yields a deterministic, evidence-linked assessment; rerunning the same snapshot and configuration yields the same metrics and provenance.

### Phase 2 — Comparability and flow/path comparison

Before calculating deltas, validate network correspondence, OD mapping, analysis periods, assignment methods, demand, geometry/regulation changes, and run quality. Stop, transform with disclosed mapping, or mark results partial when correspondence is unsafe. Never interpret a missing identifier as zero flow.

Implement configurable absolute/relative flow screens, method-specific condition indicators, OD demand/path-share decomposition, route-family matching, and path-to-link reconciliation where path data is complete. Initial thresholds are provisional and require calibration against reviewed cases. For stochastic results, report replication coverage and uncertainty before making impact claims.

**Acceptance:** comparable scenarios produce reproducible deltas and attribution; incompatible scenarios block dependent conclusions with a structured reason.

### Phase 3 — Impact network and conditions

Represent impact as a graph containing direct changes, redistribution corridors, alternative routes, upstream/downstream influence, and boundary checks. Preserve disconnected components linked by OD/path relationships. A display polygon is derived from this graph, not the primary analytical object.

Measure conditions on links, approaches, corridors, routes, and defined subpaths using only indicators supported by the simulation method. For static assignment, label cost/V/C/speed proxies accurately; do not describe them as observed density or queues. Check upstream entry flow and path changes before treating lower downstream flow as improvement.

**Acceptance:** each impact-network edge states its relation type, calculation method, evidence, assumptions, and uncertainty. Tests include upstream restriction and local-road shunt cases.

### Phase 4 — Bounded investigation and evidence completion

Add one orchestrator that calls typed analytical APIs. Record investigation state, hypothesis, required evidence, tool/version, validated result, and next action. Enforce allowed tools, read-only scope, processing and iteration budgets, and deterministic completion checks. Reaching a limit returns `PARTIAL`; missing essential data or failed comparability returns `BLOCKED`.

Every quantitative claim links to a stable calculation/data reference. Label statements as calculated, derived, hypothesis, or interpretation. OD/path association establishes a supported relationship, not by itself a causal mechanism. Treat external text and tool-returned content as data, never as instructions.

### Phase 5 — Evidence-linked interface and dynamic extension

Expose findings to Testudo and Llumen through stable evidence references for maps, charts, and synchronized scenario views. Add trajectories, queue propagation, vehicle replay, and animation only after data availability, identity alignment, performance budgets, and validation are demonstrated.

## 4. GeoAI adoption gate

Evaluate GeoAI behind an optional Testudo spatial adapter for one concrete vector/raster processing or visualization use case. Compare it with simpler GIS tooling, and measure reproducibility, install size, dependency conflicts, runtime/resource cost, and packaging impact before adoption. GeoAI is not presumed to provide traffic assignment or OD/path analytics, and must not become a required dependency of modeller-agents.

## 5. Verification cases

Use independently checked results for: unchanged scenarios; capacity reduction; increased demand; a new parallel route; upstream restriction; local-road shunt; missing path exports; changed link identifiers; and incomplete/uncertain replications. Verify explicit partial/blocked outcomes, units, time alignment, path-flow reconciliation tolerances, and provenance. LLM wording is not a test oracle.

## 6. Decisions to settle before implementation expands

1. Confirm Testudo (or a Testudo-owned domain package) as owner of deterministic algorithms and contracts.
2. Define canonical link/junction/OD identity and cross-network/path-family mapping rules.
3. Select the first exported-result format and required minimum data capabilities.
4. Approve static-assignment KPI definitions, thresholds, reconciliation tolerances, and stochastic-run treatment.
5. Specify the analytics API and evidence/provenance schema versions.
6. Decide which legacy surfaces to retire only after consumer mapping and parity evidence.
7. Decide whether the GeoAI use-case gate is met before adding its dependency.

## 7. Implementation ownership

Use 6.1-Sol for independent plan and design review. Use Luna for bounded implementation work after the ownership and contract gates are settled. Keep each implementation task scoped to an owning repository and require its declared verification evidence before advancing.
