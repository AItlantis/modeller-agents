from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .capabilities import CAPABILITY_SKILLS
from .contracts import resolve_schema_dir
from .knowledge_packs import (
    load_vault_exports,
    validate_bundle_default_knowledge,
    validate_domain_registry,
    validate_knowledge_pack,
    validate_skill_domain_affinities,
)
from .reference_packs import validate_reference_pack
from .runtime import is_installed_runtime, runtime_path, runtime_relative_path, runtime_root
from .toml_compat import load_toml


FRONTMATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---\n", re.DOTALL)


@dataclass
class DoctorResult:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    readiness_blockers: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "root": str(self.root),
            "skills": self.skills,
            "backends": self.backends,
            "warnings": self.warnings,
            "errors": self.errors,
            "readiness_blockers": self.readiness_blockers,
        }

    def format(self) -> str:
        lines = [f"modeller doctor: {'OK' if self.ok else 'FAIL'}", f"root: {self.root}"]
        lines.append(f"skills: {len(self.skills)}")
        for skill in self.skills:
            lines.append(f"  - {skill}")
        lines.append(f"backends: {len(self.backends)}")
        for backend in self.backends:
            lines.append(f"  - {backend}")
        if self.warnings:
            lines.append("warnings:")
            lines.extend(f"  - {item}" for item in self.warnings)
        if self.errors:
            lines.append("errors:")
            lines.extend(f"  - {item}" for item in self.errors)
        if self.readiness_blockers:
            lines.append("readiness blockers:")
            for blocker in self.readiness_blockers:
                lines.append(f"  - {blocker['code']}: {blocker['message']}")
        return "\n".join(lines)


def run_doctor(root: Path, *, strict: bool = False) -> DoctorResult:
    result = DoctorResult(root=root)
    installed_runtime = _is_installed_runtime(root)
    _check_required_paths(root, result, installed_runtime=installed_runtime)
    if installed_runtime:
        _check_install_manifest(root, result)
    else:
        _check_packaging(root, result)
    _check_plugin(root, result)
    _check_skills(root, result)
    if not installed_runtime:
        _check_docs_skill_index(root, result)
    _check_bundles(root, result)
    _check_knowledge_axis(root, result)
    _check_workflows(root, result)
    _check_reference_packs(root, result, strict=strict)
    if not installed_runtime:
        _check_skill_surface(root, result)
    else:
        _check_installed_skill_surface(root, result)
    _check_backends(root, result, strict=strict)
    _check_vendors(root, result, strict=strict)
    _check_contract_schemas(root, result, strict=strict)
    return result


def _is_installed_runtime(root: Path) -> bool:
    return is_installed_runtime(root)


def _check_required_paths(root: Path, result: DoctorResult, *, installed_runtime: bool = False) -> None:
    root_required = [
        ".claude/settings.json",
        ".claude/plugins/modeller/.claude-plugin/plugin.json",
        ".claude/plugins/modeller/.claude-plugin/marketplace.json",
    ]
    runtime_required = [
        "backends.toml",
        "schemas/context-receipt.schema.json",
        "schemas/run-manifest.schema.json",
        "vendors.toml",
    ]
    if installed_runtime:
        root_required.extend([".modeller/install-manifest.json", "sitecustomize.py"])
        runtime_required.extend(
            [
                "method/workflows",
                "method/templates/workflow-artifact.md",
                "reference-packs",
                "bundles",
            ]
        )
    else:
        root_required.extend(["README.md", "AGENTS.md", "pyproject.toml", "modeller-modules.yaml"])
    for rel in root_required:
        if not (root / rel).exists():
            result.errors.append(f"missing required path: {rel}")
    assets = runtime_root(root)
    for rel in runtime_required:
        if not (assets / rel).exists():
            result.errors.append(f"missing required path: {runtime_relative_path(root, assets / rel)}")


