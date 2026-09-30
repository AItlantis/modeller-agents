from __future__ import annotations

import unittest

from modeller.scenario_controller import ScenarioAnalysisController


def _catalog():
    return {
        "version_id": "version-1",
        "available_metrics": ["speed", "delay", "density"],
        "scenarios": [
            {"scenario_id": "base", "name": "Base",
             "analysis": {"baseline_role": "baseline", "interventions": []}},
            {"scenario_id": "works", "name": "Roadworks",
             "analysis": {"baseline_role": "intervention", "baseline_scenario_id": "base",
                           "interventions": [{"type": "roadworks", "location": {"section": 17},
                                               "affected_section_ids": [17], "affected_path_ids": [8]}]}},
        ],
    }


class ScenarioAnalysisControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = ScenarioAnalysisController()

    def test_overview_defaults_safely_and_uses_authored_scenario_type(self):
        plan = self.controller.plan(_catalog(), "works")

        self.assertEqual(plan["status"], "ready_to_execute")
        self.assertEqual(plan["profile"], "overview")
        self.assertEqual(plan["profile_source"], "safe_default")
        self.assertEqual(plan["scenario_type"], {
            "types": ["roadworks"], "source": "package_metadata", "verified": True,
        })
        self.assertEqual(plan["baseline_scenario_id"], "base")
        self.assertTrue(all(step["mode"] == "read_only" for step in plan["steps"]))

    def test_user_profile_overrides_ollaya_and_path_profile_fails_closed_without_capability(self):
        plan = self.controller.plan(
            _catalog(), "works", ollaya_profile="overview", requested_profile="path_impact",
        )

        self.assertEqual(plan["profile"], "path_impact")
        self.assertEqual(plan["profile_source"], "user_request")
        self.assertEqual(plan["status"], "needs_evidence")
        self.assertIn("Testudo capability: path_queries", plan["missing_evidence"])
        self.assertIn("Testudo capability: od_pair_aggregation", plan["missing_evidence"])

    def test_od_profile_requires_version_scoped_od_metrics_and_aligned_clock_windows(self):
        plan = self.controller.plan(_catalog(), "works", ollaya_profile="od_time_series")

        self.assertEqual(plan["status"], "needs_evidence")
        self.assertIn("OD-level travel_time results by scenario and interval", plan["missing_evidence"])
        self.assertIn("OD-level delay results by scenario and interval", plan["missing_evidence"])
        self.assertIn("exact OD clock-window alignment support", plan["missing_evidence"])
        self.assertEqual(plan["query_limits"]["max_od_pairs"], 500)

    def test_model_type_hint_is_unverified_and_cannot_override_authored_metadata(self):
        catalog = _catalog()
        plan = self.controller.plan(catalog, "works", ollaya_scenario_type="incident")
        self.assertEqual(plan["scenario_type"]["types"], ["roadworks"])
        self.assertTrue(plan["scenario_type"]["verified"])

        catalog["scenarios"][1].pop("analysis")
        inferred = self.controller.plan(catalog, "works", ollaya_scenario_type="incident")
        self.assertEqual(inferred["scenario_type"], {
            "types": ["incident"], "source": "ollaya_suggestion", "verified": False,
        })

    def test_unsupported_profile_and_unverified_scenario_do_not_expand_execution(self):
        invalid = self.controller.plan(_catalog(), "works", ollaya_profile="simulation")
        self.assertEqual(invalid["profile"], "overview")
        self.assertIn("Ollaya suggested an unsupported analysis profile", invalid["missing_evidence"])

        unknown = self.controller.plan(_catalog(), "not-in-catalog", requested_profile="od_time_series")
        self.assertEqual(unknown["steps"], [])
        self.assertEqual(unknown["reason"], "unverified_scenario")


if __name__ == "__main__":
    unittest.main()
