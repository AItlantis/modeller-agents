# Quality Gates

Work on a pipeline repo follows a gated phase workflow. Each phase requires its exit criterion before the next phase begins.

## Phases

| Phase | Entry | Exit criterion |
|---|---|---|
| **Brief** | User need identified | Problem + goals + non-goals documented |
| **Recon** | Brief accepted | Existing code read; dependencies confirmed; open questions listed |
| **Plan** | Recon complete | Every file to change named; every contract field to add named; conformance test that will verify it named |
| **Execute** | Plan accepted | Code written; unit tests green; step smoke passes |
| **Deploy** | Execute complete | Conformance kit passes (static + runtime); `contract.lock` updated if needed; `backend.json` valid |
| **Document** | Deploy complete | README updated; changelog entry added; limitations documented |

## The gate between Plan and Execute

This gate is the most important. The plan MUST name:
1. Every file to be created or modified.
2. Every new field or schema change, with rationale.
3. The specific conformance test (from `conformance/`) that will verify the change is correct.

A plan that says "implement the step" without naming the file is not a plan — it is a brief. Do not execute against it.

## Anti-patterns

- **Skipping recon** — writing code before reading what already exists. The most common source of duplicated logic.
- **Merging plan + execute** — the plan phase exists to catch design errors before code is written, not as a formality.
- **Undocumented limitations** — a deploy that does not document what it does NOT do is incomplete.
