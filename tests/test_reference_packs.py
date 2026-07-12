from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modeller.knowledge_packs import VaultExports, validate_knowledge_pack
from modeller.reference_packs import validate_reference_pack
from modeller.route import route_envelope


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
VAULT = WORKSPACE / "modelling-knowledge"
SHARED_ELIGIBILITY_FIXTURE = VAULT / "docs" / "dev" / "fixtures" / "eligibility-conformance.json"


class ReferencePackTests(unittest.TestCase):
    def test_validate_reference_pack_accepts_required_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "reference-packs" / "demo.toml"
            pack.parent.mkdir()
            pack.write_text(
                "\n".join(
                    [
                        'id = "demo"',
                        'status = "active"',
                        'source_repository = "demo"',
                        'owner = "demo"',
                        'central_skills = ["workflow"]',
                        "local_agents_stay_in_source = true",
                    ]
                ),
                encoding="utf-8",
            )

            result = validate_reference_pack(root, "reference-packs/demo.toml")

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.skills, ["workflow"])

    def test_route_rejects_malformed_reference_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bundles").mkdir()
            (root / "reference-packs").mkdir()
            (root / "bundles" / "demo.bundle.json").write_text(
                json.dumps(
                    {
                        "id": "demo",
                        "status": "draft",
                        "skills": ["workflow"],
                        "referencePacks": ["reference-packs/demo.toml"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "reference-packs" / "demo.toml").write_text(
                "\n".join(
                    [
                        'id = "wrong"',
                        'status = "draft"',
                        'source_repository = "demo"',
                    ]
                ),
                encoding="utf-8",
            )
            envelope = root / "envelope.json"
            envelope.write_text(
                json.dumps(
                    {
                        "intent": {"target_repository": "demo", "requested_capability": "workflow"},
                        "execution_policy": {"consent_required": True, "max_risk_level": "low"},
                    }
                ),
                encoding="utf-8",
            )

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(any("missing owner" in error for error in decision.errors), decision.errors)
            self.assertTrue(any("id 'wrong'" in error for error in decision.errors), decision.errors)

    def test_route_rejects_unknown_requested_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            envelope = root / "envelope.json"
            envelope.write_text(
                json.dumps(
                    {
                        "intent": {"target_repository": "demo", "requested_capability": "not-a-skill"},
                        "execution_policy": {"consent_required": True, "max_risk_level": "low"},
                    }
                ),
                encoding="utf-8",
            )

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertIn("unknown requested_capability 'not-a-skill'", decision.errors)

    def test_route_rejects_skill_not_authorized_by_any_reference_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(root, bundle_skills=["review"], pack_skills=["workflow"])
            envelope = _write_envelope(root, "review")

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(
                any("not authorized by any selected reference pack" in error for error in decision.errors),
                decision.errors,
            )

    def test_route_accepts_pipeline_smoke_when_bundle_and_pack_authorize_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(
                root,
                bundle_skills=["pipeline-smoke"],
                pack_skills=["pipeline-smoke"],
                routing_key_kind="repository-class",
            )
            envelope = _write_envelope(root, "pipeline-smoke")

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.skill, "pipeline-smoke")
            self.assertEqual(decision.routing_key_kind, "repository-class")

    def test_route_accepts_utf8_bom_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(root, bundle_skills=["review"], pack_skills=["review"])
            envelope = _write_envelope(root, "review")
            envelope.write_bytes(b"\xef\xbb\xbf" + envelope.read_bytes())

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.skill, "review")

    def test_route_rejects_bundle_without_routing_key_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(root, bundle_skills=["review"], pack_skills=["review"], routing_key_kind=None)
            envelope = _write_envelope(root, "review")

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(any("routingKeyKind" in error for error in decision.errors), decision.errors)

    def test_route_orders_knowledge_domains_with_source_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(
                root,
                bundle_skills=["review"],
                pack_skills=["review"],
                default_knowledge=["product"],
            )
            _write_skill(root, "review", mode="explicit", domains=["accessibility", "product"])
            _write_domain_registry(root)
            _write_knowledge_pack(root, "accessibility", status="draft")
            _write_knowledge_pack(root, "product", status="draft")
            envelope = _write_envelope(root, "review", domains=["accessibility"])

            decision = route_envelope(root, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(
                decision.knowledge_domains,
                [
                    {"id": "accessibility", "source": "request"},
                    {"id": "product", "source": "bundle-default"},
                ],
            )
            self.assertEqual(
                decision.knowledge_packs,
                ["reference-packs/domains/accessibility.toml", "reference-packs/domains/product.toml"],
            )
            self.assertEqual(decision.knowledge_budget["packs_selected"], 2)

    def test_route_rejects_default_knowledge_over_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(
                root,
                bundle_skills=["review"],
                pack_skills=["review"],
                default_knowledge=["accessibility", "product", "transport"],
            )
            envelope = _write_envelope(root, "review")

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(any("maximum is 2" in error for error in decision.errors), decision.errors)

    def test_route_rejects_domain_not_allowed_by_explicit_affinity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_bundle_and_pack(root, bundle_skills=["review"], pack_skills=["review"])
            _write_skill(root, "review", mode="explicit", domains=["product"])
            _write_domain_registry(root)
            _write_knowledge_pack(root, "accessibility", status="draft")
            envelope = _write_envelope(root, "review", domains=["accessibility"])

            decision = route_envelope(root, envelope)

            self.assertFalse(decision.ok)
            self.assertTrue(any("does not explicitly allow" in error for error in decision.errors), decision.errors)

    def test_active_knowledge_pack_fails_on_superseded_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_knowledge_pack(root, "accessibility", status="active", note_id="old-note")
            exports = VaultExports(
                index={
                    "index_digest": "index-1",
                    "notes": [
                        {
                            "id": "old-note",
                            "domain": "accessibility",
                            "status": "superseded",
                            "superseded_by": "new-note",
                            "exposable": True,
                            "sensitivity": "public",
                            "type": "reference",
                        }
                    ],
                },
                domains={
                    "index_digest": "domains-1",
                    "domains": [
                        {
                            "id": "accessibility",
                            "status": "active",
                            "routable": True,
                            "allowed_note_types": ["reference"],
                            "notes_digest": "notes-1",
                        }
                    ],
                },
            )

            result = validate_knowledge_pack(root, "reference-packs/domains/accessibility.toml", exports=exports)

            self.assertFalse(result.ok)
            self.assertTrue(any("superseded" in error for error in result.errors), result.errors)

    def test_live_accessibility_pack_conforms_to_vault_export(self) -> None:
        result = validate_knowledge_pack(ROOT, "reference-packs/domains/accessibility.toml")

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "active")

    def test_shared_eligibility_conformance_fixture(self) -> None:
        if not SHARED_ELIGIBILITY_FIXTURE.is_file():
            self.skipTest("sibling modelling-knowledge shared eligibility fixture is not available")
        index = json.loads((VAULT / "docs/dev/vault-index.json").read_text(encoding="utf-8"))
        domains = json.loads((VAULT / "docs/dev/knowledge-domains.json").read_text(encoding="utf-8"))
        exports = VaultExports(index=index, domains=domains)
        domain_specs = {d["id"]: d for d in domains["domains"]}
        fixture = json.loads(SHARED_ELIGIBILITY_FIXTURE.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _write_domain_registry(root)
                    _write_conformance_pack(root, case, domain_specs[case["domain"]], domains["index_digest"])
                    result = validate_knowledge_pack(
                        root, f"reference-packs/domains/{case['domain']}.toml", exports=exports
                    )
                    self.assertIs(result.ok, case["expected"], result.errors)

    def test_pack_currency_survives_unrelated_index_change(self) -> None:
        # A change to the whole-index digest that leaves THIS domain's notes
        # untouched must not invalidate the pack: currency is anchored to the
        # per-domain notes_digest, not the whole-index digest.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_knowledge_pack(root, "accessibility", status="active", note_id="acc-note")
            note = {
                "id": "acc-note",
                "domain": "accessibility",
                "status": "accepted",
                "exposable": True,
                "exposure_scopes": ["internal-agent"],
                "sensitivity": "public",
                "type": "reference",
            }
            domain = {
                "id": "accessibility",
                "status": "active",
                "routable": True,
                "allowed_note_types": ["reference"],
                "notes_digest": "notes-1",
            }
            # Whole-index digest differs run-to-run (unrelated notes changed),
            # but the domain notes_digest the pack pins to is unchanged.
            for index_digest in ("index-A", "index-B-after-unrelated-change"):
                exports = VaultExports(
                    index={"index_digest": index_digest, "notes": [note]},
                    domains={"index_digest": "domains-1", "domains": [domain]},
                )
                result = validate_knowledge_pack(
                    root, "reference-packs/domains/accessibility.toml", exports=exports
                )
                self.assertTrue(result.ok, result.errors)

    def test_pack_fails_when_its_domain_notes_digest_moves(self) -> None:
        # If the domain's own notes change, the notes_digest moves and the pack
        # (pinned to the old digest) must fail.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_knowledge_pack(root, "accessibility", status="active", note_id="acc-note")
            exports = VaultExports(
                index={
                    "index_digest": "index-1",
                    "notes": [
                        {
                            "id": "acc-note",
                            "domain": "accessibility",
                            "status": "accepted",
                            "exposable": True,
                            "exposure_scopes": ["internal-agent"],
                            "sensitivity": "public",
                            "type": "reference",
                        }
                    ],
                },
                domains={
                    "index_digest": "domains-1",
                    "domains": [
                        {
                            "id": "accessibility",
                            "status": "active",
                            "routable": True,
                            "allowed_note_types": ["reference"],
                            "notes_digest": "notes-CHANGED",
                        }
                    ],
                },
            )
            result = validate_knowledge_pack(
                root, "reference-packs/domains/accessibility.toml", exports=exports
            )
            self.assertFalse(result.ok)
            self.assertTrue(
                any("source_domain_notes_digest" in e for e in result.errors), result.errors
            )

    def test_live_route_selects_accessibility_pack_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope = Path(tmp) / "envelope.json"
            envelope.write_text(
                json.dumps(
                    {
                        "intent": {
                            "target_repository": "modelling-knowledge",
                            "requested_capability": "review",
                            "domains": ["accessibility"],
                        },
                        "execution_policy": {"consent_required": True, "max_risk_level": "low"},
                    }
                ),
                encoding="utf-8",
            )

            decision = route_envelope(ROOT, envelope)

            self.assertTrue(decision.ok, decision.errors)
            self.assertEqual(decision.knowledge_domains, [{"id": "accessibility", "source": "request"}])
            self.assertEqual(decision.knowledge_packs, ["reference-packs/domains/accessibility.toml"])


def _write_bundle_and_pack(
    root: Path,
    bundle_skills: list[str],
    pack_skills: list[str],
    routing_key_kind: str | None = "repository",
    default_knowledge: list[str] | None = None,
) -> None:
    (root / "bundles").mkdir()
    (root / "reference-packs").mkdir()
    bundle = {
        "id": "demo",
        "status": "draft",
        "skills": bundle_skills,
        "referencePacks": ["reference-packs/demo.toml"],
    }
    if routing_key_kind is not None:
        bundle["routingKeyKind"] = routing_key_kind
    if default_knowledge is not None:
        bundle["defaultKnowledge"] = default_knowledge
    (root / "bundles" / "demo.bundle.json").write_text(
        json.dumps(bundle),
        encoding="utf-8",
    )
    (root / "reference-packs" / "demo.toml").write_text(
        "\n".join(
            [
                'id = "demo"',
                'status = "draft"',
                'source_repository = "demo"',
                'owner = "demo"',
                f"central_skills = {json.dumps(pack_skills)}",
                "local_agents_stay_in_source = true",
            ]
        ),
        encoding="utf-8",
    )


def _write_envelope(root: Path, requested_capability: str, domains: list[str] | None = None) -> Path:
    intent = {"target_repository": "demo", "requested_capability": requested_capability}
    if domains is not None:
        intent["domains"] = domains
    return _write_envelope_with_intent(root, intent)


def _write_envelope_with_intent(root: Path, intent: dict) -> Path:
    envelope = root / "envelope.json"
    envelope.write_text(
        json.dumps(
            {
                "intent": intent,
                "execution_policy": {"consent_required": True, "max_risk_level": "low"},
            }
        ),
        encoding="utf-8",
    )
    return envelope


def _write_skill(root: Path, skill: str, *, mode: str, domains: list[str]) -> None:
    skill_dir = root / ".claude" / "plugins" / "modeller" / "skills" / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {skill}",
                "description: Demo skill",
                "metadata:",
                "  version: 0.1.0",
                "  author: test",
                "domain_affinity:",
                f"  mode: {mode}",
                "  domains:",
                *[f"    - {domain}" for domain in domains],
                "---",
                "",
                "# Skill",
            ]
        ),
        encoding="utf-8",
    )


