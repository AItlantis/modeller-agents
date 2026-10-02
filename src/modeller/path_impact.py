"""Bounded read-only execution of scenario path-impact evidence."""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from modeller.adapters.testudo_scenario_query import ScenarioQueryError

MAX_SELECTED_PATHS = 1000
MAX_OD_PAIRS = 500


def execute_path_impact(
    client: Any,
    *,
    scenario_id: str,
    baseline_scenario_id: str,
    interventions: Sequence[Any],
    metric_rows: Sequence[Mapping[str, Any]],
    requested_intervals: list[int] | None = None,
) -> dict[str, Any]:
    """Resolve affected paths, OD assignments, section-delay sums, and subpath times.

    All baseline deltas require the same ordered section sequence and identical
    absolute time windows. Missing or ambiguous crosswalk evidence is surfaced.
    """
    missing: list[str] = []
    section_scope, path_scope = _event_scope(interventions)
    if not section_scope and not path_scope:
        return _partial(["authored affected section IDs or path IDs are required"])

    scenario, baseline = _scenario_number(scenario_id), _scenario_number(baseline_scenario_id)
    if scenario is None or baseline is None or scenario == baseline:
        return _partial(["distinct integer intervention and baseline scenario IDs are required"])

    try:
        current_crosswalk = client.subpath_crosswalk(scenario)
        baseline_crosswalk = client.subpath_crosswalk(baseline)
    except (ScenarioQueryError, ValueError, TypeError):
        return _partial(["package-scoped subpath/path crosswalk query"])

    current_rows = _matched_crosswalk_rows(current_crosswalk)
    baseline_rows = _matched_crosswalk_rows(baseline_crosswalk)
    selected_paths = [row for row in current_rows if _is_affected(row, section_scope, path_scope)]
    if not selected_paths:
        return _partial(["affected path matched to an unambiguous subpath and OD identity"])

    selected_od_pairs = {
        (int(path["origin"]), int(path["destination"]), int(path["vehicle"]))
        for path in selected_paths
    }
    if len(selected_paths) > MAX_SELECTED_PATHS or len(selected_od_pairs) > MAX_OD_PAIRS:
        exceeded = []
        if len(selected_paths) > MAX_SELECTED_PATHS:
            exceeded.append(f"selected paths exceed the {MAX_SELECTED_PATHS}-path query cap")
        if len(selected_od_pairs) > MAX_OD_PAIRS:
            exceeded.append(f"selected OD pairs exceed the {MAX_OD_PAIRS}-pair query cap")
        return {
            **_partial(exceeded),
            "selected_path_count": len(selected_paths),
            "selected_od_pair_count": len(selected_od_pairs),
            "query_limits": {"max_selected_paths": MAX_SELECTED_PATHS, "max_od_pairs": MAX_OD_PAIRS},
        }

    selected_identity_counts = Counter(_path_identity(path) for path in selected_paths)
    baseline_identity_counts = Counter(_path_identity(path) for path in baseline_rows)
    ambiguous_current = sum(count - 1 for count in selected_identity_counts.values() if count > 1)
    ambiguous_baseline = sum(
        baseline_identity_counts[identity] - 1
        for identity in selected_identity_counts
        if baseline_identity_counts[identity] > 1
    )
    if ambiguous_current or ambiguous_baseline:
        return {
            **_partial(["duplicate crosswalk identities make path-to-baseline matching ambiguous"]),
            "selected_path_count": len(selected_paths),
            "ambiguous_path_count": ambiguous_current + ambiguous_baseline,
        }

    current_intervals, current_windows, interval_truncated, missing_current_intervals = _intervals_for(
        metric_rows, scenario_id, requested_intervals,
    )
    baseline_intervals, baseline_windows, baseline_truncated, _ = _intervals_for(
        metric_rows, baseline_scenario_id, None,
    )
    if interval_truncated:
        missing.append("path-impact interval list was capped at the 120-interval query limit")
    if missing_current_intervals:
        missing.append("one or more requested intervals have no selected-scenario result rows")
    if baseline_truncated:
        missing.append("baseline interval list was capped at the 120-interval query limit")
    if not current_intervals:
        missing.append("selected scenario result intervals with valid IDs")

    current_subpath_ids = sorted({int(row["subpath_oid"]) for row in selected_paths})
    baseline_matches = {
        _path_identity(row): row for row in baseline_rows
        if any(_path_identity(row) == _path_identity(selected) for selected in selected_paths)
    }
    selected_ids = {_path_identity(row) for row in selected_paths}
    if selected_ids - set(baseline_matches):
        missing.append("same ordered affected path and OD/vehicle identity in the linked baseline")

    current_route_rows = _route_assignment_rows(client, scenario, selected_paths, missing)
    baseline_path_rows = [baseline_matches[key] for key in sorted(selected_ids & set(baseline_matches))]
    baseline_route_rows = _route_assignment_rows(client, baseline, baseline_path_rows, missing)

    current_subpaths = _subpath_rows(client, scenario, current_subpath_ids, current_intervals, missing)
    baseline_subpath_ids = sorted({int(row["subpath_oid"]) for row in baseline_path_rows})
    baseline_subpaths = _subpath_rows(client, baseline, baseline_subpath_ids, baseline_intervals, missing)

    paths = []
    for path in selected_paths:
        identity = _path_identity(path)
        base_path = baseline_matches.get(identity)
        path_record = {
            "subpath_oid": path["subpath_oid"],
            "external_id": path.get("external_id"),
            "route_hash": path.get("route_hash"),
            "section_ids": list(path["section_ids"]),
            "origin": path["origin"],
            "destination": path["destination"],
            "vehicle": path["vehicle"],
            "path_assignment": {
                "current": _path_flow_for(path, current_route_rows),
                "baseline": _path_flow_for(base_path, baseline_route_rows) if base_path else None,
            },
            "section_delay_rollups": [],
            "observed_subpath_journey_times": [],
        }
        for interval in current_intervals:
            key = current_windows.get(interval)
            try:
                current_delay = client.path_delay(scenario, path["section_ids"], interval)
            except (ScenarioQueryError, ValueError, TypeError):
                missing.append(f"section-delay rollup for path {path['subpath_oid']} interval {interval}")
                current_delay = None
            current_window = _response_window_key(current_delay)
            if current_delay and current_delay.get("available") is not True:
                current_delay = None
                missing.append(f"section-delay result for path {path['subpath_oid']} interval {interval}")
            elif current_delay and key is not None and current_window != key:
                current_delay = None
                missing.append(f"absolute time-window match for path {path['subpath_oid']} interval {interval}")
            elif current_delay and current_delay.get("complete") is not True:
                missing.append(f"complete section-delay coverage for path {path['subpath_oid']} interval {interval}")

            comparison_window = current_window or key
            baseline_interval = next(
                (ent for ent, window in baseline_windows.items()
                 if comparison_window is not None and window == comparison_window), None,
            )
            baseline_delay = None
            if base_path and baseline_interval is not None:
                try:
                    baseline_delay = client.path_delay(baseline, base_path["section_ids"], baseline_interval)
                except (ScenarioQueryError, ValueError, TypeError):
                    missing.append(f"baseline section-delay rollup for path {path['subpath_oid']}")
                if (not baseline_delay or not baseline_delay.get("available")
                        or _response_window_key(baseline_delay) != comparison_window):
                    baseline_delay = None
                elif baseline_delay.get("complete") is not True:
                    missing.append(f"complete baseline section-delay coverage for path {path['subpath_oid']}")
            elif base_path and comparison_window is not None:
                missing.append(f"baseline result interval aligned to path {path['subpath_oid']} time window")
            comparable = bool(
                current_delay and baseline_delay
                and current_delay.get("complete") is True
                and baseline_delay.get("complete") is True
                and list(path["section_ids"]) == list(base_path["section_ids"])
                and current_window is not None and current_window == _response_window_key(baseline_delay)
                and _number(current_delay.get("value")) is not None
                and _number(baseline_delay.get("value")) is not None
            ) if base_path else False
            path_record["section_delay_rollups"].append({
                "interval_id": interval,
                "time_window": current_delay.get("time_window") if current_delay else None,
                "current": _delay_summary(current_delay),
                "baseline": _delay_summary(baseline_delay),
                "delta": (_number(current_delay.get("value")) - _number(baseline_delay.get("value")))
                if comparable else None,
                "comparable": comparable,
                "comparison_reason": None if comparable else _comparison_reason(
                    path, base_path, current_delay, baseline_delay, current_window,
                ),
            })

            current_journey = _journey_row(current_subpaths, path["subpath_oid"], interval)
            if current_journey is None:
                missing.append(f"observed subpath journey-time row for path {path['subpath_oid']} interval {interval}")
            baseline_journey = None
            if base_path and baseline_interval is not None:
                baseline_journey = _journey_row(baseline_subpaths, base_path["subpath_oid"], baseline_interval)
                if baseline_journey is None:
                    missing.append(f"baseline subpath journey-time row for path {path['subpath_oid']}")
            journey_comparable = bool(
                current_journey and baseline_journey and key is not None and key == baseline_windows.get(baseline_interval)
                and _number(current_journey.get("journey_time")) is not None
                and _number(baseline_journey.get("journey_time")) is not None
            )
            path_record["observed_subpath_journey_times"].append({
                "interval_id": interval,
                "time_window": _window_payload(key),
                "current": current_journey,
                "baseline": baseline_journey,
                "delta": (_number(current_journey["journey_time"]) - _number(baseline_journey["journey_time"]))
                if journey_comparable else None,
                "comparable": journey_comparable,
            })
        paths.append(path_record)

    od_pairs = sorted({(int(path["origin"]), int(path["destination"]), int(path["vehicle"]))
                       for path in selected_paths})
    return {
        "status": "complete" if not missing else "partial",
        "paths": paths,
        "affected_od_pairs": [
            {"origin": origin, "destination": destination, "vehicle": vehicle}
            for origin, destination, vehicle in od_pairs
        ],
        "selected_path_count": len(paths),
        "current_interval_count": len(current_intervals),
        "baseline_comparisons_require_exact_absolute_windows": True,
        "interpolation": False,
        "missing_evidence": list(dict.fromkeys(missing)),
    }


