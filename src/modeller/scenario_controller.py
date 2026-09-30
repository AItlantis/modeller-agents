"""Deterministic, read-only policy controller for scenario-impact workflows.

Ollaya may recommend a scenario type and analysis profile. This module treats
those as hints: it validates the profile against a fixed allowlist, resolves
scenario and baseline IDs from the Testudo catalog, and declares only bounded
read operations whose prerequisites are advertised by that catalog.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PROFILES = ("overview", "path_impact", "od_time_series")
SCENARIO_TYPES = (
    "roadworks", "incident", "lane_closure", "geometry_change",
    "speed_change", "other",
)
PROFILE_STEPS = {
    "overview": (
        "read_section_metrics",
        "align_linked_baseline_windows",
        "summarize_observed_changes",
    ),
    "path_impact": (
        "resolve_event_footprint",
        "query_affected_paths",
        "aggregate_impacted_od_pairs",
        "summarize_path_and_demand_coverage",
    ),
    "od_time_series": (
        "resolve_event_footprint",
        "query_affected_paths",
        "aggregate_impacted_od_pairs",
        "query_od_travel_time_and_delay",
        "align_same_od_clock_intervals",
        "compare_linked_baseline_and_summarize_trend",
    ),
}

# These keys form the explicit capability contract expected from a future
# package-version-scoped Testudo catalog. Missing keys are always false.
PROFILE_CAPABILITIES = {
    "path_queries": "query_affected_paths",
    "od_pair_aggregation": "aggregate_impacted_od_pairs",
    "od_travel_time": "query_od_travel_time_and_delay",
    "od_interval_metrics": "align_same_od_clock_intervals",
}


class ScenarioAnalysisController:
    """Turn model suggestions and verified catalog data into a bounded plan.

    The controller does not call Ollaya, access Testudo, resolve geometry, or
    execute a query. Its caller supplies the verified catalog and optional
    Ollaya recommendations, then may execute only the returned allowlisted
    steps through an explicitly scoped read-only client.
    """

    def plan(
        self,
        catalog: Mapping[str, Any],
        scenario_id: str | int,
        *,
        ollaya_profile: str | None = None,
        requested_profile: str | None = None,
        ollaya_scenario_type: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(catalog, Mapping):
            return self._blocked("invalid_catalog", ["verified Testudo catalog"])
        scenarios = catalog.get("scenarios")
        if not isinstance(scenarios, list):
            return self._blocked("invalid_catalog", ["scenario roster"])
        selected = next((row for row in scenarios
                         if isinstance(row, Mapping)
                         and str(row.get("scenario_id")) == str(scenario_id)), None)
        if selected is None:
            return self._blocked("unverified_scenario", ["scenario ID present in verified catalog"])

        profile, profile_source, profile_error = self._profile(
            requested_profile=requested_profile,
            ollaya_profile=ollaya_profile,
        )
        facts = selected.get("analysis") if isinstance(selected.get("analysis"), Mapping) else {}
        interventions = facts.get("interventions", [])
        if not isinstance(interventions, list):
            interventions = []
        verified_types = sorted({
            str(item.get("type")) for item in interventions
            if isinstance(item, Mapping) and item.get("type") in SCENARIO_TYPES
        })
        scenario_type = self._scenario_type(verified_types, ollaya_scenario_type)
        baseline_id = self._baseline_id(facts, selected, scenarios)
        footprint = self._event_footprint(interventions)
        capabilities = catalog.get("analysis_capabilities")
        capabilities = capabilities if isinstance(capabilities, Mapping) else {}
        available_metrics = catalog.get("available_metrics")
        available_metrics = sorted({
            str(metric) for metric in available_metrics
            if isinstance(metric, str) and metric in {"speed", "delay", "density"}
        }) if isinstance(available_metrics, list) else []

        missing: list[str] = []
        if profile_error:
            missing.append(profile_error)
        if baseline_id is None:
            missing.append("explicit linked baseline scenario")
        if profile == "overview":
            if not available_metrics:
                missing.append("available section metrics")
        else:
            if facts.get("baseline_role") != "intervention" or baseline_id == str(selected.get("scenario_id")):
                missing.append("selected intervention scenario with a distinct explicit baseline")
            if not (footprint["section_ids"] or footprint["path_ids"]):
                if not footprint["locations"]:
                    missing.append("authored event location or affected section/path IDs")
                elif capabilities.get("event_location_lookup") is not True:
                    missing.append("verified event-location-to-network lookup")
            for capability, step in PROFILE_CAPABILITIES.items():
                if step in PROFILE_STEPS[profile] and capabilities.get(capability) is not True:
                    missing.append(f"Testudo capability: {capability}")
            if profile == "od_time_series":
                od_metrics = catalog.get("available_od_metrics")
                od_metrics = {item for item in od_metrics if isinstance(item, str)} \
                    if isinstance(od_metrics, list) else set()
                for metric in ("travel_time", "delay"):
                    if metric not in od_metrics:
                        missing.append(f"OD-level {metric} results by scenario and interval")
                if "aligned_od_clock_windows" not in capabilities or capabilities.get("aligned_od_clock_windows") is not True:
                    missing.append("exact OD clock-window alignment support")

        missing = list(dict.fromkeys(missing))
        return {
            "controller": "modeller-agents.scenario-analysis.v1",
            "status": "ready_to_execute" if not missing else "needs_evidence",
            "scenario_id": str(selected.get("scenario_id")),
            "profile": profile,
            "profile_source": profile_source,
            "scenario_type": scenario_type,
            "baseline_scenario_id": baseline_id,
            "verified_event_footprint": footprint,
            "available_section_metrics": available_metrics,
            "section_composite_available": len(available_metrics) >= 2,
            "steps": [
                {"id": step, "mode": "read_only"}
                for step in PROFILE_STEPS[profile]
            ],
            "query_limits": {
                "max_scenarios": 2,
                "max_intervals": 120,
                "max_affected_sections": 1000,
                "max_affected_paths": 1000,
                "max_od_pairs": 500,
            },
            "missing_evidence": missing,
            "safety_rules": [
                "Only query the selected scenario and its explicitly linked baseline.",
                "Compare only identical OD IDs and exact absolute time windows.",
                "Do not interpolate unmatched intervals or infer missing event facts.",
                "Keep model suggestions separate from verified package facts and calculations.",
                "Never execute a simulation or mutate package/model data.",
            ],
        }

    @staticmethod
    def _profile(
        *, requested_profile: str | None, ollaya_profile: str | None,
    ) -> tuple[str, str, str | None]:
        if requested_profile is not None:
            if requested_profile not in PROFILES:
                return "overview", "safe_default", "requested analysis profile is not supported"
            return requested_profile, "user_request", None
        if ollaya_profile is not None:
            if ollaya_profile not in PROFILES:
                return "overview", "safe_default", "Ollaya suggested an unsupported analysis profile"
            return ollaya_profile, "ollaya_recommendation", None
        return "overview", "safe_default", None

    @staticmethod
    def _scenario_type(verified_types: list[str], ollaya_type: str | None) -> dict[str, Any]:
        if verified_types:
            return {"types": verified_types, "source": "package_metadata", "verified": True}
        if ollaya_type in SCENARIO_TYPES:
            return {"types": [ollaya_type], "source": "ollaya_suggestion", "verified": False}
        return {"types": [], "source": "unavailable", "verified": False}

    @staticmethod
    def _baseline_id(
        facts: Mapping[str, Any], selected: Mapping[str, Any], scenarios: list[Any],
    ) -> str | None:
        if facts.get("baseline_role") == "baseline":
            return str(selected.get("scenario_id"))
        linked = facts.get("baseline_scenario_id")
        if (facts.get("baseline_role") == "intervention" and linked is not None
                and any(isinstance(row, Mapping)
                        and str(row.get("scenario_id")) == str(linked) for row in scenarios)):
            return str(linked)
        return None

    @staticmethod
    def _event_footprint(interventions: list[Any]) -> dict[str, Any]:
        fields = ("section_ids", "path_ids", "locations")
        collected: dict[str, list[Any]] = {field: [] for field in fields}
        limits = {"section_ids": 1000, "path_ids": 1000, "locations": 20}
        truncated: set[str] = set()
        for row in interventions:
            if not isinstance(row, Mapping):
                continue
            for source, target in (
                ("affected_section_ids", "section_ids"),
                ("affected_path_ids", "path_ids"),
                ("location", "locations"),
            ):
                value = row.get(source)
                values = value if source != "location" and isinstance(value, list) else [value]
                for item in values:
                    if len(collected[target]) >= limits[target]:
                        truncated.add(target)
                        break
                    if target == "locations" and isinstance(item, Mapping):
                        value_to_add: Any = dict(item)
                    elif isinstance(item, (str, int)) and not isinstance(item, bool):
                        text = str(item).strip()
                        value_to_add = text if text and len(text) <= 256 else None
                    else:
                        value_to_add = None
                    if value_to_add is not None and value_to_add not in collected[target]:
                        collected[target].append(value_to_add)
        return {**collected, "truncated_fields": sorted(truncated)}

    @staticmethod
    def _blocked(reason: str, missing: list[str]) -> dict[str, Any]:
        return {
            "controller": "modeller-agents.scenario-analysis.v1",
            "status": "needs_evidence",
            "reason": reason,
            "steps": [],
            "missing_evidence": missing,
        }