def _write_domain_registry(root: Path) -> None:
    domain_dir = root / "reference-packs" / "domains"
    domain_dir.mkdir(parents=True, exist_ok=True)
    domain_dir.joinpath("_registry.toml").write_text(
        "\n".join(
            [
                "schema_version = 1",
                "",
                "[domains.accessibility]",
                'pack = "reference-packs/domains/accessibility.toml"',
                'aliases = ["accessibility-analysis"]',
                "",
                "[domains.product]",
                'pack = "reference-packs/domains/product.toml"',
                'aliases = ["product-design"]',
            ]
        ),
        encoding="utf-8",
    )


def _write_knowledge_pack(root: Path, domain: str, *, status: str, note_id: str | None = None) -> None:
    domain_dir = root / "reference-packs" / "domains"
    domain_dir.mkdir(parents=True, exist_ok=True)
    note_id = note_id or f"{domain}-note"
    domain_dir.joinpath(f"{domain}.toml").write_text(
        "\n".join(
            [
                "schema_version = 1",
                f'id = "{domain}"',
                'kind = "knowledge"',
                f'domain = "{domain}"',
                f'status = "{status}"',
                'source_vault = "modelling-knowledge"',
                'source_domain_notes_digest = "notes-1"',
                'source_domains_digest = "domains-1"',
                'required_scopes = ["internal-agent"]',
                'max_sensitivity = "internal"',
                "",
                "[authority_context]",
                'vault = "modelling-knowledge"',
                'domain_registry = "registry/knowledge-domains.yml"',
                'scope_decision = "0005-knowledge-vault-domain-scope"',
                'knowledge_seam_decision = "0009-vault-side-knowledge-seam"',
                'coordination_decision = "0010-typed-packs-cross-repo-coordination"',
                'checked_at = "2026-07-12"',
                "",
                "[[notes]]",
                f'id = "{note_id}"',
                "required = true",
                'purpose = "test"',
            ]
        ),
        encoding="utf-8",
    )


