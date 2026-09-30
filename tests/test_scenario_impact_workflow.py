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
