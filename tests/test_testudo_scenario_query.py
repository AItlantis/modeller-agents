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

    def test_path_and_subpath_reads_are_version_scoped_gets_and_preserve_order(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.method, request.full_url))
            return _Response({"available": True, "rows": []})

        client = TestudoScenarioQueryClient(
            ScenarioQueryConfig("https://testudo.example", "v1", "scoped", activation=True), opener=opener
        )
        client.subpath_crosswalk(12)
        client.od_routes(12, 10, 20, vehicle=3, interval=4)
        client.path_delay(12, [20, 10, 20], 7)
        client.subpath_metrics(12, [700, 701], [7, 8])

        self.assertTrue(all(method == "GET" for method, _url in seen))
        self.assertTrue(seen[0][1].endswith("/path-api/subpaths/crosswalk?scid=12"))
        self.assertIn("/path-api/od/10/20/routes?", seen[1][1])
        self.assertIn("section_ids=20%2C10%2C20", seen[2][1])
        self.assertIn("ent=7", seen[2][1])
        self.assertIn("oids=700%2C701", seen[3][1])
        self.assertIn("ent_values=7%2C8", seen[3][1])

    def test_path_reads_reject_unbounded_or_mistyped_identifiers(self):
        client = TestudoScenarioQueryClient(
            ScenarioQueryConfig("https://testudo.example", "v1", "scoped", activation=True),
            opener=lambda *_args, **_kwargs: _Response({"available": True}),
        )
        with self.assertRaises(ScenarioQueryError):
            client.path_delay(1, [True], 1)
        with self.assertRaises(ScenarioQueryError):
            client.path_delay(1, list(range(501)), 1)
        with self.assertRaises(ScenarioQueryError):
            client.subpath_metrics(1, [5], [])

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
