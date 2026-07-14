from __future__ import annotations


CAPABILITY_SKILLS = {
    "antagonist-review": "antagonist-review",
    "backend-align": "backend-align",
    "backend-contract-check": "backend-contract-check",
    "backend-scaffold": "backend-scaffold",
    "backend_run": "backend-contract-check",
    "run_backend": "backend-contract-check",
    "memory-recon": "memory-recon",
    "pipeline-fix": "pipeline-fix",
    "pipeline-review": "pipeline-review",
    "pipeline-smoke": "pipeline-smoke",
    "recon": "memory-recon",
    "orchestrate": "orchestrate",
    "review": "review",
    "source-boundary-check": "source-boundary-check",
    "workflow": "workflow",
}


def canonical_skill_for_capability(requested_capability: str | None) -> str | None:
    capability = str(requested_capability or "workflow")
    return CAPABILITY_SKILLS.get(capability)


def direct_skill_capabilities() -> set[str]:
    return {skill for capability, skill in CAPABILITY_SKILLS.items() if capability == skill}
