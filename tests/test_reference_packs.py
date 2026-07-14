from __future__ import annotations

import copy
import hashlib
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

    def test_live_accessibility_pack_is_draft_warning_while_domain_deactivated(self) -> None:
        # F-A: domain routability is intentionally disabled in the vault and
        # mirrored locally as a draft pack. Pack validation should keep that
        # state visible without treating it as structural corruption.
        result = validate_knowledge_pack(ROOT, "reference-packs/domains/accessibility.toml")

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "draft")
        self.assertTrue(
            any("knowledge pack is draft" in warning for warning in result.warnings),
            result.warnings,
        )
        self.assertTrue(
            any("domain 'accessibility' is disabled in vault export" in warning for warning in result.warnings),
            result.warnings,
        )

    def test_shared_eligibility_conformance_fixture(self) -> None:
        if not SHARED_ELIGIBILITY_FIXTURE.is_file():
            self.skipTest("sibling modelling-knowledge shared eligibility fixture is not available")
        index = json.loads((VAULT / "docs/dev/vault-index.json").read_text(encoding="utf-8"))
        domains = json.loads((VAULT / "docs/dev/knowledge-domains.json").read_text(encoding="utf-8"))
        exports = VaultExports(index=index, domains=domains)
        domain_specs = {d["id"]: d for d in domains["domains"]}
        fixture = json.loads(SHARED_ELIGIBILITY_FIXTURE.read_text(encoding="utf-8"))
        skipped_live: list[str] = []
        asserted_live = 0
        for case in fixture["cases"]:
            domain_spec = domain_specs.get(case["domain"], {})
            # F-A deactivation tolerance: the live cases are routability-
            # dependent, so when the live vault export marks the case's domain
            # not active/routable (as accessibility now is), the expected
            # result cannot hold. Record + continue rather than assert-fail or
            # abort the whole test (self.skipTest would stop the synthetic
            # cases from running too); keep the real assertion for
            # active/routable domains.
            if domain_spec.get("status") != "active" or domain_spec.get("routable") is not True:
                skipped_live.append(
                    f"{case['id']} (domain {case['domain']!r} not active/routable in vault export)"
                )
                continue
            with self.subTest(case=case["id"]):
                asserted_live += 1
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _write_domain_registry(root)
                    _write_conformance_pack(root, case, domain_spec, domains["index_digest"])
                    result = validate_knowledge_pack(
                        root, f"reference-packs/domains/{case['domain']}.toml", exports=exports
                    )
                    self.assertIs(result.ok, case["expected"], result.errors)

        for case in fixture.get("synthetic_cases", []):
            if "modeller-agents" not in case.get("applies_to", []):
                continue
            with self.subTest(synthetic_case=case["id"]):
                synth_exports, notes_digest, domains_index_digest = _build_synthetic_exports(
                    index, domains, case
                )
                synth_domain_spec = {
                    d["id"]: d for d in synth_exports.domains["domains"]
                }[case["domain"]]
                pack_overrides = dict(case.get("pack_overrides", {}))
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _write_domain_registry(root)
                    _write_conformance_pack(
                        root,
                        case,
                        synth_domain_spec,
                        domains_index_digest,
                        pack_overrides=pack_overrides,
                    )
                    result = validate_knowledge_pack(
                        root,
                        f"reference-packs/domains/{case['domain']}.toml",
                        exports=synth_exports,
                    )
                    if case["expected"]:
                        self.assertTrue(result.ok, result.errors)
                    else:
                        self.assertFalse(result.ok, result.errors)
                        expected_error = case.get("expected_error_contains")
                        if expected_error:
                            self.assertTrue(
                                any(expected_error in err for err in result.errors),
                                f"no error contains {expected_error!r}: {result.errors}",
                            )

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

    def test_live_route_does_not_select_accessibility_pack_while_deactivated(self) -> None:
        # F-A: domain routability deactivated (registry draft/routable:false);
        # revert this expectation when routability is restored after 0010
        # general-scope acceptance + DR-1 cure. This test used to assert routing
        # SELECTS the accessibility knowledge pack with provenance (ok, one
        # knowledge_domain, one knowledge_pack). With accessibility no longer
        # active/routable in the vault export, the knowledge axis for that
        # domain is unavailable: routing must NOT select it, and the knowledge
        # pack validation error surfaces on the decision. The base/repo route
        # (target repository, skill, bundle, reference pack) still resolves.
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

            # Knowledge axis is unavailable for the deactivated domain: nothing
            # selected on either the domain or pack axis.
            self.assertEqual(decision.knowledge_domains, [])
            self.assertEqual(decision.knowledge_packs, [])
            # The decision fails and carries a clear disabled-domain error.
            self.assertFalse(decision.ok, decision.errors)
            self.assertTrue(
                any("knowledge domain 'accessibility' is disabled; pack not loaded" in e for e in decision.errors),
                decision.errors,
            )
            # The non-knowledge (base/repo) route still resolves normally.
            self.assertEqual(decision.target_repository, "modelling-knowledge")
            self.assertEqual(decision.skill, "review")
            self.assertEqual(decision.bundle, "modelling-knowledge")
            self.assertEqual(
                decision.reference_packs, ["reference-packs/modelling-knowledge.toml"]
            )


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


