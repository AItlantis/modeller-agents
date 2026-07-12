# Pipeline Fix Reference Pack

Contract-class failures (result.json not written, absolute artifact paths, wrong exit code, schema violations) are diagnosed and fixed centrally. Domain-class failures (backend logic, environment, interpreter crashes) are routed to the backend repo's local agents — this skill does not cross that boundary. Load `reference-packs/modeller-pipelines.toml` for the CLI seam and result status values. Load the target backend's reference pack for domain-class symptoms.
