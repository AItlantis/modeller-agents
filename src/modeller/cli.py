from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backend import check_backend, format_backend_check, list_backend_ids
from .doctor import run_doctor
from .install import install_plugin
from .memory_transport import transport_memory_candidate
from .planning import build_execution_plan, write_context_envelope
from .readiness import build_readiness_report
from .run import run_backend_pipeline, validate_backend_json, validate_result_json
from .route import route_envelope
from .sync import list_vendors, plan_sync
from .traceability import (
    build_run_manifest,
    validate_run_manifest,
    write_run_manifest,
)
from .workflow import advance_workflow, check_current_step, complete_artifact, format_status, init_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modeller")
    parser.add_argument("--root", default=".", help="Repository root to inspect.")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Validate repository structure and manifests.")
    doctor.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    doctor.add_argument("--strict", action="store_true", help="Fail readiness checks that are warnings in normal mode.")
    doctor.add_argument("--json", action="store_true", help="Emit a machine-readable doctor result.")

    skills = sub.add_parser("skills", help="List discovered central skills.")
    skills.add_argument("--root", dest="command_root", help="Repository root to inspect.")

    backends = sub.add_parser("backends", help="List or check registered runtime backends.")
    backends.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    backends.add_argument("--check", metavar="BACKEND_ID", help="Check one backend manifest when configured.")

    readiness = sub.add_parser("readiness", help="Plan strict-readiness remediation without applying changes.")
    readiness.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    readiness.add_argument("--json", action="store_true", help="Emit a machine-readable readiness report.")

    memory = sub.add_parser("memory", help="Transport modeller-memory candidates through agent-owned seams.")
    memory.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_transport = memory_sub.add_parser(
        "transport-candidate",
        help="Write a vault-inbox MemoryCandidate as a discovery draft.",
    )
    memory_transport.add_argument("--candidate", required=True, help="MemoryCandidate JSON path.")
    memory_transport.add_argument(
        "--vault-inbox",
        required=True,
        help="Vault inbox/discovery-drafts directory to receive the draft.",
    )

    sync = sub.add_parser("sync", help="Print the git subtree command for a planned vendor sync.")
    sync.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    sync.add_argument("vendor", nargs="?", help="Vendor id. Omit to list vendors.")

    install = sub.add_parser("install", help="Install plugin wiring into a target project.")
    install.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    install.add_argument("target", help="Target project root.")
    install.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    install.add_argument(
        "--include-runtime-assets",
        action="store_true",
        help="Also copy runtime assets under .modeller/runtime in the target.",
    )
    install.add_argument(
        "--install-python-path",
        action="store_true",
        help="Write a user-site .pth file so python -m modeller.cli works without PYTHONPATH.",
    )

    validate = sub.add_parser("validate", help="Validate contract-shaped JSON artifacts.")
    validate.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    validate.add_argument("--backend-json", help="Path to backend.json to validate.")
    validate.add_argument("--expected-backend-id", help="Expected backend id for --backend-json.")
    validate.add_argument("--result-json", help="Path to result.json to validate.")

    route = sub.add_parser("route", help="Route a Testudo/modeller context envelope to a skill and bundle.")
    route.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    route.add_argument("--envelope", required=True, help="Path to a context envelope JSON file.")
    route.add_argument(
        "--run-id",
        help="Deterministic workflow run id override. Takes precedence over the envelope's run_id when set.",
    )

    plan = sub.add_parser("plan", help="Draft a prompt-to-approved-execution plan without executing it.")
    plan.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    plan.add_argument("--prompt", required=True, help="User prompt or work request to draft from.")
    plan.add_argument("--target-repository", help="Target repository/bundle id. Inferred from prompt when unambiguous.")
    plan.add_argument("--requested-capability", help="Requested capability. Inferred from prompt when unambiguous.")
    plan.add_argument("--domain", action="append", default=[], help="Knowledge domain to request. Repeatable.")
    plan.add_argument("--run-id", help="Workflow run id to include in the draft envelope.")
    workflow_policy = plan.add_mutually_exclusive_group()
    workflow_policy.add_argument("--requires-workflow", action="store_true", help="Require an active workflow gate.")
    workflow_policy.add_argument("--no-requires-workflow", action="store_true", help="Do not require a workflow gate.")
    plan.add_argument("--max-risk-level", default="low", choices=["low", "medium", "high"])
    plan.add_argument("--no-consent-required", action="store_true", help="Mark consent as not required for low-risk plans.")
    plan.add_argument("--envelope-output", help="Write the drafted context envelope to this path.")
    plan.add_argument("--json", action="store_true", help="Emit the full machine-readable plan.")

    run = sub.add_parser("run", help="Run a declared backend pipeline through backend.json.runner.command.")
    run.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    run.add_argument("backend_id", help="Registered backend id.")
    run.add_argument("pipeline_id", help="Pipeline id declared by backend.json.")
    run.add_argument("--config", required=True, help="Pipeline config path.")
    run.add_argument("--run-dir", required=True, help="Run output directory.")
    run.add_argument("--backend-root", help="Backend root override. Otherwise uses backends.local.toml.")
    run.add_argument("--timeout-s", type=int, default=3600, help="Backend subprocess timeout in seconds.")

    workflow = sub.add_parser("workflow", help="Manage deterministic artifact-gated workflows.")
    workflow.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_init = workflow_sub.add_parser("init", help="Initialize a workflow run and draft artifacts.")
    workflow_init.add_argument("--run-id", required=True)
    workflow_status = workflow_sub.add_parser("status", help="Show workflow run status.")
    workflow_status.add_argument("--run-id", required=True)
    workflow_check = workflow_sub.add_parser("check", help="Check current step artifact gate.")
    workflow_check.add_argument("--run-id", required=True)
    workflow_advance = workflow_sub.add_parser("advance", help="Advance to the next step if the current gate passes.")
    workflow_advance.add_argument("--run-id", required=True)
    workflow_complete = workflow_sub.add_parser("complete-artifact", help="Mark an artifact complete after writing evidence.")
    workflow_complete.add_argument("--run-id", required=True)
    workflow_complete.add_argument("--artifact", required=True)
    workflow_complete.add_argument("--updated-by", required=True)
    workflow_complete.add_argument("--evidence", required=True)
    workflow_complete.add_argument("--output", required=True)
    workflow_complete.add_argument("--purpose", help="Artifact purpose. Defaults to a step-oriented sentence.")
    workflow_complete.add_argument("--verification", help="Verification evidence for the completed artifact.")
    workflow_manifest = workflow_sub.add_parser("manifest", help="Emit a RunManifest for a workflow run.")
    workflow_manifest.add_argument("--run-id", required=True)
    workflow_manifest.add_argument("--envelope", help="Optional context envelope JSON to include as a ContextReceipt.")
    workflow_manifest.add_argument("--output", help="Optional manifest output path. Prints to stdout when omitted.")
    workflow_close = workflow_sub.add_parser("close", help="Check the deterministic close gate and write a RunManifest.")
    workflow_close.add_argument("--run-id", required=True)
    workflow_close.add_argument("--envelope", help="Optional context envelope JSON to include as a ContextReceipt.")
    workflow_close.add_argument("--manifest-output", help="Manifest output path. Defaults to .modeller/runs/<run-id>/run-manifest.json.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.command_root or args.root).resolve()
    result = run_doctor(root, strict=getattr(args, "strict", False))

    if args.command == "doctor":
        print(json.dumps(result.to_dict(), indent=2) if args.json else result.format())
        return 0 if result.ok else 1
    if args.command == "skills":
        for skill in result.skills:
            print(skill)
        return 0 if result.ok else 1
    if args.command == "backends":
        if args.check:
            check = check_backend(root, args.check)
            print(format_backend_check(check))
            return 0 if check.ok else 1
        for backend in result.backends:
            print(backend)
        return 0 if result.ok else 1
    if args.command == "readiness":
        report = build_readiness_report(root)
        print(report.format_json() if args.json else report.format())
        return 0 if report.ok else 1
    if args.command == "memory":
        if args.memory_command == "transport-candidate":
            result = transport_memory_candidate(Path(args.candidate), Path(args.vault_inbox))
            print(result.format())
            return 0 if result.ok else 1
    if args.command == "sync":
        if not args.vendor:
            for vendor in list_vendors(root):
                print(vendor)
            return 0
        print(plan_sync(root, args.vendor).format())
        return 0
    if args.command == "install":
        print(
            install_plugin(
                root,
                Path(args.target),
                dry_run=not args.apply,
                include_runtime_assets=args.include_runtime_assets,
                install_python_path=args.install_python_path,
            ).format()
        )
        return 0
    if args.command == "validate":
        exit_code = 0
        if args.backend_json:
            check = validate_backend_json(Path(args.backend_json), expected_id=args.expected_backend_id, root=root)
            print(format_backend_check(check))
            exit_code = 0 if check.ok else 1
        if args.result_json:
            check = validate_result_json(Path(args.result_json), root=root)
            print(check.format())
            exit_code = 0 if check.ok and exit_code == 0 else 1
        if not args.backend_json and not args.result_json:
            print("nothing to validate; pass --backend-json or --result-json")
            return 1
        return exit_code
    if args.command == "route":
        decision = route_envelope(root, Path(args.envelope), run_id=args.run_id)
        print(decision.format())
        return 0 if decision.ok else 1
    if args.command == "plan":
        requires_workflow = None
        if args.requires_workflow:
            requires_workflow = True
        elif args.no_requires_workflow:
            requires_workflow = False
        envelope_output = Path(args.envelope_output) if args.envelope_output else None
        plan = build_execution_plan(
            root=root,
            prompt=args.prompt,
            target_repository=args.target_repository,
            requested_capability=args.requested_capability,
            domains=args.domain,
            run_id=args.run_id,
            requires_workflow=requires_workflow,
            consent_required=not args.no_consent_required,
            max_risk_level=args.max_risk_level,
            envelope_output=envelope_output,
        )
        if envelope_output is not None:
            write_context_envelope(envelope_output, plan.context_envelope)
        print(json.dumps(plan.to_dict(), indent=2) if args.json else plan.format())
        return 0 if plan.ok else 1
    if args.command == "run":
        result = run_backend_pipeline(
            root=root,
            backend_id=args.backend_id,
            pipeline_id=args.pipeline_id,
            config=Path(args.config),
            run_dir=Path(args.run_dir),
            backend_root=Path(args.backend_root) if args.backend_root else None,
            timeout_s=args.timeout_s,
        )
        print(result.format())
        return 0 if result.ok else 1
    if args.command == "workflow":
        if args.workflow_command == "init":
            state = init_workflow(root, args.run_id)
            print(json.dumps(state, indent=2))
            return 0
        if args.workflow_command == "status":
            print(format_status(root, args.run_id))
            return 0
        if args.workflow_command == "check":
            gate = check_current_step(root, args.run_id)
            print(gate.format())
            return 0 if gate.ok else 1
        if args.workflow_command == "advance":
            gate = advance_workflow(root, args.run_id)
            print(gate.format())
            return 0 if gate.ok else 1
        if args.workflow_command == "complete-artifact":
            path = complete_artifact(
                root=root,
                run_id=args.run_id,
                artifact=args.artifact,
                updated_by=args.updated_by,
                evidence=args.evidence,
                output=args.output,
                purpose=args.purpose,
                verification=args.verification,
            )
            print(path)
            return 0
        if args.workflow_command == "manifest":
            manifest = build_run_manifest(
                root=root,
                run_id=args.run_id,
                envelope_path=Path(args.envelope) if args.envelope else None,
            )
            if args.output:
                path = write_run_manifest(
                    root=root,
                    run_id=args.run_id,
                    envelope_path=Path(args.envelope) if args.envelope else None,
                    output_path=Path(args.output),
                )
                print(path)
            else:
                print(json.dumps(manifest, indent=2))
            return 0
        if args.workflow_command == "close":
            path = write_run_manifest(
                root=root,
                run_id=args.run_id,
                envelope_path=Path(args.envelope) if args.envelope else None,
                output_path=Path(args.manifest_output) if args.manifest_output else None,
            )
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest_check = validate_run_manifest(manifest)
            gate = manifest["gates"]["close"]
            ok = gate["ok"] and manifest_check.ok
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "manifest": str(path),
                        "manifest_check": {
                            "ok": manifest_check.ok,
                            "errors": manifest_check.errors,
                            "warnings": manifest_check.warnings,
                        },
                        "close_gate": gate,
                    },
                    indent=2,
                )
            )
            return 0 if ok else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
