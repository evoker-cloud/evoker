# Contributing

Use issues for defects and proposed changes. Keep changes focused and include
reproduction steps or tests for behavior changes.

Preserve the ARTEX and Norma attribution and license notices. Contributions to
the engine use its existing license. Do not commit credentials, assessment data,
customer evidence, local configuration, or model weights.

`engine/` currently preserves an exact source snapshot. Update source fingerprints
and the corresponding-source release whenever changing it. Keep the engine's
agent orchestration upstream-compatible; runtime and provider adapters belong at
the boundary. Do not weaken the hosted worker's network or credential controls
when adding self-hosted provider support.

Build and run the boundary tests shown in README.md before submitting changes.