def _check_install_manifest(root: Path, result: DoctorResult) -> None:
    manifest = _load_json(root / ".modeller/install-manifest.json", result)
    if not manifest:
        return
    if manifest.get("schema_version") != 1:
        result.errors.append(".modeller/install-manifest.json schema_version must be 1")
    if manifest.get("installer") != "modeller-agents":
        result.errors.append(".modeller/install-manifest.json installer must be modeller-agents")
    if Path(str(manifest.get("target_root", ""))).resolve() != root.resolve():
        result.errors.append(".modeller/install-manifest.json target_root must match inspected root")
    source_root = manifest.get("source_root")
    if not isinstance(source_root, str) or not source_root.strip():
        result.errors.append(".modeller/install-manifest.json source_root must be a non-empty string")
    elif not Path(source_root).exists():
        result.warnings.append(f"install source_root no longer exists: {source_root}")
    copied_plugin = manifest.get("copied_plugin")
    if copied_plugin != ".claude/plugins/modeller":
        result.errors.append(".modeller/install-manifest.json copied_plugin must be .claude/plugins/modeller")
    bootstrap = manifest.get("python_path_bootstrap")
    if bootstrap != "sitecustomize.py":
        result.errors.append(".modeller/install-manifest.json python_path_bootstrap must be sitecustomize.py")
    elif not (root / bootstrap).exists():
        result.errors.append("missing Python import bootstrap: sitecustomize.py")
    if manifest.get("include_runtime_assets") is not True:
        result.warnings.append("install manifest says runtime assets were not copied into this target")
    runtime_rel = manifest.get("runtime_root")
    if runtime_rel:
        if not isinstance(runtime_rel, str):
            result.errors.append(".modeller/install-manifest.json runtime_root must be a string when set")
        elif Path(runtime_rel).is_absolute() or ".." in Path(runtime_rel).parts:
            result.errors.append(".modeller/install-manifest.json runtime_root must be a safe relative path")
        elif not (root / runtime_rel).exists():
            result.errors.append(f"install manifest runtime_root does not exist: {runtime_rel}")


def _check_packaging(root: Path, result: DoctorResult) -> None:
    data = _load_toml(root / "pyproject.toml", result)
    if not data:
        return
    build_system = data.get("build-system", {})
    if build_system.get("build-backend") != "hatchling.build":
        result.errors.append("pyproject.toml build-system.build-backend must be hatchling.build")
    requires = build_system.get("requires", [])
    if not isinstance(requires, list) or not any(str(item).startswith("hatchling") for item in requires):
        result.errors.append("pyproject.toml build-system.requires must include hatchling")

    project = data.get("project", {})
    if project.get("name") != "modeller-agents":
        result.errors.append("pyproject.toml project.name must be modeller-agents")
    if not isinstance(project.get("version"), str) or not project.get("version"):
        result.errors.append("pyproject.toml project.version must be a non-empty string")
    readme = project.get("readme")
    if not isinstance(readme, str) or not (root / readme).exists():
        result.errors.append("pyproject.toml project.readme must point to an existing file")
    license_file = project.get("license", {}).get("file") if isinstance(project.get("license"), dict) else ""
    if not license_file or not (root / str(license_file)).exists():
        result.errors.append("pyproject.toml project.license.file must point to an existing file")

    scripts = project.get("scripts", {})
    if scripts.get("modeller") != "modeller.cli:main":
        result.errors.append("pyproject.toml project.scripts.modeller must be modeller.cli:main")
    elif not (root / "src/modeller/cli.py").exists():
        result.errors.append("pyproject.toml project.scripts.modeller target src/modeller/cli.py is missing")

    hatch = data.get("tool", {}).get("hatch", {}) if isinstance(data.get("tool"), dict) else {}
    wheel = hatch.get("build", {}).get("targets", {}).get("wheel", {}) if isinstance(hatch.get("build"), dict) else {}
    packages = wheel.get("packages", [])
    if "src/modeller" not in packages:
        result.errors.append("pyproject.toml wheel packages must include src/modeller")
    if "src/modeller_agents" not in packages:
        result.errors.append("pyproject.toml wheel packages must include src/modeller_agents")
    if not (root / "src/modeller/__init__.py").exists():
        result.errors.append("package initializer missing: src/modeller/__init__.py")
    if not (root / "src/modeller_agents/__init__.py").exists():
        result.errors.append("compat package initializer missing: src/modeller_agents/__init__.py")
    force_include = wheel.get("force-include", {})
    expected_assets = {
        ".claude/plugins/modeller": "modeller/runtime/.claude/plugins/modeller",
        ".claude/settings.json": "modeller/runtime/.claude/settings.json",
        ".mcp.json.example": "modeller/runtime/.mcp.json.example",
        "method": "modeller/runtime/method",
        "reference-packs": "modeller/runtime/reference-packs",
        "bundles": "modeller/runtime/bundles",
        "schemas": "modeller/runtime/schemas",
        "backends.toml": "modeller/runtime/backends.toml",
        "vendors.toml": "modeller/runtime/vendors.toml",
    }
    for source, target in expected_assets.items():
        if force_include.get(source) != target:
            result.errors.append(f"pyproject.toml wheel force-include must map {source} to {target}")
        if not (root / source).exists():
            result.errors.append(f"pyproject.toml wheel force-include source is missing: {source}")


