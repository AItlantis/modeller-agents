from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .backend import check_backend, format_backend_check, list_backend_ids
from .doctor import run_doctor
from .install import install_plugin
from .memory_transport import transport_memory_candidate
from .orchestrator import build_chat_handoff_prompt, format_orchestration, orchestrate_prompt
from .planning import build_execution_plan, write_context_envelope
from .readiness import build_readiness_report
from .runtime import discover_installed_target_roots, has_runtime_bundle, runtime_path
from .run import run_backend_pipeline, validate_backend_json, validate_result_json
from .subagents import (
    build_subagent_work_order,
    ingest_subagent_lane_receipt_into_v_cycle_artifacts,
    load_json,
    persist_subagent_lane_receipt,
    write_json,
)
from .route import route_envelope
from .sync import list_vendors, plan_sync
from .traceability import (
    build_run_manifest,
    validate_run_manifest,
    write_run_manifest,
)
from .vcycle import (
    advance_v_cycle,
    apply_human_review_provider,
    check_v_cycle_current_stage,
    format_v_cycle_status,
    init_v_cycle_run,
    is_v_cycle_run,
    list_v_cycle_workflows,
    recommend_v_cycle_stage,
    review_v_cycle_stage,
    trace_check_v_cycle,
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
    plan.add_argument(
        "--gate-policy",
        choices=["bind-run", "check-current-gate"],
        help="Workflow gate policy. bind-run verifies run/stage binding; check-current-gate requires the current exit gate.",
    )
    plan.add_argument("--no-consent-required", action="store_true", help="Mark consent as not required for low-risk plans.")
    plan.add_argument("--envelope-output", help="Write the drafted context envelope to this path.")
    plan.add_argument("--json", action="store_true", help="Emit the full machine-readable plan.")

    orchestrate = sub.add_parser("orchestrate", help="Plan, bind, and start a gate-bound orchestration loop.")
    orchestrate.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    orchestrate.add_argument("--prompt", required=True, help="Natural-language user request.")
    orchestrate.add_argument("--target-repository", help="Target repository/bundle id. Inferred when unambiguous.")
    orchestrate.add_argument("--run-id", help="Workflow run id. Generated deterministically when omitted.")
    orchestrate.add_argument("--target-path", help="Repository-relative path to bind into the work order.")
    orchestrate.add_argument("--agent-id", default="subagent", help="Subagent id to bind in the generated work order.")
    orchestrate.add_argument("--mode", default="stage", choices=["stage", "paired-review"], help="V-cycle invocation mode when a run is initialized.")
    orchestrate.add_argument("--required-test", action="append", default=[], help="Required test command/name for the work order.")
    orchestrate.add_argument("--envelope-output", help="Context envelope path. Defaults under .modeller/runs/<run-id>.")
    orchestrate.add_argument("--work-order-output", help="Work-order path. Defaults under .modeller/runs/<run-id>/work-orders/.")
    orchestrate.add_argument(
        "--chat-output",
        help="Write a Codex/Claude starter prompt that loads the generated orchestration context.",
    )
    orchestrate.add_argument(
        "--launch-chat",
        choices=["codex", "claude"],
        help="Launch an interactive chat client with the generated handoff prompt. Writes --chat-output or a default handoff file.",
    )
    orchestrate.add_argument("--json", action="store_true", help="Emit machine-readable orchestration status.")

    run = sub.add_parser("run", help="Run a declared backend pipeline through backend.json.runner.command.")
    run.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    run.add_argument("backend_id", help="Registered backend id.")
    run.add_argument("pipeline_id", help="Pipeline id declared by backend.json.")
    run.add_argument("--config", required=True, help="Pipeline config path.")
    run.add_argument("--run-dir", required=True, help="Run output directory.")
    run.add_argument("--backend-root", help="Backend root override. Otherwise uses backends.local.toml.")
    run.add_argument("--timeout-s", type=int, default=3600, help="Backend subprocess timeout in seconds.")

    workflows = sub.add_parser("workflows", help="List available workflow families and deterministic workflows.")
    workflows.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    workflows_sub = workflows.add_subparsers(dest="workflows_command", required=True)
    workflows_list = workflows_sub.add_parser("list", help="List workflow families.")
    workflows_list.add_argument("--json", action="store_true", help="Emit machine-readable workflow catalog.")

    workflow = sub.add_parser("workflow", help="Manage deterministic artifact-gated workflows.")
    workflow.add_argument("--root", dest="command_root", help="Repository root to inspect.")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_init = workflow_sub.add_parser("init", help="Initialize a workflow run and draft artifacts.")
    workflow_init.add_argument("--run-id", required=True)
    workflow_init.add_argument("--family", default="deterministic", choices=["deterministic", "v-cycle"])
    workflow_init.add_argument("--mode", default="stage", choices=["full", "stage", "paired-review"])
    workflow_init.add_argument("--stage", help="V-cycle stage id for stage or paired-review mode.")
    workflow_recommend = workflow_sub.add_parser("recommend", help="Recommend a V-cycle stage from a prompt.")
    workflow_recommend.add_argument("--prompt", required=True)
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
    workflow_trace = workflow_sub.add_parser("trace-check", help="Check V-cycle traceability artifact.")
    workflow_trace.add_argument("--run-id", required=True)
    workflow_review = workflow_sub.add_parser("review", help="Apply a human review receipt to a V-cycle stage.")
    workflow_review.add_argument("--run-id", required=True)
    workflow_review.add_argument("--receipt", required=True)
    workflow_request_review = workflow_sub.add_parser("request-review", help="Apply a human review through a controlled provider.")
    workflow_request_review.add_argument("--run-id", required=True)
    workflow_request_review.add_argument("--provider", required=True, choices=["receipt-file", "test-fixture"])
    workflow_request_review.add_argument("--receipt", help="Receipt JSON path for receipt-file provider.")
    workflow_request_review.add_argument("--fixture-metadata", help="Fixture metadata JSON for test-fixture provider.")
    workflow_request_review.add_argument("--stage-id")
    workflow_request_review.add_argument("--reviewer-id")
    workflow_request_review.add_argument("--reviewer-role")
    workflow_request_review.add_argument(
        "--decision",
        default="approved",
        choices=["approved", "approved-with-reservations", "changes-requested", "rejected"],
    )
    workflow_request_review.add_argument(
        "--review-type",
        default="approval",
        choices=["expert-review", "approval", "sign-off", "action-approval"],
    )
    workflow_request_review.add_argument("--allow-test-fixture", action="store_true")
    workflow_human_review = workflow_sub.add_parser("human-review", help=argparse.SUPPRESS)
    workflow_human_review.add_argument("--run-id", required=True)
    workflow_human_review.add_argument("--provider", required=True, choices=["receipt-file", "test-fixture"])
    workflow_human_review.add_argument("--receipt")
    workflow_human_review.add_argument("--fixture-metadata")
    workflow_human_review.add_argument("--stage-id")
    workflow_human_review.add_argument("--reviewer-id")
    workflow_human_review.add_argument("--reviewer-role")
    workflow_human_review.add_argument("--decision", default="approved", choices=["approved", "approved-with-reservations", "changes-requested", "rejected"])
    workflow_human_review.add_argument("--review-type", default="approval", choices=["expert-review", "approval", "sign-off", "action-approval"])
    workflow_human_review.add_argument("--allow-test-fixture", action="store_true")
    workflow_work_order = workflow_sub.add_parser("work-order", help="Create a gate-bound subagent work order.")
    workflow_work_order.add_argument("--run-id", required=True)
    workflow_work_order.add_argument("--target-repository", required=True)
    workflow_work_order.add_argument("--task", required=True)
    workflow_work_order.add_argument("--agent-id", default="subagent")
    workflow_work_order.add_argument("--stage-id")
    workflow_work_order.add_argument("--target-path")
    workflow_work_order.add_argument("--allowed-path", action="append", default=[])
    workflow_work_order.add_argument("--required-test", action="append", default=[])
    workflow_work_order.add_argument("--output", required=True)
    workflow_lane_receipt = workflow_sub.add_parser("lane-receipt", help="Validate a subagent lane receipt.")
    workflow_lane_receipt.add_argument("--work-order", required=True)
    workflow_lane_receipt.add_argument("--receipt", required=True)
    workflow_ingest_lane = workflow_sub.add_parser(
        "ingest-lane-receipt",
        help="Ingest a persisted subagent lane receipt into active V-cycle artifacts.",
    )
    workflow_ingest_lane.add_argument("--run-id", required=True)
    workflow_ingest_lane.add_argument("--receipt-id", required=True)
    workflow_ingest_lane.add_argument("--stage-id")
    workflow_ingest_lane.add_argument("--artifact", action="append", required=True)
    workflow_ingest_lane.add_argument("--mode", default="append", choices=["append"])
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
    root_resolution = _resolve_target_root_for_command(root, args)
    if root_resolution is not None:
        if not root_resolution["ok"]:
            print(json.dumps(root_resolution, indent=2) if getattr(args, "json", False) else _format_root_resolution(root_resolution))
            return 1
        root = Path(root_resolution["resolved_root"])
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
            gate_policy=args.gate_policy,
            envelope_output=envelope_output,
        )
        if envelope_output is not None:
            write_context_envelope(envelope_output, plan.context_envelope)
        print(json.dumps(plan.to_dict(), indent=2) if args.json else plan.format())
        return 0 if plan.ok else 1
    if args.command == "orchestrate":
        payload = orchestrate_prompt(
            root=root,
            prompt=args.prompt,
            target_repository=args.target_repository,
            run_id=args.run_id,
            target_path=args.target_path,
            agent_id=args.agent_id,
            invocation_mode=args.mode,
            required_tests=args.required_test,
            envelope_output=Path(args.envelope_output) if args.envelope_output else None,
            work_order_output=Path(args.work_order_output) if args.work_order_output else None,
        )
        if payload.get("ok") and (args.chat_output or args.launch_chat):
            chat_path = _default_chat_handoff_path(root, payload, args.chat_output)
            chat_prompt = build_chat_handoff_prompt(root, payload)
            chat_path.parent.mkdir(parents=True, exist_ok=True)
            chat_path.write_text(chat_prompt, encoding="utf-8")
            payload["chat_handoff_path"] = _display_cli_path(root, chat_path)
            payload["chat_cwd"] = str(_chat_cwd(root, payload).resolve())
            if args.launch_chat:
                chat_command = _chat_launch_command(args.launch_chat, chat_path)
                payload["chat_launch_command"] = chat_command
                if args.json:
                    print(json.dumps(payload, indent=2))
                    return 0
                print(format_orchestration(payload))
                print(f"chat_handoff: {payload['chat_handoff_path']}")
                print(f"launching_chat: {subprocess.list2cmdline(chat_command)}")
                return subprocess.run(chat_command, cwd=_chat_cwd(root, payload), check=False).returncode
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_orchestration(payload))
            if payload.get("chat_handoff_path"):
                print(f"chat_handoff: {payload['chat_handoff_path']}")
                launcher = "codex" if _command_available("codex") else "claude"
                print(f"chat_command: {subprocess.list2cmdline(_chat_launch_command(launcher, root / payload['chat_handoff_path']))}")
        return 0 if payload.get("ok") else 1
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
    if args.command == "workflows":
        if args.workflows_command == "list":
            catalog = list_v_cycle_workflows(root)
            if args.json:
                print(json.dumps({"workflows": catalog}, indent=2))
            else:
                for workflow in catalog:
                    print(f"{workflow['workflow_family']}: {workflow['name']}")
                    for stage in workflow["stages"]:
                        print(f"  - {stage['id']} ({stage['branch']}, {stage['vigilance_level']})")
            return 0
    if args.command == "workflow":
        if args.workflow_command == "init":
            if args.family == "v-cycle":
                state = init_v_cycle_run(
                    root,
                    args.run_id,
                    invocation_mode=args.mode,
                    requested_stage=args.stage,
                )
            else:
                state = init_workflow(root, args.run_id)
            print(json.dumps(state, indent=2))
            return 0
        if args.workflow_command == "recommend":
            print(json.dumps(recommend_v_cycle_stage(root, args.prompt), indent=2))
            return 0
        if args.workflow_command == "status":
            print(format_v_cycle_status(root, args.run_id) if is_v_cycle_run(root, args.run_id) else format_status(root, args.run_id))
            return 0
        if args.workflow_command == "check":
            gate = check_v_cycle_current_stage(root, args.run_id) if is_v_cycle_run(root, args.run_id) else check_current_step(root, args.run_id)
            print(gate.format())
            return 0 if gate.ok else 1
        if args.workflow_command == "advance":
            gate = advance_v_cycle(root, args.run_id) if is_v_cycle_run(root, args.run_id) else advance_workflow(root, args.run_id)
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
        if args.workflow_command == "trace-check":
            gate = trace_check_v_cycle(root, args.run_id)
            print(gate.format())
            return 0 if gate.ok else 1
        if args.workflow_command == "review":
            payload = review_v_cycle_stage(root, args.run_id, Path(args.receipt))
            print(json.dumps(payload, indent=2))
            return 0 if payload.get("ok") else 1
        if args.workflow_command in {"request-review", "human-review"}:
            payload = apply_human_review_provider(
                root,
                args.run_id,
                provider=args.provider,
                receipt_path=Path(args.receipt) if args.receipt else None,
                fixture_metadata_path=Path(args.fixture_metadata) if args.fixture_metadata else None,
                reviewer_id=args.reviewer_id,
                reviewer_role=args.reviewer_role,
                decision=args.decision,
                review_type=args.review_type,
                allow_test_fixture=args.allow_test_fixture,
                stage_id=args.stage_id,
            )
            print(json.dumps(payload, indent=2))
            return 0 if payload.get("ok") else 1
        if args.workflow_command == "work-order":
            payload = build_subagent_work_order(
                root=root,
                run_id=args.run_id,
                target_repository=args.target_repository,
                task=args.task,
                agent_id=args.agent_id,
                stage_id=args.stage_id,
                target_path=args.target_path,
                allowed_paths=args.allowed_path,
                required_tests=args.required_test,
            )
            path = write_json(Path(args.output), payload)
            print(json.dumps({"ok": True, "work_order": str(path), "payload": payload}, indent=2))
            return 0
        if args.workflow_command == "lane-receipt":
            payload = persist_subagent_lane_receipt(
                root,
                load_json(Path(args.work_order)),
                load_json(Path(args.receipt)),
            )
            print(json.dumps(payload, indent=2))
            return 0 if payload.get("ok") else 1
        if args.workflow_command == "ingest-lane-receipt":
            payload = ingest_subagent_lane_receipt_into_v_cycle_artifacts(
                root,
                run_id=args.run_id,
                receipt_id=args.receipt_id,
                stage_id=args.stage_id,
                artifacts=args.artifact,
            )
            print(json.dumps(payload, indent=2))
            return 0 if payload.get("ok") else 1
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