def _write_conformance_pack(root: Path, case: dict, domain_spec: dict, domains_digest: str) -> None:
    domain = case["domain"]
    domain_dir = root / "reference-packs" / "domains"
    domain_dir.mkdir(parents=True, exist_ok=True)
    domain_dir.joinpath(f"{domain}.toml").write_text(
        "\n".join(
            [
                "schema_version = 1",
                f'id = "{domain}"',
                'kind = "knowledge"',
                f'domain = "{domain}"',
                'status = "active"',
                'source_vault = "modelling-knowledge"',
                f'source_domain_notes_digest = "{domain_spec["notes_digest"]}"',
                f'source_domains_digest = "{domains_digest}"',
                f"required_scopes = {json.dumps(case['required_scopes'])}",
                f'max_sensitivity = "{case["max_sensitivity"]}"',
                "",
                "[authority_context]",
                'vault = "modelling-knowledge"',
                'domain_registry = "registry/knowledge-domains.yml"',
                'scope_decision = "0005-knowledge-vault-domain-scope"',
                'knowledge_seam_decision = "0009-vault-side-knowledge-seam"',
                'coordination_decision = "0010-typed-packs-cross-repo-coordination"',
                'checked_at = "2026-07-12"',
                "",
                "[[notes]]",
                f'id = "{case["note_id"]}"',
                "required = true",
                f'purpose = "{case["id"]}"',
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
