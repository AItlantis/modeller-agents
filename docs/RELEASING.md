# Releasing the modeller-agents wheel

The `v*` release workflow builds from the event's `github.sha`, checks that the
tag matches `pyproject.toml`, runs tests, and builds exactly one wheel. It signs
that wheel with GitHub Artifact Attestations using the default SLSA provenance
predicate. The attested subject is the wheel file itself, so its SHA-256 binds
the statement to the exact bytes later attached to the GitHub Release.

The workflow transfers the wheel, `SHA256SUMS`, and the Sigstore bundle through
one run-and-attempt-scoped Actions artifact. Before it creates a draft release,
it checks the wheel checksum, verifies the bundle signature and signer with
`gh attestation verify`, then checks that the signed statement names the wheel,
the source commit and tag, `.github/workflows/release.yml`, and this exact
Actions run and attempt. If any check fails, the workflow does not create the
draft release.

Each release attaches:

- the `.whl` package;
- `SHA256SUMS` for the package;
- `<wheel filename>.sigstore.json`, the portable Sigstore bundle containing
  the signed SLSA statement.

Consumers should verify the bundle against the downloaded wheel with
`gh attestation verify <wheel> --bundle <wheel>.sigstore.json --repo
AItlantis/modeller-agents --signer-workflow
AItlantis/modeller-agents/.github/workflows/release.yml --source-digest
<source commit SHA>`. The release workflow also performs the equivalent check
before publishing and validates the SLSA `invocationId` against
`<run ID>/<run attempt>`.

Artifact Attestations require `id-token: write`, `attestations: write`, and
`artifact-metadata: write` on the wheel-build job. The release job receives
only `contents: write` so it can create the draft release; it does not mint an
attestation.
