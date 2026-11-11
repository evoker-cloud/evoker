# ARTEX hosted port

This directory contains source patches and overlays for the revision pinned in
`source.json`. It is part of Evoker's Security Testing implementation. The
customer feature remains disabled until the release gates in
`docs/security-testing-implementation.md` pass.

## Build

From the Evoker repository root, run:

```sh
node integrations/artex/prepare.mjs /tmp/evoker-artex-build
```

The destination must not exist. The script verifies the local artifact hashes,
checks out the exact upstream revision, copies Norma into a private directory,
applies both patches, and builds `cmd/evoker`. It does not execute the harness.
Do not use the original `cmd/artex` application for hosted assessments.

`cmd/evoker` accepts a plan JSON path and private data directory. It initializes
the per-run database and emits `ready`. The trusted runtime sends `activate` on
standard input only after Evoker commits run activation. Termination signals
and the plan deadline stop the harness. Standard output contains normalized
events; raw agent traces remain outside the customer event stream.

The trusted provisioner must supply an isolated database, an unprivileged OS
sandbox, resource limits, an independent deadline watchdog, and network rules
that permit only the assessment broker and its database. Environment variables
are `EVOKER_HOSTED=true`, `EVOKER_MODEL_BASE_URL`, `EVOKER_RUN_CREDENTIAL`, and
`ARTEX_PG_DSN`. Never supply a customer API key, Modal credentials, Cloudflare
credentials, or access to Evoker's application database.

The first profile retains ARTEX's goal, planner, worker, graph and reporter
logic, but exposes only graph operations and fixed read-only inspection tools.
Shell commands, filesystem tools, arbitrary HTTP, MCP discovery, automatic
network enrichment, the original web frontend, and admin endpoints are not
available through this entrypoint. Application tool filtering does not replace
OS and network isolation.

## Updates

1. Review the candidate upstream revision and its provenance.
2. Rebase the patches in a disposable source checkout; preserve the upstream
   agent orchestration rather than creating a second implementation.
3. Review changed tool registrations, model transports, database migrations,
   startup hooks and dependencies.
4. Regenerate `patches/hosted.patch` from the pinned revision, copy reviewed
   overlay changes, and update SHA-256 values in `source.json`.
5. Build from a new directory and run the hosted boundary checks in an OS
   sandbox. Recheck dependency advisories against the resolved module graph
   and actual compiler version.
6. Run scope, cancellation, lease, billing and controlled real-model tests.
   A source, model, provider, price or runtime-image change requires renewed
   qualification before admission.

The upstream repository is a reviewed source candidate; the original repository
was unavailable during research. Provenance remains a release gate. ARTEX is
AGPL-3.0-only; Norma is Apache-2.0. Retain the included license notices and offer
the complete corresponding source of the modified running ARTEX version to
network users before enabling customer access. A patch directory alone is not
the complete source offer.

## Current isolated runtime

ARTEX CPU execution uses Appset's existing gVisor runtime. Modal supplies GPU
inference only. Each assessment gets a separate Kubernetes Job in
`evoker-security`: one CPU, 2 GiB RAM, no network, no credentials, no retries,
and at most 15 minutes. Admission policies enforce the pinned private image,
read-only root, non-root identity, capability restrictions and scratch volume.
The supervisor starts a private PostgreSQL Unix socket and relays fixed
model/inspection operations through a loopback mailbox. The trusted controller
uses a short-lived Kubernetes service-account token for the exec channel;
workers never receive it. The earlier Modal CPU adapter is retained solely for
explicit rollback and historical qualification, never automatic fallback.

`appset-image.json` records the exact image and source inputs; the private image
is preloaded on Appset, not pushed to a public registry. Build its layer with:

```sh
python3 integrations/artex/package-appset.py /path/to/linux-binary /path/to/python-install /tmp/artex-layer.tgz
```

Append this layer to the pinned PostgreSQL base with `crane mutate --output`,
using `/usr/local/bin/python3 -I /opt/evoker/supervisor.py` as entrypoint, user
`1000:1000` and working directory `/work`. Verify the archive checksum and the
imported config/layer digests. K3s converts archive manifest media types on
import, so pin the verified imported manifest digest. Never trust a mutable tag.
See `docs/artex-appset-migration-2026-11-10.md` for qualification and rollback.

Build the corresponding-source archive with:

```sh
python3 integrations/artex/package-source.py /tmp/evoker-artex-build /tmp/evoker-artex-runtime-image.json /tmp/evoker-artex-source.tar.gz
```

Use the source directory and image manifest from the exact reviewed build.
The packager rejects changed revisions, patches, overlays and artifact hashes.
Publish the resulting archive and a visible source link before customer access;
generating an archive locally does not fulfill that publication requirement.
