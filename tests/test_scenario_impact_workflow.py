from __future__ import annotations

import unittest

from modeller.scenario_impact import (
    ScenarioImpactWorkflow, align_rows, observed_effective_periods, rank_sections,
    split_effective_period_rows,
)


class _Testudo:
    config = type("Config", (), {"version_id": "v1"})()

    def __init__(self, rows):
        self.rows = rows
        self.catalog_calls = 0
        self.metrics_args = None

    def catalog(self):
        self.catalog_calls += 1
        return {
            "version_id": "v1",
            "scenarios": [
                {"scenario_id": "1", "name": "Baseline",
                 "analysis": {"baseline_role": "baseline", "baseline_scenario_id": "1", "interventions": []}},
                {"scenario_id": "2", "name": "Roadworks North",
                 "analysis": {"baseline_role": "intervention", "baseline_scenario_id": "1",
                              "interventions": [{"type": "roadworks", "affected_section_ids": [10],
                                                 "affected_path_ids": [5],
                                                 "effective_window": {"start_interval": 1, "end_interval": 2}}]}},
            ],
            "path_references": {"5": "paths/5"},
        }

    def metrics(self, scenario_ids, intervals=None):
        self.metrics_args = (scenario_ids, intervals)
        return {"status": "complete", "rows": self.rows}


class _PathTestudo(_Testudo):
    window = {"start": "2024-06-27T08:00:00", "end": "2024-06-27T08:05:00"}

    def __init__(self, rows):
        super().__init__(rows)
        self.crosswalk_calls = []
        self.route_calls = []
        self.delay_calls = []
        self.subpath_calls = []
        self.delay_complete = True
        self.crosswalk_override = None

    def catalog(self):
        value = super().catalog()
        value["analysis_capabilities"] = {
            "path_queries": True,
            "subpath_crosswalk": True,
            "od_pair_aggregation": True,
            "path_delay_rollup": True,
            "subpath_metrics": True,
        }
        value["available_od_metrics"] = []
        return value

    def subpath_crosswalk(self, scenario_id):
        self.crosswalk_calls.append(scenario_id)
        if self.crosswalk_override is not None:
            return {"available": True, "rows": self.crosswalk_override.get(scenario_id, [])}
        oid, rid = (500, 7) if scenario_id == 2 else (900, 11)
        return {"available": True, "rows": [{
            "subpath_oid": oid, "external_id": "path-5", "route_hash": "hash-5",
            "section_ids": [10, 20], "match_status": "matched",
            "origin": 1, "destination": 2, "vehicle": 3, "route_ids": [rid],
        }]}

    def od_routes(self, scenario_id, origin, destination, *, vehicle=None, interval=None):
        self.route_calls.append((scenario_id, origin, destination, vehicle, interval))
        rid, volume = (7, 50) if scenario_id == 2 else (11, 40)
        return {"routes": [{"route_id": rid, "interval": 1, "route_volume": volume}]}

    def path_delay(self, scenario_id, section_ids, interval):
        self.delay_calls.append((scenario_id, section_ids, interval))
        value = 20 if scenario_id == 2 else 15
        return {
            "available": True, "value": value, "complete": self.delay_complete,
            "coverage": 1.0 if self.delay_complete else 0.5,
            "expected_sections": 2, "observed_sections": 2 if self.delay_complete else 1,
            "missing_section_ids": [] if self.delay_complete else [20],
            "section_values": [{"section_id": 10, "delay": value / 2},
                               {"section_id": 20, "delay": value / 2}],
            "time_window": self.window,
        }

    def subpath_metrics(self, scenario_id, subpath_ids, intervals):
        self.subpath_calls.append((scenario_id, subpath_ids, intervals))
        oid, value = (500, 120) if scenario_id == 2 else (900, 100)
        return {"available": True, "rows": [{
            "oid": oid, "ent": 1, "journey_time": value, "count": 10,
        }]}


class _Matcher:
    def __init__(self, decision=None, error=None):
        self.decision, self.error = decision, error
        self.calls = 0

    def match(self, _prompt, _candidates):
        self.calls += 1
        if self.error:
            raise self.error
        return self.decision


def _row(scenario, section, interval, start, end, speed, delay, density):
    return {"scenario_id": str(scenario), "section_id": section, "interval_id": interval,
            "time_window": {"start": start, "end": end},
            "speed": speed, "delay": delay, "density": density}


def _rows():
    start, end = "2024-06-27T08:00:00", "2024-06-27T08:05:00"
    return [
        _row(2, 10, 1, start, end, 25, 10, 20),
        _row(2, 11, 1, start, end, 5, 50, 40),
        _row(1, 10, 1, start, end, 30, 0, 0),
        _row(1, 11, 1, start, end, 5, 49, 39),
    ]


