# CLI Seam — Normative Specification

**Contract version:** 1.2  
**Status:** normative

A conforming backend MUST expose exactly two subcommands, invocable as a subprocess on whatever interpreter the backend requires.

## Commands

### `describe`

    <backend-cmd> describe [--json]

- MUST exit 0.
- MUST emit valid JSON on stdout.
- The JSON MUST be the backend's `backend.json` content (same fields, same values).
- The `--json` flag is optional to accept; the command always emits JSON regardless.

### `run`

    <backend-cmd> run <pipeline_id> --config <cfg.yml> --run-dir <dir>

- MUST exit 0 if and only if `result.json` status is `"success"`.
- MUST exit non-zero for `"failed"` or `"partial"` status, and on any unhandled exception.
- MUST write `result.json` to `<run-dir>/result.json` in **every** outcome — including crash-adjacent failure. Writing `result.json` is the runner's last act before exit.
- The **final non-empty stdout line MUST be the absolute path to `result.json`**. This is the entire machine-readable stdout contract — everything else on stdout/stderr is human-readable logs.

## Interpreter note

`<backend-cmd>` is entirely the backend's concern. Examples:
- `python runner/minirunner.py` (system Python, template)
- `python -m aimsun_psp.cli` (Aimsun-embedded Python, aimsun-psp)

`modeller-agents` invokes `<backend-cmd>` as a subprocess, reads the last stdout line, and re-validates `result.json` against the vendored schema. It does not inspect the interpreter.

## What is out of contract

How a backend dispatches internally — presenter, work_unit, aconsole, direct function call — is explicitly NOT part of this contract. The seam is the subprocess boundary: stdin/stdout/exit code and the `result.json` file.

This includes *whether* a model-bound backend has a fixed model-path input at all: some do (e.g. a
backend that always opens a named `.ang`), some don't (e.g. a backend whose primary mode operates on
an already-open/injected model and has no model-path config field). Both are conforming; neither is
assumed by this document. See `docs/BACKEND_ARCHETYPES.md` (non-normative) for a survey of observed
backend shapes and how each maps onto this seam.