def _check_plugin(root: Path, result: DoctorResult) -> None:
    settings = _load_json(root / ".claude/settings.json", result)
    plugin = _load_json(root / ".claude/plugins/modeller/.claude-plugin/plugin.json", result)
    marketplace = _load_json(root / ".claude/plugins/modeller/.claude-plugin/marketplace.json", result)
    if not settings or not plugin or not marketplace:
        return
    name = plugin.get("name")
    if name != "modeller":
        result.errors.append("plugin.json name must be 'modeller'")
    enabled = settings.get("enabledPlugins", {})
    if "modeller@modeller-marketplace" not in enabled:
        result.errors.append("settings.json must enable modeller@modeller-marketplace")
    plugins = marketplace.get("plugins", [])
    if not plugins or plugins[0].get("name") != name:
        result.errors.append("marketplace plugin name must match plugin.json")


def _check_skills(root: Path, result: DoctorResult) -> None:
    skill_root = root / ".claude/plugins/modeller/skills"
    if not skill_root.exists():
        result.errors.append("missing skill root")
        return
    for skill_dir in sorted(path for path in skill_root.iterdir() if path.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            result.errors.append(f"missing SKILL.md for skill {skill_dir.name}")
            continue
        text = skill_file.read_text(encoding="utf-8")
        frontmatter = _frontmatter(text)
        if not frontmatter:
            result.errors.append(f"missing front matter in {skill_file}")
            continue
        name = _frontmatter_value(frontmatter, "name")
        description = _frontmatter_value(frontmatter, "description")
        version = _frontmatter_nested_value(frontmatter, "metadata", "version")
        author = _frontmatter_nested_value(frontmatter, "metadata", "author")
        if name != skill_dir.name:
            result.errors.append(f"skill {skill_dir.name} has mismatched name {name!r}")
        if not description:
            result.errors.append(f"skill {skill_dir.name} missing description")
        if not version:
            result.errors.append(f"skill {skill_dir.name} missing metadata.version")
        if not author:
            result.errors.append(f"skill {skill_dir.name} missing metadata.author")
        result.skills.append(skill_dir.name)


def _check_bundles(root: Path, result: DoctorResult) -> None:
    known_skills = set(result.skills)
    assets = runtime_root(root)
    for bundle_file in sorted((assets / "bundles").glob("*.bundle.json")):
        bundle = _load_json(bundle_file, result)
        if not bundle:
            continue
        expected_id = bundle_file.name.removesuffix(".bundle.json")
        if bundle.get("id") != expected_id:
            result.errors.append(f"{bundle_file.name} id must match filename stem {expected_id!r}")
        if bundle.get("status") not in {"draft", "active", "deprecated"}:
            result.errors.append(f"{bundle_file.name} has invalid status")
        if bundle.get("routingKeyKind") not in {"repository", "repository-class"}:
            result.errors.append(f"{bundle_file.name} must declare routingKeyKind repository or repository-class")
        result.errors.extend(validate_bundle_default_knowledge(bundle_file.name, bundle))
        skills = bundle.get("skills")
        if not isinstance(skills, list) or not skills or not all(isinstance(skill, str) and skill for skill in skills):
            result.errors.append(f"{bundle_file.name} must declare non-empty string-array skills")
            skills = []
        reference_packs = bundle.get("referencePacks")
        if (
            not isinstance(reference_packs, list)
            or not reference_packs
            or not all(isinstance(path, str) and path for path in reference_packs)
        ):
            result.errors.append(f"{bundle_file.name} must select at least one reference pack")
        for skill in skills:
            if skill not in known_skills:
                result.errors.append(f"{bundle_file.name} references unknown skill {skill}")


def _check_reference_packs(root: Path, result: DoctorResult, *, strict: bool) -> None:
    checks = {}
    assets = runtime_root(root)
    for bundle_file in sorted((assets / "bundles").glob("*.bundle.json")):
        bundle = _load_json(bundle_file, result)
        if not bundle:
            continue
        bundle_skills = set(bundle.get("skills", []))
        authorized_skills: set[str] = set()
        for rel in bundle.get("referencePacks", []):
            if str(rel) not in checks:
                check = validate_reference_pack(root, str(rel))
                checks[str(rel)] = check
                result.errors.extend(check.errors)
                result.warnings.extend(check.warnings)
                if strict and check.status != "active":
                    _add_readiness_blocker(
                        result,
                        code="reference-pack-not-active",
                        message=f"strict readiness requires reference pack {rel} to be active",
                        path=str(rel),
                        remediation="Close draft-only decisions, verify bundle/pack scope, then set status = 'active'.",
                    )
            check = checks[str(rel)]
            if check.ok:
                authorized_skills.update(check.skills)
        missing_from_pack_union = sorted(bundle_skills.difference(authorized_skills))
        if missing_from_pack_union:
            result.errors.append(
                f"{bundle_file.name} references skills not authorized by selected reference packs: "
                f"{', '.join(missing_from_pack_union)}"
            )
    for pack_file in sorted((assets / "reference-packs").glob("*.toml")):
        rel = pack_file.relative_to(assets).as_posix()
        if rel not in checks:
            result.warnings.append(f"reference pack is not used by any bundle: {rel}")


def _check_knowledge_axis(root: Path, result: DoctorResult) -> None:
    result.errors.extend(validate_skill_domain_affinities(root))
    has_default_knowledge = False
    assets = runtime_root(root)
    for bundle_file in sorted((assets / "bundles").glob("*.bundle.json")):
        bundle = _load_json(bundle_file, result)
        if bundle.get("defaultKnowledge"):
            has_default_knowledge = True
    domain_root = assets / "reference-packs" / "domains"
    if not domain_root.exists() and not has_default_knowledge:
        return
    exports = load_vault_exports(root)
    result.warnings.extend(exports.warnings)
    result.errors.extend(validate_domain_registry(root, exports=exports, warnings=result.warnings))
    for pack_file in sorted(domain_root.glob("*.toml")) if domain_root.exists() else []:
        if pack_file.name == "_registry.toml":
            continue
        rel = pack_file.relative_to(assets).as_posix()
        check = validate_knowledge_pack(root, rel, exports=exports)
        result.errors.extend(check.errors)
        result.warnings.extend(check.warnings)


def _check_docs_skill_index(root: Path, result: DoctorResult) -> None:
    index = root / "docs/skills/modeller/SKILL_INDEX.md"
    if not index.exists():
        result.errors.append("missing docs/skills/modeller/SKILL_INDEX.md")
        return
    text = index.read_text(encoding="utf-8")
    for skill in result.skills:
        if f"`{skill}`" not in text:
            result.errors.append(f"skill docs index missing {skill}")


def _check_skill_surface(root: Path, result: DoctorResult) -> None:
    known = set(result.skills)
    modules = _load_modules_manifest(root / "modeller-modules.yaml", result)
    if modules:
        _compare_sets("modeller-modules.yaml skills", set(modules.get("skills", [])), "plugin skill dirs", known, result)
        actual_bundle_paths = {
            path.relative_to(root).as_posix() for path in sorted((root / "bundles").glob("*.bundle.json"))
        }
        _compare_sets("modeller-modules.yaml bundles", set(modules.get("bundles", [])), "bundle files", actual_bundle_paths, result)
        actual_pack_paths = {
            path.relative_to(root).as_posix() for path in sorted((root / "reference-packs").glob("*.toml"))
        }
        _compare_sets(
            "modeller-modules.yaml reference_packs",
            set(modules.get("reference_packs", [])),
            "reference pack files",
            actual_pack_paths,
            result,
        )
    index_skills = _markdown_seed_skills(root / "docs/skills/modeller/SKILL_INDEX.md", result, "docs skill index")
    if index_skills is not None:
        _compare_sets("docs skill index", index_skills, "plugin skill dirs", known, result)
    readme_skills = _markdown_seed_skills(root / ".claude/plugins/modeller/README.md", result, "plugin README")
    if readme_skills is not None:
        _compare_sets("plugin README seed skills", readme_skills, "plugin skill dirs", known, result)

    routed_skills = set(CAPABILITY_SKILLS.values())
    _compare_sets("route capability skills", routed_skills, "plugin skill dirs", known, result)
    missing_direct_capabilities = sorted(skill for skill in known if CAPABILITY_SKILLS.get(skill) != skill)
    if missing_direct_capabilities:
        result.errors.append(
            "CAPABILITY_SKILLS must map every canonical skill name directly to itself: "
            + ", ".join(missing_direct_capabilities)
        )

    for bundle_file in sorted((root / "bundles").glob("*.bundle.json")):
        bundle = _load_json(bundle_file, result)
        if not bundle:
            continue
        bundle_skills = set(bundle.get("skills", []))
        unknown = sorted(bundle_skills.difference(known))
        unrouted = sorted(bundle_skills.difference(routed_skills))
        if unknown:
            result.errors.append(f"{bundle_file.name} has skills missing from plugin skill dirs: {', '.join(unknown)}")
        if unrouted:
            result.errors.append(f"{bundle_file.name} has skills missing from CAPABILITY_SKILLS: {', '.join(unrouted)}")

    for pack_file in sorted((root / "reference-packs").glob("*.toml")):
        data = _load_toml(pack_file, result)
        skills = data.get("central_skills", []) if data else []
        if not isinstance(skills, list):
            continue
        unknown = sorted(set(skills).difference(known))
        unrouted = sorted(set(skills).difference(routed_skills))
        rel = pack_file.relative_to(root).as_posix()
        if unknown:
            result.errors.append(f"{rel} has skills missing from plugin skill dirs: {', '.join(unknown)}")
        if unrouted:
            result.errors.append(f"{rel} has skills missing from CAPABILITY_SKILLS: {', '.join(unrouted)}")


def _check_installed_skill_surface(root: Path, result: DoctorResult) -> None:
    known = set(result.skills)
    routed_skills = set(CAPABILITY_SKILLS.values())
    missing_direct_capabilities = sorted(skill for skill in known if CAPABILITY_SKILLS.get(skill) != skill)
    if missing_direct_capabilities:
        result.errors.append(
            "CAPABILITY_SKILLS must map every canonical skill name directly to itself: "
            + ", ".join(missing_direct_capabilities)
        )
    assets = runtime_root(root)
    for bundle_file in sorted((assets / "bundles").glob("*.bundle.json")):
        bundle = _load_json(bundle_file, result)
        if not bundle:
            continue
        bundle_skills = set(bundle.get("skills", []))
        unknown = sorted(bundle_skills.difference(known))
        unrouted = sorted(bundle_skills.difference(routed_skills))
        if unknown:
            result.errors.append(f"{bundle_file.name} has skills missing from plugin skill dirs: {', '.join(unknown)}")
        if unrouted:
            result.errors.append(f"{bundle_file.name} has skills missing from CAPABILITY_SKILLS: {', '.join(unrouted)}")
    for pack_file in sorted((assets / "reference-packs").glob("*.toml")):
        data = _load_toml(pack_file, result)
        skills = data.get("central_skills", []) if data else []
        if not isinstance(skills, list):
            continue
        unknown = sorted(set(skills).difference(known))
        unrouted = sorted(set(skills).difference(routed_skills))
        rel = pack_file.relative_to(assets).as_posix()
        if unknown:
            result.errors.append(f"{rel} has skills missing from plugin skill dirs: {', '.join(unknown)}")
        if unrouted:
            result.errors.append(f"{rel} has skills missing from CAPABILITY_SKILLS: {', '.join(unrouted)}")


def _compare_sets(left_name: str, left: set[str], right_name: str, right: set[str], result: DoctorResult) -> None:
    missing = sorted(right.difference(left))
    extra = sorted(left.difference(right))
    if missing:
        result.errors.append(f"{left_name} missing entries from {right_name}: {', '.join(missing)}")
    if extra:
        result.errors.append(f"{left_name} has unknown entries not in {right_name}: {', '.join(extra)}")


def _markdown_seed_skills(path: Path, result: DoctorResult, label: str) -> set[str] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        result.errors.append(f"missing {label}: {path.relative_to(result.root).as_posix()}")
        return None
    in_section = False
    skills: set[str] = set()
    for line in lines:
        if line.strip() == "## Seed Skills":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            match = re.match(r"- `([^`]+)`$", line.strip())
            if match:
                skills.add(match.group(1))
    return skills


def _load_modules_manifest(path: Path, result: DoctorResult) -> dict[str, list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        result.errors.append("missing modeller-modules.yaml")
        return {}
    manifest = {"skills": [], "bundles": [], "reference_packs": []}
    section = ""
    pending_bundle = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            pending_bundle = False
            continue
        if section in {"skills", "reference_packs"} and stripped.startswith("- "):
            manifest[section].append(stripped[2:].strip())
        elif section == "bundles":
            if stripped.startswith("- id:"):
                pending_bundle = True
            elif pending_bundle and stripped.startswith("path:"):
                manifest["bundles"].append(stripped.split(":", 1)[1].strip())
                pending_bundle = False
    return manifest


def _check_workflows(root: Path, result: DoctorResult) -> None:
    workflow_dir = runtime_path(root, "method", "workflows")
    template_path = runtime_path(root, "method", "templates", "workflow-artifact.md")
    if not workflow_dir.exists():
        result.errors.append("missing workflow directory: method/workflows")
        return
    workflows = sorted(workflow_dir.glob("*.workflow.json"))
    if not workflows:
        result.errors.append("missing workflow definitions under method/workflows")
    for workflow_file in workflows:
        workflow = _load_json(workflow_file, result)
        if workflow:
            _check_workflow_definition(workflow_file, workflow, result)
    if not template_path.exists():
        result.errors.append("missing workflow artifact template: method/templates/workflow-artifact.md")
        return
    template = template_path.read_text(encoding="utf-8")
    for token in [
        "{workflow_id}",
        "{run_id}",
        "{artifact}",
        "{step}",
        "{title}",
        "## Purpose",
        "## Evidence",
        "## Decisions Or Outputs",
        "## Verification",
    ]:
        if token not in template:
            result.errors.append(f"workflow artifact template missing {token}")


def _check_workflow_definition(workflow_file: Path, workflow: dict, result: DoctorResult) -> None:
    rel = workflow_file.relative_to(result.root).as_posix()
    workflow_id = workflow.get("workflow_id")
    expected_id = workflow_file.name.removesuffix(".workflow.json")
    if workflow_id != expected_id:
        result.errors.append(f"{rel}: workflow_id must match filename stem {expected_id!r}")
    for key in ["artifact_root", "state_path"]:
        value = workflow.get(key)
        if not isinstance(value, str) or "{run_id}" not in value:
            result.errors.append(f"{rel}: {key} must be a string containing {{run_id}}")
    artifacts = workflow.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        result.errors.append(f"{rel}: artifacts must be a non-empty object")
        artifacts = {}
    requirements = workflow.get("artifact_requirements")
    if not isinstance(requirements, dict):
        result.errors.append(f"{rel}: artifact_requirements must be an object")
        requirements = {}
    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        result.errors.append(f"{rel}: steps must be a non-empty array")
        return
    seen_artifacts: set[str] = set()
    for index, step in enumerate(steps):
        prefix = f"{rel}: steps[{index}]"
        if not isinstance(step, dict):
            result.errors.append(f"{prefix} must be an object")
            continue
        for key in ["id", "title", "owner", "exit_gate"]:
            if not isinstance(step.get(key), str) or not step.get(key).strip():
                result.errors.append(f"{prefix}.{key} must be a non-empty string")
        required_artifacts = step.get("required_artifacts")
        if not isinstance(required_artifacts, list) or not required_artifacts:
            result.errors.append(f"{prefix}.required_artifacts must be a non-empty array")
            continue
        for artifact in required_artifacts:
            if not isinstance(artifact, str) or not artifact:
                result.errors.append(f"{prefix}.required_artifacts contains an invalid artifact id")
                continue
            if artifact in seen_artifacts:
                result.errors.append(f"{rel}: artifact {artifact!r} is required by multiple steps")
            seen_artifacts.add(artifact)
            if artifact not in artifacts:
                result.errors.append(f"{rel}: artifact {artifact!r} is missing from artifacts")
            terms = requirements.get(artifact, {}).get("required_terms")
            if not isinstance(terms, list) or not terms or not all(isinstance(term, str) and term for term in terms):
                result.errors.append(f"{rel}: artifact {artifact!r} must declare non-empty required_terms")


def _check_backends(root: Path, result: DoctorResult, *, strict: bool) -> None:
    data = _load_toml(runtime_path(root, "backends.toml"), result)
    for name, cfg in data.get("backend", {}).items():
        result.backends.append(name)
        if cfg.get("backend_id") != name:
            result.errors.append(f"backend {name} backend_id mismatch")
        if cfg.get("status") not in {"planned", "active", "disabled"}:
            result.errors.append(f"backend {name} has invalid status")
        if strict and cfg.get("status") == "planned":
            _add_readiness_blocker(
                result,
                code="backend-not-active",
                message=f"strict readiness requires backend {name} to be active, not planned",
                path="backends.toml",
                remediation="Create/verify backend.json, run the backend smoke through modeller.cli run, then mark the backend active.",
            )
        if strict and not str(cfg.get("expected_contract", "")).strip():
            _add_readiness_blocker(
                result,
                code="backend-contract-unpinned",
                message=f"strict readiness requires backend {name} to declare expected_contract",
                path="backends.toml",
                remediation="Set expected_contract to the modeller-pipelines contract version verified by backend smoke.",
            )


def _check_vendors(root: Path, result: DoctorResult, *, strict: bool) -> None:
    data = _load_toml(runtime_path(root, "vendors.toml"), result)
    for name, cfg in data.get("vendor", {}).items():
        if cfg.get("writable") is not False:
            result.errors.append(f"vendor {name} must be writable = false")
        prefix = cfg.get("prefix")
        if not prefix or not str(prefix).startswith("vendor/"):
            result.errors.append(f"vendor {name} prefix must be under vendor/")
        if cfg.get("status") == "planned":
            result.warnings.append(f"vendor {name} is planned and not synced yet")
            if strict:
                _add_readiness_blocker(
                    result,
                    code="vendor-not-synced",
                    message=f"strict readiness requires vendor {name} to be synced, not planned",
                    path=str(prefix or ""),
                    remediation="Run the planned vendor sync after confirming remote/ref, then set status to synced/active.",
                )
        pinned = cfg.get("pinned")
        if not pinned or not str(pinned).strip():
            result.warnings.append(f"vendor {name} is not pinned to an immutable revision")
            if strict:
                _add_readiness_blocker(
                    result,
                    code="vendor-not-pinned",
                    message=f"strict readiness requires vendor {name} to be pinned",
                    path=str(prefix or ""),
                    remediation="Record the immutable revision that exactly matches the vendored content.",
                )


def _check_contract_schemas(root: Path, result: DoctorResult, *, strict: bool) -> None:
    schema_dir = resolve_schema_dir(root)
    if schema_dir is None:
        result.errors.append("modeller-pipelines contract schemas are not available")
        return
    required = [
        "backend.schema.json",
        "pipeline.schema.json",
        "result.schema.json",
        "run-config.schema.json",
        "step-result.schema.json",
    ]
    for name in required:
        if not (schema_dir / name).exists():
            result.errors.append(f"missing contract schema: {schema_dir / name}")
    if "vendor" not in schema_dir.parts:
        result.warnings.append(f"using sibling modeller-pipelines schemas: {schema_dir}")
        if strict:
            _add_readiness_blocker(
                result,
                code="schema-sibling-fallback",
                message=f"strict readiness requires vendored modeller-pipelines schemas, not sibling fallback: {schema_dir}",
                path=str(schema_dir),
                remediation="Vendor modeller-pipelines under vendor/modeller-pipelines and pin the exact revision.",
            )


def _add_readiness_blocker(
    result: DoctorResult,
    *,
    code: str,
    message: str,
    path: str = "",
    remediation: str = "",
) -> None:
    result.errors.append(message)
    result.readiness_blockers.append(
        {
            "code": code,
            "message": message,
            "path": path,
            "remediation": remediation,
        }
    )


def _load_json(path: Path, result: DoctorResult) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result.errors.append(f"missing json file: {path.relative_to(result.root)}")
    except json.JSONDecodeError as exc:
        result.errors.append(f"invalid json {path.relative_to(result.root)}: {exc}")
    return {}


def _load_toml(path: Path, result: DoctorResult) -> dict:
    try:
        return load_toml(path)
    except FileNotFoundError:
        result.errors.append(f"missing toml file: {path.relative_to(result.root)}")
    except Exception as exc:
        result.errors.append(f"invalid toml {path.relative_to(result.root)}: {exc}")
    return {}


def _frontmatter(text: str) -> str:
    match = FRONTMATTER_RE.match(text)
    return match.group("body") if match else ""


def _frontmatter_value(frontmatter: str, key: str) -> str:
    for line in frontmatter.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


def _frontmatter_nested_value(frontmatter: str, parent: str, key: str) -> str:
    lines = frontmatter.splitlines()
    in_parent = False
    for line in lines:
        if line.startswith(f"{parent}:"):
            in_parent = True
            continue
        if in_parent:
            if line and not line.startswith(" "):
                return ""
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                return stripped.split(":", 1)[1].strip()
    return ""
