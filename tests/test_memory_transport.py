from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modeller.memory_transport import transport_memory_candidate


class MemoryTransportTests(unittest.TestCase):
    def test_transport_writes_valid_discovery_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = _write_candidate(root)
            inbox = root / "modelling-knowledge" / "inbox" / "discovery-drafts"

            result = transport_memory_candidate(candidate_path, inbox)

            self.assertTrue(result.ok, result.errors)
            self.assertIsNotNone(result.output_path)
            draft = result.output_path.read_text(encoding="utf-8")
            self.assertIn('status: "draft"', draft)
            self.assertIn('type: "discovery-draft"', draft)
            self.assertIn('owner: "modeller-agents/memory-agent"', draft)
            self.assertIn('source: "modeller-memory"', draft)
            self.assertIn('candidate_id: "memcand-20260714-001"', draft)
            self.assertIn('origin_run: "run-20260714-001"', draft)
            self.assertIn("authority_context_refs:", draft)
            self.assertIn("related_decisions:", draft)
            self.assertIn('sensitivity: "internal"', draft)
            self.assertIn("captured_from:", draft)
            self.assertIn("claim:", draft)
            self.assertNotIn("\nauthority_level:", draft)
            self.assertNotIn("\nid:", draft)
            self.assertEqual(result.output_path.parent.resolve(), inbox.resolve())

    def test_transport_refuses_non_inbox_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = _write_candidate(root, target="companion")
            inbox = root / "modelling-knowledge" / "inbox" / "discovery-drafts"

            result = transport_memory_candidate(candidate_path, inbox)

            self.assertFalse(result.ok)
            self.assertTrue(any("vault-inbox" in error for error in result.errors), result.errors)
            self.assertFalse(inbox.exists())

    def test_transport_refuses_unsafe_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = _write_candidate(root)
            unsafe = root / "modelling-knowledge" / "domains"

            result = transport_memory_candidate(candidate_path, unsafe)

            self.assertFalse(result.ok)
            self.assertTrue(any("inbox/discovery-drafts" in error for error in result.errors), result.errors)
            self.assertFalse(unsafe.exists())


def _write_candidate(root: Path, **overrides: object) -> Path:
    candidate = {
        "candidate_id": "memcand-20260714-001",
        "classification": "durable-candidate",
        "claim": "Memory transport must write vault inbox candidates as governed discovery drafts.",
        "provenance": {
            "origin_run": "run-20260714-001",
            "source_repository": "modeller-agents",
            "source_commit": "abc123",
            "evidence_refs": ["docs/dev/memory-transport.md"],
        },
        "sensitivity": "internal",
        "target": "vault-inbox",
        "confidence": 0.9,
        "related_decisions": ["0007-memory-promotion-coordination"],
        "origin_run": "run-20260714-001",
        "authority_context_refs": ["decisions/0007-memory-promotion-coordination"],
    }
    candidate.update(overrides)
    path = root / "candidate.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
