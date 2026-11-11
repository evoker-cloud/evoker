# Evoker

Evoker is an open-source security assessment engine built on ARTEX.
[Evoker Cloud](https://evoker.cloud) is the hosted SaaS version.

This repository contains the modified engine, its isolated runtime, build inputs,
and source notices. It does not contain the Evoker Cloud web application,
account system, billing service, or deployment credentials.

## Build

Requirements: Go 1.26.10 and Python 3.11 or newer for source verification.

```sh
python3 scripts/verify-source.py
mkdir -p dist
cd engine
go build -p 2 -trimpath -o ../dist/evoker ./cmd/evoker
go test -p 2 ./agent -run TestEvoker -count=1
```

The build downloads the dependencies in `engine/go.mod` and verifies them
against `engine/go.sum`. The modified Norma dependency is included locally.

## Engine interface

The current command is a headless worker entrypoint:

```text
evoker <plan.json> <isolated-data-directory>
```

It needs a per-assessment PostgreSQL database, an isolated runtime, and a trusted
model and inspection broker. It emits JSON events and waits for `activate` on
standard input before starting the assessment. The included supervisor implements
this contract. See [Runtime interface](docs/runtime.md) and the exact
[build recipe](engine/BUILD-EVOKER.md).

The available inspection tools check response headers, TLS configuration, and
public metadata on explicitly authorized hosts. Shell commands, arbitrary HTTP,
filesystem tools, and external MCP tools are disabled in this entrypoint.

## Self-hosted CLI

The next release will add operator-facing `init`, `assess`, and `report` commands
and configuration for OpenAI-compatible model endpoints, including local models.
Those commands are not part of this source release. The current runtime's model
transport expects the Evoker broker protocol; changing a URL alone is insufficient.
Model providers will need reliable tool calling and enough context for the agent
workflow. See [CLI roadmap](docs/cli-roadmap.md).

## Source and attribution

The engine is derived from ARTEX revision
`133f3cf97f2d153227a1a95d3c4b7cd5b72020a6`, retrieved from the
[artex-global mirror](https://github.com/jiwoochris/artex-global).
The upstream tree, notices, applied patches, and modified Norma source are in
`engine/`. This is an independent port and does not imply upstream endorsement.

The engine is AGPL-3.0-only. Norma is Apache-2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE). Source releases identify the exact engine and runtime inputs.

Only assess systems you own or have explicit permission to test. The runtime
requires independent network restrictions, resource limits, and cancellation
controls; a prompt is not an authorization boundary.