class ScenarioImpactWorkflowTests(unittest.TestCase):
    def test_matched_request_gathers_explicit_baseline_and_separate_rankings(self):
        testudo = _Testudo(_rows())
        matcher = _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.91})
        workflow = ScenarioImpactWorkflow(testudo, matcher)

        result = workflow.analyze("What did Roadworks North change?", intervals=[1])

        self.assertEqual(result["analysis_status"], "complete")
        self.assertEqual(result["scenario"]["scenario_id"], "2")
        self.assertEqual(result["baseline_scenario_id"], "1")
        self.assertEqual(testudo.metrics_args, ([2, 1], [1]))
        self.assertEqual(result["current_severity"]["sections"][0]["section_id"], 11)
        self.assertEqual(result["worsening_vs_baseline"]["sections"][0]["section_id"], 10)
        self.assertEqual(result["affected_path_ids"], ["5"])
        self.assertEqual(result["aligned_time_windows"], [{"start": "2024-06-27T08:00:00", "end": "2024-06-27T08:05:00"}])
        self.assertEqual(result["observed_effective_periods"], {"during": [1]})
        self.assertTrue(result["period_analysis"]["available"])
        self.assertIn("during", result["period_analysis"]["periods"])
        self.assertFalse(result["interpolation"])

    def test_path_impact_executes_crosswalk_od_delay_sum_and_observed_subpath_time(self):
        testudo = _PathTestudo(_rows())
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.92})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")

        self.assertEqual(result["analysis_status"], "complete")
        self.assertEqual(result["path_impact"]["status"], "complete")
        self.assertEqual(testudo.crosswalk_calls, [2, 1])
        self.assertEqual(testudo.route_calls, [(2, 1, 2, 3, None), (1, 1, 2, 3, None)])
        self.assertEqual(testudo.delay_calls, [(2, [10, 20], 1), (1, [10, 20], 1)])
        self.assertEqual(testudo.subpath_calls, [(2, [500], [1]), (1, [900], [1])])
        path = result["path_impact"]["paths"][0]
        self.assertEqual(path["section_delay_rollups"][0]["delta"], 5)
        self.assertEqual(path["observed_subpath_journey_times"][0]["delta"], 20)
        self.assertEqual(path["path_assignment"]["current"]["interval_flows"], [
            {"interval_id": 1, "route_volume": 50.0},
        ])
        self.assertIsNone(path["path_assignment"]["current"]["total_route_volume_across_assignment_intervals"])
        self.assertEqual(result["path_impact"]["affected_od_pairs"], [
            {"origin": 1, "destination": 2, "vehicle": 3},
        ])

    def test_path_reference_matches_generated_route_id(self):
        testudo = _PathTestudo(_rows())
        catalog = testudo.catalog

        def path_id_only_catalog():
            value = catalog()
            intervention = value["scenarios"][1]["analysis"]["interventions"][0]
            intervention["affected_section_ids"] = []
            intervention["affected_path_ids"] = [7]
            return value

        testudo.catalog = path_id_only_catalog
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.92})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        self.assertEqual(result["path_impact"]["status"], "complete")
        self.assertEqual(testudo.route_calls[0], (2, 1, 2, 3, None))

    def test_path_impact_stops_before_downstream_reads_when_path_cap_is_exceeded(self):
        testudo = _PathTestudo(_rows())
        testudo.crosswalk_override = {
            2: [{"subpath_oid": index, "external_id": f"p-{index}", "route_hash": f"h-{index}",
                 "section_ids": [10, 20], "match_status": "matched", "origin": 1,
                 "destination": 2, "vehicle": 3, "route_ids": [index]} for index in range(1001)],
            1: [],
        }
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.92})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        self.assertEqual(result["path_impact"]["status"], "partial")
        self.assertEqual(result["path_impact"]["selected_path_count"], 1001)
        self.assertIn("1000-path query cap", result["path_impact"]["missing_evidence"][0])
        self.assertEqual(testudo.route_calls, [])
        self.assertEqual(testudo.delay_calls, [])
        self.assertEqual(testudo.subpath_calls, [])

    def test_path_impact_stops_before_downstream_reads_when_od_cap_is_exceeded(self):
        testudo = _PathTestudo(_rows())
        testudo.crosswalk_override = {
            2: [{"subpath_oid": index, "external_id": f"p-{index}", "route_hash": f"h-{index}",
                 "section_ids": [10, 20], "match_status": "matched", "origin": index,
                 "destination": index + 1, "vehicle": 3, "route_ids": [index]} for index in range(501)],
            1: [],
        }
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.92})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        self.assertEqual(result["path_impact"]["status"], "partial")
        self.assertEqual(result["path_impact"]["selected_od_pair_count"], 501)
        self.assertIn("500-pair query cap", result["path_impact"]["missing_evidence"][0])
        self.assertEqual(testudo.route_calls, [])
        self.assertEqual(testudo.delay_calls, [])
        self.assertEqual(testudo.subpath_calls, [])

    def test_duplicate_current_path_identity_is_ambiguous_and_not_queried(self):
        testudo = _PathTestudo(_rows())
        duplicate = {"section_ids": [10, 20], "match_status": "matched", "origin": 1,
                     "destination": 2, "vehicle": 3}
        testudo.crosswalk_override = {
            2: [dict(duplicate, subpath_oid=500, external_id="path-a", route_ids=[7]),
                dict(duplicate, subpath_oid=501, external_id="path-b", route_ids=[8])],
            1: [],
        }
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.92})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        self.assertEqual(result["path_impact"]["status"], "partial")
        self.assertEqual(result["path_impact"]["ambiguous_path_count"], 1)
        self.assertEqual(testudo.route_calls, [])
        self.assertEqual(testudo.delay_calls, [])
        self.assertEqual(testudo.subpath_calls, [])

    def test_duplicate_baseline_path_identity_is_ambiguous_and_not_queried(self):
        testudo = _PathTestudo(_rows())
        current = {"subpath_oid": 500, "external_id": "current", "route_hash": "current-hash",
                   "section_ids": [10, 20], "match_status": "matched", "origin": 1,
                   "destination": 2, "vehicle": 3, "route_ids": [7]}
        baseline = {**current, "subpath_oid": 900, "external_id": "base-a", "route_hash": "base-a-hash",
                    "route_ids": [11]}
        second_baseline = {**baseline, "subpath_oid": 901, "external_id": "base-b",
                           "route_hash": "base-b-hash", "route_ids": [12]}
        testudo.crosswalk_override = {2: [current], 1: [baseline, second_baseline]}
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.92})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        self.assertEqual(result["path_impact"]["status"], "partial")
        self.assertEqual(result["path_impact"]["ambiguous_path_count"], 1)
        self.assertEqual(testudo.route_calls, [])
        self.assertEqual(testudo.delay_calls, [])
        self.assertEqual(testudo.subpath_calls, [])

    def test_path_impact_withholds_delta_when_absolute_windows_do_not_match(self):
        rows = _rows()
        rows[2]["time_window"] = {"start": "2024-06-27T07:00:00", "end": "2024-06-27T07:05:00"}
        rows[3]["time_window"] = rows[2]["time_window"]
        testudo = _PathTestudo(rows)
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.9})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        path = result["path_impact"]["paths"][0]
        self.assertIsNone(path["section_delay_rollups"][0]["delta"])
        self.assertFalse(path["section_delay_rollups"][0]["comparable"])
        self.assertIsNone(path["observed_subpath_journey_times"][0]["delta"])

    def test_path_impact_fails_closed_when_package_does_not_advertise_capabilities(self):
        testudo = _Testudo(_rows())
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.9})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        self.assertEqual(result["analysis_status"], "partial")
        self.assertIsNone(result["path_impact"])
        self.assertIn("path-impact prerequisites are incomplete; no path queries were run", result["missing_evidence"])

    def test_incomplete_section_coverage_is_reported_and_never_yields_a_delta(self):
        testudo = _PathTestudo(_rows())
        testudo.delay_complete = False
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.9})
        ).analyze("Compare Roadworks North", intervals=[1], requested_profile="path_impact")
        path = result["path_impact"]["paths"][0]
        self.assertEqual(result["analysis_status"], "partial")
        self.assertEqual(path["section_delay_rollups"][0]["current"]["coverage"], 0.5)
        self.assertIsNone(path["section_delay_rollups"][0]["delta"])
        self.assertIn("complete section-delay coverage for path 500 interval 1", result["missing_evidence"])

    def test_same_interval_id_with_different_absolute_window_is_not_compared(self):
        rows = _rows()
        rows[2]["time_window"] = {"start": "2024-06-27T07:00:00", "end": "2024-06-27T07:05:00"}
        rows[3]["time_window"] = {"start": "2024-06-27T07:00:00", "end": "2024-06-27T07:05:00"}
        result = ScenarioImpactWorkflow(
            _Testudo(rows), _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.9})
        ).analyze("Compare Roadworks North")
        self.assertEqual(result["worsening_vs_baseline"]["available"], False)
        self.assertEqual(result["aligned_time_windows"], [])
        self.assertEqual(result["unmatched_interval_count"], 4)

    def test_ollaya_outage_allows_only_exact_name_fallback(self):
        from modeller.adapters.ollaya_scenario_match import ScenarioDecisionError
        testudo = _Testudo(_rows())
        result = ScenarioImpactWorkflow(testudo, _Matcher(error=ScenarioDecisionError("offline"))).analyze(
            "Compare Roadworks North impacts"
        )
        self.assertEqual(result["scenario"]["scenario_id"], "2")
        self.assertEqual(result["match_method"], "exact_scenario_name")
        self.assertIsNone(result["model_match_score"])

        ambiguous = ScenarioImpactWorkflow(
            _Testudo([]), _Matcher(error=ScenarioDecisionError("offline"))
        ).analyze("Roadworks Northish")
        self.assertEqual(ambiguous["analysis_status"], "needs_clarification")

    def test_ambiguous_ollaya_decision_does_not_query_metrics(self):
        testudo = _Testudo([])
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "ambiguous", "candidates": [{"scenario_id": "2"}]})
        ).analyze("Maybe roadworks?")
        self.assertEqual(result["analysis_status"], "needs_clarification")
        self.assertIsNone(testudo.metrics_args)

    def test_missing_intervention_metadata_does_not_infer_a_baseline(self):
        testudo = _Testudo(_rows())
        original_catalog = testudo.catalog
        def legacy_catalog():
            value = original_catalog()
            value["scenarios"][1].pop("analysis")
            return value
        testudo.catalog = legacy_catalog
        result = ScenarioImpactWorkflow(
            testudo, _Matcher({"status": "matched", "scenario_id": "2", "model_match_score": 0.9})
        ).analyze("Roadworks North")
        self.assertEqual(result["analysis_status"], "partial")
        self.assertIsNone(result["baseline_scenario_id"])
        self.assertIsNone(result["verified_package_facts"])

    def test_composite_requires_two_metrics_and_alignment_requires_exact_windows(self):
        ranking = rank_sections([{"section_id": 1, "speed": 10}, {"section_id": 2, "density": 3}])
        self.assertFalse(ranking["available"])
        self.assertEqual(set(ranking["metric_rankings"]), {"speed", "density"})
        aligned = align_rows([
            _row(2, 10, 1, "2024-06-27T08:00:00", "2024-06-27T08:05:00", 10, 0, 0),
            _row(1, 10, 1, "2024-06-27T08:05:00", "2024-06-27T08:10:00", 20, 0, 0),
        ], "2", "1")
        self.assertEqual(aligned["rows"], [])
        self.assertEqual(aligned["unmatched_count"], 2)

    def test_alignment_preserves_precision_and_compares_equivalent_absolute_windows(self):
        unequal = align_rows([
            _row(2, 10, 1, "2024-06-27T08:00:00.100", "2024-06-27T08:05:00.100", 10, 0, 0),
            _row(1, 10, 1, "2024-06-27T08:00:00.900", "2024-06-27T08:05:00.900", 20, 0, 0),
        ], "2", "1")
        self.assertEqual(unequal["rows"], [])
        self.assertEqual(unequal["unmatched_count"], 2)

        equivalent = align_rows([
            _row(2, 10, 1, "2024-06-27T08:00:00+00:00", "2024-06-27T08:05:00+00:00", 10, 0, 0),
            _row(1, 10, 9, "2024-06-27T09:00:00+01:00", "2024-06-27T09:05:00+01:00", 20, 0, 0),
        ], "2", "1")
        self.assertEqual(len(equivalent["rows"]), 1)
        self.assertEqual(equivalent["rows"][0]["speed_delta"], -10)

        too_precise = align_rows([
            _row(2, 10, 1, "2024-06-27T08:00:00.123456789", "2024-06-27T08:05:00.123456789", 10, 0, 0),
            _row(1, 10, 1, "2024-06-27T08:00:00,123456700", "2024-06-27T08:05:00,123456700", 20, 0, 0),
        ], "2", "1")
        self.assertEqual(too_precise["rows"], [])
        self.assertEqual(too_precise["unmatched_count"], 2)

    def test_absolute_effective_window_reports_only_observed_phases(self):
        rows = [
            _row(2, 10, 1, "2024-06-27T08:00:00", "2024-06-27T08:05:00", 10, 0, 0),
            _row(2, 10, 2, "2024-06-27T08:05:00", "2024-06-27T08:10:00", 10, 0, 0),
            _row(2, 10, 3, "2024-06-27T08:10:00", "2024-06-27T08:15:00", 10, 0, 0),
        ]
        interventions = [{"effective_window": {
            "start": "2024-06-27T08:05:00", "end": "2024-06-27T08:10:00",
        }}]
        grouped = split_effective_period_rows(rows, interventions)
        self.assertEqual({key: [row["interval_id"] for row in values]
                          for key, values in grouped.items()}, {
            "before": [1], "during": [2], "after": [3],
        })
        self.assertEqual(observed_effective_periods(rows, interventions), {
            "before": [1], "during": [2], "after": [3],
        })


if __name__ == "__main__":
    unittest.main()