def _partial(missing: list[str]) -> dict[str, Any]:
    return {
        "status": "partial", "paths": [], "affected_od_pairs": [],
        "selected_path_count": 0, "current_interval_count": 0,
        "baseline_comparisons_require_exact_absolute_windows": True,
        "interpolation": False, "missing_evidence": missing,
    }


def _scenario_number(value: str) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 and str(number) == str(value) else None


def _event_scope(interventions: Sequence[Any]) -> tuple[set[int], set[str]]:
    sections: set[int] = set()
    paths: set[str] = set()
    for item in interventions:
        if not isinstance(item, Mapping):
            continue
        for value in item.get("affected_section_ids", []) if isinstance(item.get("affected_section_ids"), list) else []:
            try:
                sections.add(int(value))
            except (TypeError, ValueError):
                continue
        for value in item.get("affected_path_ids", []) if isinstance(item.get("affected_path_ids"), list) else []:
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                paths.add(str(value))
    return sections, paths


def _matched_crosswalk_rows(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    if response.get("available") is not True or not isinstance(response.get("rows"), list):
        return []
    rows = []
    for raw in response["rows"]:
        if not isinstance(raw, Mapping) or raw.get("match_status") != "matched":
            continue
        try:
            sections = [int(value) for value in raw["section_ids"]]
            origin, destination, vehicle = (int(raw[field]) for field in ("origin", "destination", "vehicle"))
            subpath_oid = int(raw["subpath_oid"])
            route_ids = [int(value) for value in raw.get("route_ids", [])]
        except (KeyError, TypeError, ValueError):
            continue
        if not sections or not route_ids:
            continue
        rows.append({**dict(raw), "section_ids": sections, "origin": origin,
                     "destination": destination, "vehicle": vehicle,
                     "subpath_oid": subpath_oid, "route_ids": route_ids})
    return rows


def _is_affected(row: Mapping[str, Any], sections: set[int], paths: set[str]) -> bool:
    if sections.intersection(row["section_ids"]):
        return True
    # Path metadata may refer to a subpath object, external ID, or stable route hash.
    references = {str(row.get("subpath_oid")), str(row.get("external_id") or ""),
                  str(row.get("route_hash") or ""),
                  *(str(value) for value in row.get("route_ids", [])
                    if isinstance(value, (str, int)) and not isinstance(value, bool))}
    return bool(paths.intersection(references))


def _path_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (int(row["origin"]), int(row["destination"]), int(row["vehicle"]), tuple(row["section_ids"]))


def _intervals_for(
    rows: Sequence[Mapping[str, Any]], scenario_id: str, requested: list[int] | None,
) -> tuple[list[int], dict[int, tuple[str, str]], bool, bool]:
    by_interval: dict[int, tuple[str, str]] = {}
    all_ids: set[int] = set()
    for row in rows:
        if str(row.get("scenario_id")) != str(scenario_id):
            continue
        try:
            interval = int(row["interval_id"])
        except (KeyError, TypeError, ValueError):
            continue
        all_ids.add(interval)
        key = _window_key(row.get("time_window"))
        if key is not None:
            by_interval[interval] = key
    requested_ids = set(requested) if requested is not None else all_ids
    missing_requested = bool(requested_ids - all_ids)
    ordered = sorted(requested_ids & all_ids)
    truncated = len(ordered) > 120
    return ordered[:120], by_interval, truncated, missing_requested


def _route_assignment_rows(client: Any, scenario: int, paths: Sequence[Mapping[str, Any]], missing: list[str]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    output: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    od_pairs = sorted({(int(row["origin"]), int(row["destination"]), int(row["vehicle"])) for row in paths})
    for origin, destination, vehicle in od_pairs:
        try:
            response = client.od_routes(scenario, origin, destination, vehicle=vehicle)
        except (ScenarioQueryError, ValueError, TypeError):
            missing.append(f"path-assignment routes for OD {origin}->{destination}")
            continue
        routes = response.get("routes") if isinstance(response.get("routes"), list) else []
        for path in paths:
            if (int(path["origin"]), int(path["destination"]), int(path["vehicle"])) != (origin, destination, vehicle):
                continue
            path_ids = {int(value) for value in path.get("route_ids", [])}
            identity = _path_identity(path)
            route_index = { _safe_int(route.get("route_id")): route for route in routes
                            if isinstance(route, Mapping) and _safe_int(route.get("route_id")) is not None }
            matched = [dict(route_index[route_id]) for route_id in sorted(path_ids & set(route_index))]
            if path_ids - set(route_index):
                missing.append(f"crosswalk route assignments for OD {origin}->{destination}")
            output[identity] = matched
    return output


def _path_flow_for(path: Mapping[str, Any] | None, rows: Mapping[tuple[Any, ...], list[dict[str, Any]]]) -> dict[str, Any] | None:
    if path is None:
        return None
    assignments = rows.get(_path_identity(path), [])
    return {
        "route_count": len(assignments),
        "interval_flows": [
            {"interval_id": row.get("interval"), "route_volume": _number(row.get("route_volume"))}
            for row in assignments
        ],
        "total_route_volume_across_assignment_intervals": None,
        "volume_aggregation": "not_summed_across_assignment_intervals",
    }


def _subpath_rows(client: Any, scenario: int, ids: list[int], intervals: list[int], missing: list[str]) -> list[dict[str, Any]]:
    if not ids or not intervals:
        return []
    output = []
    for offset in range(0, len(ids), 1000):
        try:
            response = client.subpath_metrics(scenario, ids[offset:offset + 1000], intervals)
        except (ScenarioQueryError, ValueError, TypeError):
            missing.append(f"observed subpath journey-time metrics for scenario {scenario}")
            return output
        if response.get("available") is not True:
            missing.append(f"observed subpath journey-time metrics for scenario {scenario}")
            continue
        output.extend(dict(row) for row in response.get("rows", []) if isinstance(row, Mapping))
    return output


def _journey_row(rows: Sequence[Mapping[str, Any]], oid: int, interval: int) -> dict[str, Any] | None:
    return next((dict(row) for row in rows
                 if _safe_int(row.get("oid")) == int(oid) and _safe_int(row.get("ent")) == interval), None)


def _delay_summary(response: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return {key: response.get(key) for key in (
        "measure", "interpretation", "value", "complete", "coverage",
        "expected_sections", "observed_sections", "missing_section_ids", "section_values",
    )}


def _comparison_reason(path, baseline_path, current, baseline, current_window) -> str | None:
    if baseline_path is None:
        return "no_exact_baseline_path_identity"
    if list(path["section_ids"]) != list(baseline_path["section_ids"]):
        return "ordered_path_mismatch"
    if current_window is None:
        return "absolute_time_window_unavailable"
    if current is None or baseline is None:
        return "path_delay_evidence_unavailable"
    if current.get("complete") is not True or baseline.get("complete") is not True:
        return "incomplete_section_coverage"
    return "absolute_time_window_mismatch"


def _response_window_key(response: Mapping[str, Any] | None) -> tuple[str, str] | None:
    return _window_key(response.get("time_window")) if isinstance(response, Mapping) else None


def _window_key(window: Any) -> tuple[str, str] | None:
    if not isinstance(window, Mapping):
        return None
    start, end = window.get("start"), window.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    if any((m := re.search(r"T\d{2}:\d{2}:\d{2}[.,](\d+)", value)) and len(m.group(1)) > 6
           for value in (start, end)):
        return None
    try:
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
    except ValueError:
        return None
    if b <= a or (a.tzinfo is None) != (b.tzinfo is None):
        return None
    if a.tzinfo is not None:
        a, b = a.astimezone(timezone.utc), b.astimezone(timezone.utc)
    return a.isoformat(), b.isoformat()


def _window_payload(key: tuple[str, str] | None) -> dict[str, str] | None:
    return {"start": key[0], "end": key[1]} if key else None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)