def _resolve_target_root_for_command(root: Path, args: argparse.Namespace) -> dict | None:
    if args.command not in {"plan", "orchestrate"}:
        return None
    target_repository = getattr(args, "target_repository", None)
    if not target_repository:
        return None
    target_repository = str(target_repository)
    if has_runtime_bundle(root, target_repository):
        return None
    matches = discover_installed_target_roots(root, target_repository)
    searched_bundle = runtime_path(root, "bundles", f"{target_repository}.bundle.json")
    child_patterns = [str(root / target_repository), str(root / "*" / target_repository)]
    payload = {
        "ok": len(matches) == 1,
        "inspected_root": str(root),
        "target_repository": target_repository,
        "searched_root_bundle": str(searched_bundle),
        "searched_child_patterns": child_patterns,
        "matching_installed_child_candidates": [str(path) for path in matches],
        "resolved_root": str(matches[0]) if len(matches) == 1 else "",
        "errors": [],
    }
    if len(matches) == 1:
        return payload
    if not matches:
        payload["errors"].append(
            f"no bundle found for target repository {target_repository!r} at inspected root or bounded installed child roots"
        )
        payload["advice"] = f"rerun with --root pointing at the installed target repository, for example --root <workspace>\\aimsun\\{target_repository}"
    else:
        payload["errors"].append(f"multiple installed child roots match target repository {target_repository!r}")
        payload["advice"] = "rerun with --root set to one matching installed target repository"
    return payload


