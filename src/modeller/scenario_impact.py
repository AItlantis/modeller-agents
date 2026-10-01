"""Read-only orchestration for Testudo scenario impact analysis."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from modeller.adapters.ollaya_scenario_match import (
    NO_MATCH_CHOICE,
    OllayaScenarioMatcher,
    ScenarioDecisionError,
)
from modeller.adapters.testudo_scenario_query import (
    ScenarioQueryError,
    TestudoScenarioQueryClient,
)
from modeller.path_impact import execute_path_impact
from modeller.scenario_controller import ScenarioAnalysisController

METRICS = ("speed", "delay", "density")


class ScenarioImpactWorkflow:
    """Gather catalog-backed scenario, metric, and gated path-impact evidence."""

    def __init__(
        self,
        testudo: TestudoScenarioQueryClient,
        ollaya: OllayaScenarioMatcher,
        controller: ScenarioAnalysisController | None = None,
    ) -> None:
        self._testudo = testudo
        self._ollaya = ollaya
        self._controller = controller or ScenarioAnalysisController()

    def analyze(
        self,
        prompt: str,
        intervals: list[int] | None = None,
        *,
        requested_profile: str | None = None,
        ollaya_profile: str | None = None,
        ollaya_scenario_type: str | None = None,
    ) -> dict[str, Any]:
        catalog = self._testudo.catalog()
        scenarios = catalog.get("scenarios")
        if not isinstance(scenarios, list):
            raise ScenarioQueryError("Testudo catalog did not contain a scenario roster")
        if not scenarios:
            return {"analysis_status": "needs_clarification", "reason": "no_scenarios", "candidates": []}
        try:
            decision = self._ollaya.match(prompt, scenarios)
        except ScenarioDecisionError:
            exact = _exact_name_matches(prompt, scenarios)
            if len(exact) != 1:
                return {
                    "analysis_status": "needs_clarification",
                    "reason": "ollaya_unavailable_exact_match_required",
                    "candidates": _candidate_summaries(scenarios),
                    "missing_evidence": ["Ollaya typed scenario decision"],
                }
            decision = {
                "status": "matched", "available": False,
                "scenario_id": exact[0]["scenario_id"], "model_match_score": None,
                "method": "exact_scenario_name",
            }
        if decision.get("status") != "matched":
            return {
                "analysis_status": "needs_clarification",
                "reason": "scenario_match_ambiguous_or_no_match",
                "candidates": decision.get("candidates") or _candidate_summaries(scenarios),
                "model_match_score": decision.get("model_match_score"),
                "score_label": "model match score",
            }
        selected = next((item for item in scenarios
                         if str(item.get("scenario_id")) == str(decision.get("scenario_id"))), None)
        if selected is None:
            return {"analysis_status": "needs_clarification", "reason": "unverified_scenario_choice",
                    "candidates": _candidate_summaries(scenarios)}

        facts = selected.get("analysis") if isinstance(selected.get("analysis"), Mapping) else None
        baseline_id = None
        if facts and facts.get("baseline_role") == "baseline":
            baseline_id = str(selected["scenario_id"])
        elif facts and facts.get("baseline_role") == "intervention":
            linked = facts.get("baseline_scenario_id")
            if linked is not None and any(str(item.get("scenario_id")) == str(linked) for item in scenarios):
                baseline_id = str(linked)

        selected_id = str(selected["scenario_id"])
        requested_ids = [selected_id]
        if baseline_id is not None and baseline_id != selected_id:
            requested_ids.append(baseline_id)
        analysis_plan = self._controller.plan(
            catalog,
            selected_id,
            requested_profile=requested_profile,
            ollaya_profile=ollaya_profile,
            ollaya_scenario_type=ollaya_scenario_type,
        )
        try:
            metrics = self._testudo.metrics([int(value) for value in requested_ids], intervals)
        except (ScenarioQueryError, ValueError):
            return _partial_without_metrics(selected, facts, baseline_id, decision, analysis_plan)
        rows = metrics.get("rows") if isinstance(metrics.get("rows"), list) else []
        current_rows = [row for row in rows if str(row.get("scenario_id")) == selected_id]
        current_ranking = rank_sections(_aggregate_current(current_rows))
        aligned = {"rows": [], "unmatched_count": len(current_rows), "interpolation": False}
        worsening = {
            "available": False, "reason": "no_explicit_baseline", "metrics": [],
            "sections": [], "metric_rankings": {},
        }
        if baseline_id is not None and baseline_id != selected_id:
            aligned = align_rows(rows, selected_id, baseline_id)
            worsening = rank_sections(_aggregate_aligned(aligned["rows"]), delta=True)
        interventions = facts.get("interventions", []) if facts else []
        observed = observed_effective_periods(current_rows, interventions)
        current_period_rows = split_effective_period_rows(current_rows, interventions)
        aligned_period_rows = split_effective_period_rows(aligned["rows"], interventions)
        period_analysis = {
            "available": bool(current_period_rows),
            "reason": None if current_period_rows else "effective_window_or_matching_result_intervals_unavailable",
            "periods": {},
        }
        for period, period_rows in current_period_rows.items():
            phase_aligned = aligned_period_rows.get(period, [])
            phase_windows = _unique_windows(period_rows)
            period_analysis["periods"][period] = {
                "interval_ids": sorted({row["interval_id"] for row in period_rows
                                         if row.get("interval_id") is not None}, key=str),
                "time_windows": phase_windows,
                "current_severity": rank_sections(_aggregate_current(period_rows)),
                "worsening_vs_baseline": rank_sections(_aggregate_aligned(phase_aligned), delta=True),
            }
        has_metrics = bool(current_ranking["metrics"])
        expects_baseline = bool(facts and facts.get("baseline_role") == "intervention")
        status = (
            "complete" if has_metrics and facts is not None
            and (not expects_baseline or bool(worsening["metrics"])) else "partial"
        )
        missing_evidence = _missing_evidence(facts, current_rows, baseline_id, worsening)
        path_impact = None
        if analysis_plan.get("profile") != "overview":
            missing_evidence.extend(analysis_plan.get("missing_evidence", []))
            if analysis_plan.get("profile") == "path_impact" and analysis_plan.get("status") == "ready_to_execute":
                path_impact = execute_path_impact(
                    self._testudo,
                    scenario_id=selected_id,
                    baseline_scenario_id=baseline_id or "",
                    interventions=facts.get("interventions", []) if facts else [],
                    metric_rows=rows,
                    requested_intervals=intervals,
                )
                missing_evidence.extend(path_impact.get("missing_evidence", []))
                if path_impact.get("status") != "complete":
                    status = "partial"
            elif analysis_plan.get("profile") == "od_time_series":
                status = "partial"
                missing_evidence.append("OD time-series execution is not implemented")
            else:
                status = "partial"
                missing_evidence.append("path-impact prerequisites are incomplete; no path queries were run")
        return {
            "analysis_status": status,
            "analysis_plan": analysis_plan,
            "source_version_id": catalog.get("version_id", self._testudo.config.version_id),
            "scenario": {"scenario_id": selected_id, "name": selected.get("name", "")},
            "baseline_scenario_id": baseline_id,
            "verified_package_facts": facts,
            "current_severity": current_ranking,
            "worsening_vs_baseline": worsening,
            "aligned_time_windows": _unique_windows(aligned["rows"]),
            "unmatched_interval_count": aligned["unmatched_count"],
            "observed_effective_periods": observed,
            "period_analysis": period_analysis,
            "affected_section_ids": sorted({
                str(value) for item in interventions if isinstance(item, Mapping)
                for value in item.get("affected_section_ids", [])
            }),
            "affected_path_ids": sorted({
                str(value) for item in interventions if isinstance(item, Mapping)
                for value in item.get("affected_path_ids", [])
            }),
            "path_references": catalog.get("path_references"),
            "path_impact": path_impact,
            "match_method": decision.get("method", "ollaya_typed_choice"),
            "model_match_score": decision.get("model_match_score"),
            "score_label": "model match score",
            "score_calibration_status": "not_validated_on_held_out_scenario_data",
            "metric_query_status": metrics.get("status", "unknown"),
            "missing_evidence": list(dict.fromkeys(missing_evidence)),
            "interpolation": False,
        }


def _candidate_summaries(scenarios: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"scenario_id": str(item.get("scenario_id")), "name": str(item.get("name") or "")}
            for item in scenarios[:10] if isinstance(item, Mapping)]


def _exact_name_matches(prompt: str, scenarios: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    def tokens(value: str) -> list[str]:
        return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold(), flags=re.UNICODE)

    prompt_tokens = tokens(prompt)
    matches = []
    for item in scenarios:
        name_tokens = tokens(str(item.get("name") or ""))
        if not name_tokens or len(name_tokens) > len(prompt_tokens):
            continue
        if any(prompt_tokens[index:index + len(name_tokens)] == name_tokens
               for index in range(len(prompt_tokens) - len(name_tokens) + 1)):
            matches.append(item)
    return matches


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _aggregate_current(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("section_id"))].append(row)
    output = []
    for section_id, values in grouped.items():
        entry: dict[str, Any] = {
            "section_id": values[0].get("section_id"),
            "interval_ids": [row.get("interval_id") for row in values],
            "time_windows": [row.get("time_window") for row in values if isinstance(row.get("time_window"), Mapping)],
        }
        for metric in METRICS:
            observed = [_number(row.get(metric)) for row in values]
            numbers = [value for value in observed if value is not None]
            if numbers:
                entry[metric] = sum(numbers) / len(numbers)
        output.append(entry)
    return output


def align_rows(rows: Sequence[Mapping[str, Any]], selected_id: str, baseline_id: str) -> dict[str, Any]:
    """Join exact section and exact absolute window keys; do not pair interval labels."""
    def index(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
        window = row.get("time_window")
        if not isinstance(window, Mapping):
            return None
        start, end = window.get("start"), window.get("end")
        if not isinstance(start, str) or not isinstance(end, str):
            return None
        # datetime only preserves microseconds. Refuse higher input precision
        # rather than silently truncating it into a false match.
        if _has_unsupported_fraction(start) or _has_unsupported_fraction(end):
            return None
        try:
            start_dt, end_dt = datetime.fromisoformat(start), datetime.fromisoformat(end)
        except ValueError:
            return None
        if end_dt <= start_dt or (start_dt.tzinfo is None) != (end_dt.tzinfo is None):
            return None
        if start_dt.tzinfo is not None:
            start_dt = start_dt.astimezone(timezone.utc)
            end_dt = end_dt.astimezone(timezone.utc)
        return str(row.get("section_id")), start_dt.isoformat(), end_dt.isoformat()

    selected = {key: row for row in rows if str(row.get("scenario_id")) == selected_id
                if (key := index(row)) is not None}
    baseline = {key: row for row in rows if str(row.get("scenario_id")) == baseline_id
                if (key := index(row)) is not None}
    common = sorted(set(selected) & set(baseline))
    joined = []
    for section_id, start, end in common:
        current, before = selected[(section_id, start, end)], baseline[(section_id, start, end)]
        entry = {
            "section_id": current.get("section_id"),
            "interval_id": current.get("interval_id"),
            "baseline_interval_id": before.get("interval_id"),
            "time_window": {"start": start, "end": end},
        }
        for metric in METRICS:
            current_value, baseline_value = _number(current.get(metric)), _number(before.get(metric))
            if current_value is not None and baseline_value is not None:
                entry[metric] = current_value
                entry[f"{metric}_baseline"] = baseline_value
                entry[f"{metric}_delta"] = current_value - baseline_value
        joined.append(entry)
    chosen_count = sum(str(row.get("scenario_id")) == selected_id for row in rows)
    baseline_count = sum(str(row.get("scenario_id")) == baseline_id for row in rows)
    return {"rows": joined,
            "unmatched_count": chosen_count + baseline_count - 2 * len(joined),
            "interpolation": False}


def _has_unsupported_fraction(value: str) -> bool:
    """Return true when an ISO time carries precision Python would truncate."""
    match = re.search(r"T\d{2}:\d{2}:\d{2}[.,](\d+)", value, flags=re.IGNORECASE)
    return bool(match and len(match.group(1)) > 6)


def _aggregate_aligned(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("section_id"))].append(row)
    output = []
    for values in grouped.values():
        entry: dict[str, Any] = {
            "section_id": values[0].get("section_id"),
            "aligned_intervals": [row.get("interval_id") for row in values],
            "aligned_time_windows": [row.get("time_window") for row in values],
        }
        keys = (*METRICS, *(f"{metric}_baseline" for metric in METRICS),
                *(f"{metric}_delta" for metric in METRICS))
        for key in keys:
            numbers = [_number(row.get(key)) for row in values]
            present = [number for number in numbers if number is not None]
            if present:
                entry[key] = sum(present) / len(present)
        output.append(entry)
    return output


def percentile_rank(values: Sequence[float], *, higher_is_worse: bool) -> list[float]:
    ranked = sorted(((index, value) for index, value in enumerate(values) if math.isfinite(value)),
                    key=lambda item: item[1], reverse=higher_is_worse)
    output = [math.nan] * len(values)
    index = 0
    count = len(ranked)
    while index < count:
        end = index + 1
        while end < count and ranked[end][1] == ranked[index][1]:
            end += 1
        score = 1.0 if count == 1 else 1.0 - ((index + end - 1) / 2) / (count - 1)
        for position in range(index, end):
            output[ranked[position][0]] = score
        index = end
    return output


def rank_sections(rows: Sequence[Mapping[str, Any]], *, delta: bool = False) -> dict[str, Any]:
    metrics = [metric for metric in METRICS if any(
        _number(row.get(metric if not delta else f"{metric}_delta")) is not None for row in rows
    )]
    components: dict[str, list[float]] = {}
    for metric in metrics:
        values = [_number(row.get(metric if not delta else f"{metric}_delta")) for row in rows]
        valid = [(index, -value if delta and metric == "speed" else value)
                 for index, value in enumerate(values) if value is not None]
        ranked = percentile_rank([value for _index, value in valid], higher_is_worse=(metric != "speed" or delta))
        component_values = [math.nan] * len(values)
        for (original_index, _value), score in zip(valid, ranked):
            component_values[original_index] = score
        components[metric] = component_values
    sections = []
    metric_rankings: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        present = {metric: components[metric][index] for metric in metrics if math.isfinite(components[metric][index])}
        score = sum(present.values()) / len(present) if len(present) >= 2 else None
        metric_values = {}
        for metric in metrics:
            if delta:
                metric_values[metric] = {"current": row.get(metric), "baseline": row.get(f"{metric}_baseline"),
                                         "delta": row.get(f"{metric}_delta")}
            else:
                metric_values[metric] = {"current": row.get(metric)}
        sections.append({"section_id": row.get("section_id"), "score": score,
                         "interval_ids": row.get("aligned_intervals", row.get("interval_ids", [])),
                         "time_windows": row.get("aligned_time_windows", row.get("time_windows", [])),
                         "metrics": metric_values, "metric_percentiles": present,
                         "contributing_metrics": list(present)})
    sections.sort(key=lambda item: (-1 if item["score"] is None else -item["score"], str(item["section_id"])))
    for metric in metrics:
        available_indices = [idx for idx in range(len(rows)) if math.isfinite(components[metric][idx])]
        ordered_indices = sorted(
            available_indices,
            key=lambda idx: (-components[metric][idx], str(rows[idx].get("section_id"))),
        )
        metric_rankings[metric] = []
        for idx in ordered_indices:
            values = (
                {"current": rows[idx].get(metric), "baseline": rows[idx].get(f"{metric}_baseline"),
                 "delta": rows[idx].get(f"{metric}_delta")}
                if delta else rows[idx].get(metric)
            )
            metric_rankings[metric].append({
                "section_id": rows[idx].get("section_id"),
                "percentile": components[metric][idx],
                "values": values,
            })
    available = any(row["score"] is not None for row in sections)
    reason = None if available else (
        "fewer_than_two_metrics" if len(metrics) < 2 else "no_section_has_two_metrics"
    )
    return {"available": available,
            "reason": reason,
            "metrics": metrics, "sections": sections, "metric_rankings": metric_rankings}


def observed_effective_periods(
    rows: Sequence[Mapping[str, Any]],
    interventions: Sequence[Mapping[str, Any]],
) -> dict[str, list[Any]]:
    grouped = split_effective_period_rows(rows, interventions)
    return {phase: sorted({row.get("interval_id") for row in values if row.get("interval_id") is not None})
            for phase, values in grouped.items()
            if any(row.get("interval_id") is not None for row in values)}


def split_effective_period_rows(
    rows: Sequence[Mapping[str, Any]], interventions: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    """Group observed result rows around complete, package-declared windows."""
    if not interventions:
        return {}
    windows: list[tuple[Any, Any]] = []
    basis = None
    for intervention in interventions:
        window = intervention.get("effective_window")
        if not isinstance(window, Mapping):
            return {}
        start_interval, end_interval = window.get("start_interval"), window.get("end_interval")
        if (isinstance(start_interval, (int, float)) and not isinstance(start_interval, bool)
                and isinstance(end_interval, (int, float)) and not isinstance(end_interval, bool)
                and start_interval <= end_interval):
            item_basis, bounds = "interval", (start_interval, end_interval)
        else:
            start, end = window.get("start"), window.get("end")
            if not isinstance(start, str) or not isinstance(end, str):
                return {}
            parsed = (_parse_clock(start), _parse_clock(end))
            if parsed[0] is None or parsed[1] is None or parsed[1] <= parsed[0]:
                return {}
            item_basis, bounds = "clock", parsed
            if (bounds[0].tzinfo is None) != (bounds[1].tzinfo is None):
                return {}
        if basis is not None and basis != item_basis:
            return {}
        basis = item_basis
        windows.append(bounds)

    aware = False
    if basis == "clock":
        aware = windows[0][0].tzinfo is not None
        if any((start.tzinfo is not None) != aware for start, _end in windows):
            return {}
        if aware:
            windows = [(start.astimezone(timezone.utc), end.astimezone(timezone.utc))
                       for start, end in windows]
    earliest, latest = min(start for start, _end in windows), max(end for _start, end in windows)
    grouped: dict[str, list[Mapping[str, Any]]] = {"before": [], "during": [], "after": []}
    for row in rows:
        period = None
        if basis == "interval":
            interval = row.get("interval_id")
            if isinstance(interval, (int, float)) and not isinstance(interval, bool):
                if any(start <= interval <= end for start, end in windows):
                    period = "during"
                elif interval < earliest:
                    period = "before"
                elif interval > latest:
                    period = "after"
        else:
            time_window = row.get("time_window")
            if isinstance(time_window, Mapping):
                start, end = time_window.get("start"), time_window.get("end")
                if isinstance(start, str) and isinstance(end, str):
                    row_start, row_end = _parse_clock(start), _parse_clock(end)
                    if (row_start is not None and row_end is not None and row_end > row_start
                            and (row_start.tzinfo is None) == (row_end.tzinfo is None)
                            and (row_start.tzinfo is not None) == aware):
                        if aware:
                            row_start = row_start.astimezone(timezone.utc)
                            row_end = row_end.astimezone(timezone.utc)
                        if any(row_start < end_bound and row_end > start_bound
                               for start_bound, end_bound in windows):
                            period = "during"
                        elif row_end <= earliest:
                            period = "before"
                        elif row_start >= latest:
                            period = "after"
        if period:
            grouped[period].append(row)
    return {phase: values for phase, values in grouped.items() if values}


def _parse_clock(value: str) -> datetime | None:
    if _has_unsupported_fraction(value):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _unique_windows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    windows = sorted({(row["time_window"]["start"], row["time_window"]["end"])
                      for row in rows if isinstance(row.get("time_window"), Mapping)
                      and isinstance(row["time_window"].get("start"), str)
                      and isinstance(row["time_window"].get("end"), str)})
    return [{"start": start, "end": end} for start, end in windows]


def _missing_evidence(facts: Any, current_rows: Sequence[Mapping[str, Any]], baseline_id: str | None,
                      worsening: Mapping[str, Any]) -> list[str]:
    missing = []
    if facts is None:
        missing.append("declared scenario intervention metadata")
    if not current_rows:
        missing.append("selected scenario result metrics")
    if facts and facts.get("baseline_role") == "intervention" and baseline_id is None:
        missing.append("explicit linked baseline in the package catalog")
    if (baseline_id is not None and facts and facts.get("baseline_role") == "intervention"
            and not worsening.get("metrics")):
        missing.append("exactly aligned baseline result metrics")
    return missing


def _partial_without_metrics(selected: Mapping[str, Any], facts: Any, baseline_id: str | None,
                             decision: Mapping[str, Any],
                             analysis_plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    missing = ["Testudo scenario result metrics"]
    if analysis_plan and analysis_plan.get("profile") != "overview":
        missing.extend(analysis_plan.get("missing_evidence", []))
        missing.append("deeper analysis profile steps have not been executed")
    return {
        "analysis_status": "partial",
        "analysis_plan": dict(analysis_plan or {}),
        "scenario": {"scenario_id": str(selected.get("scenario_id")), "name": selected.get("name", "")},
        "baseline_scenario_id": baseline_id,
        "verified_package_facts": facts,
        "current_severity": rank_sections([]),
        "worsening_vs_baseline": rank_sections([], delta=True),
        "match_method": decision.get("method", "ollaya_typed_choice"),
        "model_match_score": decision.get("model_match_score"),
        "score_label": "model match score",
        "score_calibration_status": "not_validated_on_held_out_scenario_data",
        "missing_evidence": list(dict.fromkeys(missing)),
        "interpolation": False,
    }
