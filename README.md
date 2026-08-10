# modeller-pipelines

> **Version:** contract-v1.2

## What this is

`modeller-pipelines` is the **versioned contract surface** for the modeller ecosystem. It defines, in
normative prose and machine-readable JSON Schema, what a pipeline backend must expose and what
modeller-agents may expect to consume. It also ships one runnable, copyable template pipeline so new
backend authors have a concrete starting point.

Three things live here:

1. **Versioned contracts** (`contracts/`) — schemas plus normative prose specs covering pipeline
   definition format, step interface, CLI seam, and result envelope. Every other repo in the ecosystem
   pins a `contract_version` string; the schemas here are the ground truth for that version.

2. **A runnable template pipeline** (`template/`) — a self-contained `trip_summary` pipeline you can
   copy and adapt. It is illustrative, not normative; backends MUST conform to `contracts/`, NOT to
   `template/`.

3. **A black-box conformance kit** (`conformance/`) — a test harness that can be pointed at any
   backend's CLI seam and verifies conformance to the current contract version without knowing anything
   about the backend's internals.

## What this is NOT

- **NOT a shared runtime framework.** Nothing in the production ecosystem imports this repository at
  runtime. There are no base classes, no shared runners, no plugin hooks here.
- **NOT a monorepo for backends.** Backend implementations (e.g. `aimsun-psp`) live in their own
  repositories; they reference this repo's schemas via CI fetch or `contract.lock`, not by vendor
  copy.
- **NOT a Testudo concern.** Testudo is downstream of pipeline outputs. The contracts here define
  what a pipeline runner produces, not how Testudo consumes it.

## Topology

```
modeller-pipelines   ← this repo (contract surface + template + conformance kit)
│
├── vendored into → modeller-agents   (git subtree, offline schema access)
│
└── referenced by → aimsun-psp        (runtime backend, CI-fetches schemas,
                                        registered via backend.json + contract.lock)
```

The **one discipline everything flows from**: backends conform to `contracts/`, NOT to `template/`.
If a template pattern and a contract rule conflict, the contract wins.

## Contents

```
contracts/
  VERSION                   Plain text contract version ("1.2")
  PIPELINE_DEFINITION.md    Normative spec: *.pipeline.yml shape
  STEP_INTERFACE.md         Normative spec: step/action run() contract
  CLI_SEAM.md               Normative spec: CLI subcommands and guarantees
  RESULT_CONTRACT.md        Normative spec: result.json semantics
  schemas/
    pipeline.schema.json
    step-result.schema.json
    result.schema.json
    backend.schema.json
    run-config.schema.json

template/                   Copyable trip_summary pipeline (illustrative)
conformance/                Black-box conformance kit

CONTRACT_VERSIONS.md        Version history and support window table
CHANGELOG.md                Human-readable change log
```

## Quick start (new backend)

1. Fetch the schemas for your target `contract_version`:
   ```
   curl -sSL https://raw.githubusercontent.com/AItlantis/modeller-pipelines/contract-v1.2/contracts/schemas/backend.schema.json
   ```
2. Author `backend.json` conforming to `backend.schema.json`.
3. Implement the CLI seam described in `contracts/CLI_SEAM.md`.
4. Implement `run(config, step_params, run_context) -> dict` for each step module per
   `contracts/STEP_INTERFACE.md`.
5. Write a `contract.lock` file pinning `contract_version: "1.2"`.
6. Run the conformance kit against your CLI (see below).

## Quick start (new pipeline repo)

1. Copy `template/` into your repo as a starting point.
2. Edit `*.pipeline.yml` to declare your steps, inputs, and outputs per
   `contracts/PIPELINE_DEFINITION.md`.
3. Validate the yml against `contracts/schemas/pipeline.schema.json`.
4. Register the pipeline in your `backend.json`.

## How to run conformance

```bash
# Self-conformance: run against the template (from repo root)
pytest conformance --backend-root template --backend-cmd "python runner/minirunner.py"

# The kit exits 0 iff all normative checks pass.
```

The conformance kit verifies the CLI seam, result envelope shape, and step-result schema. It does NOT
test business logic inside your steps.
