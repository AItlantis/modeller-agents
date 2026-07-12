# Pipeline Smoke Reference Pack

Smoke invocation uses the CLI seam (describe + run subcommands) via the declared runner.command. All validation is against the resolved modeller-pipelines vendor schemas. If the smoke pipeline requires backend tooling, use a tool-free seam smoke pipeline instead. Load `reference-packs/modeller-pipelines.toml` for the CLI seam, result schema path, and artifact-path invariant.