def _format_root_resolution(payload: dict) -> str:
    lines = ["target root resolution: BLOCKED"]
    lines.append(f"inspected_root: {payload['inspected_root']}")
    lines.append(f"target_repository: {payload['target_repository']}")
    lines.append(f"searched_root_bundle: {payload['searched_root_bundle']}")
    lines.append("searched_child_patterns:")
    lines.extend(f"  - {pattern}" for pattern in payload["searched_child_patterns"])
    if payload["matching_installed_child_candidates"]:
        lines.append("matching_installed_child_candidates:")
        lines.extend(f"  - {path}" for path in payload["matching_installed_child_candidates"])
    lines.append("errors:")
    lines.extend(f"  - {error}" for error in payload["errors"])
    if payload.get("advice"):
        lines.append(f"advice: {payload['advice']}")
    return "\n".join(lines)


def _default_chat_handoff_path(root: Path, payload: dict, explicit_output: str | None) -> Path:
    if explicit_output:
        path = Path(explicit_output)
        return path if path.is_absolute() else root / path
    run_id = payload.get("run_id")
    if run_id:
        return root / ".modeller" / "runs" / str(run_id) / "chat-handoff.md"
    return root / ".modeller" / "chat-handoffs" / "orchestrate-chat-handoff.md"


def _chat_launch_command(launcher: str, chat_path: Path) -> list[str]:
    prompt = (
        "Use the modeller:orchestrator agent. "
        f"Read this handoff file and continue the workflow from it: {chat_path.resolve()}"
    )
    return [_resolve_chat_launcher(launcher), prompt]


def _resolve_chat_launcher(launcher: str) -> str:
    if launcher == "claude":
        return shutil.which("claude.cmd") or shutil.which("claude") or launcher
    return shutil.which(launcher) or launcher


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


def _display_cli_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _chat_cwd(root: Path, payload: dict) -> Path:
    source_root = payload.get("plan", {}).get("alignment_contract", {}).get("source_root")
    if isinstance(source_root, str) and source_root.strip():
        candidate = Path(source_root)
        if candidate.exists():
            return candidate
    return root


if __name__ == "__main__":
    raise SystemExit(main())
