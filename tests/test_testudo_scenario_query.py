from __future__ import annotations

import json
import unittest
from modeller.adapters.testudo_scenario_query import (
    ScenarioQueryConfig,
    ScenarioQueryError,
    TestudoScenarioQueryClient,
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


class ScenarioQueryTests(unittest.TestCase):
    def test_only_scoped_get_requests_are_sent(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.method, request.full_url, request.get_header("Authorization"), timeout))
            return _Response({"version_id": "v1", "scenarios": []})

        client = TestudoScenarioQueryClient(
            ScenarioQueryConfig("https://testudo.example", "v1", "scoped", activation=True), opener=opener
        )
        self.assertEqual(client.catalog()["version_id"], "v1")
        self.assertEqual(seen[0][0], "GET")
        self.assertTrue(seen[0][1].endswith("/api/v1/view/v1/scenario-analysis/catalog"))
        self.assertEqual(seen[0][2], "Bearer scoped")

    def test_metrics_bounds_ids_and_encodes_interval_filters(self):
        seen = []

        def opener(request, timeout):
            seen.append(request.full_url)
            return _Response({"version_id": "v1", "rows": []})

        client = TestudoScenarioQueryClient(
            ScenarioQueryConfig("https://testudo.example", "v1", "scoped", activation=True), opener=opener
        )
        client.metrics([2, 3], [1, 4])
        self.assertIn("scids=2%2C3", seen[0])
        self.assertIn("intervals=1%2C4", seen[0])
        with self.assertRaises(ScenarioQueryError):
            client.metrics([True])

    def test_requires_explicit_activation_and_version_bound_response(self):
        with self.assertRaises(ValueError):
            TestudoScenarioQueryClient(ScenarioQueryConfig("https://testudo.example", "v1", "", activation=False))

        client = TestudoScenarioQueryClient(
            ScenarioQueryConfig("https://testudo.example", "v1", "scoped", activation=True),
            opener=lambda *_args, **_kwargs: _Response({"version_id": "other"}),
        )
        with self.assertRaises(ScenarioQueryError):
            client.catalog()

    def test_plain_http_is_restricted_to_loopback_development(self):
        with self.assertRaises(ValueError):
            ScenarioQueryConfig("http://testudo.example", "v1", "scoped", activation=True)
        config = ScenarioQueryConfig("http://127.0.0.1:8020", "v1", "local", activation=True)
        self.assertEqual(config.base_url, "http://127.0.0.1:8020")


if __name__ == "__main__":
    unittest.main()
