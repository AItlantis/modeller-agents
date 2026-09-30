from __future__ import annotations

import json
import unittest

from modeller.adapters.ollaya_scenario_match import (
    OllayaScenarioConfig,
    OllayaScenarioMatcher,
    ScenarioDecisionError,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class OllayaScenarioMatchTests(unittest.TestCase):
    def _matcher(self, answer, seen):
        payload = {"done_reason": "decide", "state_truncated": False,
                   "answers": {"scenario": answer}}
        def opener(request, timeout):
            seen.append((request, timeout))
            return _Response(payload)
        return OllayaScenarioMatcher(
            OllayaScenarioConfig("https://ollaya.example", "laya", "secret", activation=True),
            opener=opener,
        )

    def test_only_catalog_choices_can_pass_the_score_and_margin_gate(self):
        seen = []
        matcher = self._matcher({
            "type": "choice", "choice": "2",
            "probabilities": {"1": 0.05, "2": 0.90, "__no_match__": 0.05},
        }, seen)
        result = matcher.match("Compare roadworks", [
            {"scenario_id": 1, "name": "Baseline"},
            {"scenario_id": 2, "name": "Roadworks North",
             "analysis": {"baseline_role": "intervention", "baseline_scenario_id": 1,
                          "interventions": [{"type": "roadworks", "location": {"road": "A12"},
                                             "effective_window": {"start_interval": 2, "end_interval": 5}}]}},
        ])
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["scenario_id"], "2")
        self.assertEqual(result["model_match_score"], 0.9)
        request = seen[0][0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        body = json.loads(request.data)
        self.assertEqual(body["questions"]["scenario"]["type"], "choice")
        self.assertIn("__no_match__", body["questions"]["scenario"]["criteria"])
        self.assertEqual(body["state"]["verified_candidates"][1]["intervention_types"], ["roadworks"])
        self.assertEqual(body["state"]["verified_candidates"][1]["locations"], ['{"road":"A12"}'])
        self.assertEqual(body["state"]["verified_candidates"][1]["effective_windows"], ['{"start_interval":2,"end_interval":5}'])

    def test_low_margin_no_match_and_invalid_distributions_never_select(self):
        seen = []
        low = self._matcher({"type": "choice", "choice": "2",
                             "probabilities": {"1": 0.20, "2": 0.79, "__no_match__": 0.01}}, seen)
        self.assertEqual(low.match("roadworks", [{"scenario_id": "1"}, {"scenario_id": "2"}])["status"], "ambiguous")
        no_match = self._matcher({"type": "choice", "choice": "__no_match__",
                                  "probabilities": {"1": 0.05, "2": 0.05, "__no_match__": 0.90}}, seen)
        decision = no_match.match("unrelated", [{"scenario_id": "1"}, {"scenario_id": "2"}])
        self.assertEqual(decision["status"], "ambiguous")
        self.assertTrue(decision["no_match"])
        malformed = self._matcher({"type": "choice", "choice": "2",
                                   "probabilities": {"1": 0.4, "2": 0.4, "__no_match__": 0.4}}, seen)
        with self.assertRaises(ScenarioDecisionError):
            malformed.match("roadworks", [{"scenario_id": "1"}, {"scenario_id": "2"}])

    def test_unlisted_choice_and_missing_score_distribution_are_rejected(self):
        seen = []
        outsider = self._matcher({"type": "choice", "choice": "99",
                                  "probabilities": {"1": 0.5, "__no_match__": 0.5}}, seen)
        with self.assertRaises(ScenarioDecisionError):
            outsider.match("choose", [{"scenario_id": "1"}])
        missing = self._matcher({"type": "choice", "choice": "1", "confidence": 0.99}, seen)
        with self.assertRaises(ScenarioDecisionError):
            missing.match("choose", [{"scenario_id": "1"}])

    def test_activation_and_candidate_ids_are_validated(self):
        with self.assertRaises(ValueError):
            OllayaScenarioMatcher(OllayaScenarioConfig("https://ollaya.example", "laya"))
        seen = []
        matcher = self._matcher({"type": "choice", "choice": "1",
                                 "probabilities": {"1": 0.5, "__no_match__": 0.5}}, seen)
        with self.assertRaises(ValueError):
            matcher.match("prompt", [{"scenario_id": "1"}, {"scenario_id": "1"}])
        with self.assertRaises(ValueError):
            OllayaScenarioConfig("http://ollaya.example", "laya", "secret", activation=True)
        local_config = OllayaScenarioConfig("http://127.0.0.1:11435", "laya", activation=True)
        self.assertTrue(local_config.activation)


if __name__ == "__main__":
    unittest.main()