def _write_conformance_pack(
    root: Path,
    case: dict,
    domain_spec: dict,
    domains_digest: str,
    pack_overrides: dict | None = None,
) -> None:
    domain = case["domain"]
    # The pack stamps CURRENT digests by default so a well-formed active pack
    # passes currency. pack_overrides lets a conformance case inject a stale
    # value (e.g. source_domain_notes_digest) to exercise currency FAILURE.
    pack_overrides = pack_overrides or {}
    notes_digest = pack_overrides.get("source_domain_notes_digest", domain_spec["notes_digest"])
    src_domains_digest = pack_overrides.get("source_domains_digest", domains_digest)
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
                f'source_domain_notes_digest = "{notes_digest}"',
                f'source_domains_digest = "{src_domains_digest}"',
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


# --- Synthetic-export digest helpers -------------------------------------
# These recompute per-domain notes_digest and the domains index_digest exactly
# the way modeller-memory's vault_doctor exporter does (see
# vault_doctor/export.py: _canonical_json / _digest / _notes_digest_by_domain /
# build_domains). Keeping the recomputation in lock-step with the exporter is
# what lets a mutated synthetic export stay currency-valid, so a VALID synthetic
# case passes parity while the STALE-DIGEST case (injected via pack_overrides)
# fails parity.
_EXPORT_SCHEMA_VERSION = 1


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(obj) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _domain_notes_digest(index_notes: list[dict], domain: str) -> str:
    entries = [n for n in index_notes if n.get("domain") == domain]
    entries.sort(key=lambda e: (e.get("id") or "", e.get("canonical_path") or ""))
    return _digest({"schema_version": _EXPORT_SCHEMA_VERSION, "domain": domain, "notes": entries})


def _domains_index_digest(domain_entries: list[dict]) -> str:
    core = {"schema_version": _EXPORT_SCHEMA_VERSION, "domains": sorted(domain_entries, key=lambda e: e["id"])}
    return _digest(core)


def _build_synthetic_exports(live_index: dict, live_domains: dict, case: dict):
    """Return (VaultExports, notes_digest, domains_index_digest) for a synthetic case.

    Starts from the live exports, merges the case's synthetic_note into the
    index notes that validate_knowledge_pack reads (exports.index['notes'], keyed
    by id), applies synthetic_domain_overrides to that domain's entry, then
    recomputes the domain notes_digest and the domains index_digest the same way
    the exporter does so a well-formed pack pinned to the recomputed digests is
    current for the mutated export.
    """
    index = copy.deepcopy(live_index)
    domains = copy.deepcopy(live_domains)
    domain = case["domain"]

    synthetic_note = case.get("synthetic_note")
    if synthetic_note is not None:
        notes = index.setdefault("notes", [])
        # Merge by stable id (replace an existing row with the same id, else append).
        notes = [n for n in notes if n.get("id") != synthetic_note["id"]]
        notes.append(copy.deepcopy(synthetic_note))
        index["notes"] = notes

    overrides = case.get("synthetic_domain_overrides", {})
    recomputed_notes_digest = _domain_notes_digest(index.get("notes", []), domain)
    for entry in domains.get("domains", []):
        if entry.get("id") == domain:
            entry.update(overrides)
            entry["notes_digest"] = recomputed_notes_digest
            break

    recomputed_domains_digest = _domains_index_digest(domains.get("domains", []))
    domains["index_digest"] = recomputed_domains_digest
    index["index_digest"] = index.get("index_digest", "")

    exports = VaultExports(index=index, domains=domains)
    return exports, recomputed_notes_digest, recomputed_domains_digest


if __name__ == "__main__":
    unittest.main()
