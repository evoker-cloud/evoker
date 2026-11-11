# Modified ARTEX source for Evoker

ARTEX is licensed under AGPL-3.0-only. Norma is licensed under Apache-2.0.
Upstream notices and license files are retained. Appset, Inc. modified the
hosted entrypoint, tool boundary, model transport, context handling, dependency
versions, event/finding export and isolated runtime in November 2026.

This archive contains the full pinned ARTEX tree, applied patches, modified
Norma copy, and the runtime/build recipes for the image in runtime-image.json.
It contains no Evoker customer data, credentials, application code or weights.

Build from the archive root with Go 1.26.10:

    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -p 2 -trimpath -ldflags='-s -w' -o evoker-artex ./cmd/evoker

Go downloads dependencies listed in go.mod and verifies go.sum. The modified
Norma dependency is included in evoker-norma. The original web application is
included for source completeness but is neither built nor used by this binary.
The runtime uses Appset's gVisor Jobs. Its pinned PostgreSQL base, standalone
Python version and source inputs are recorded in evoker-port/runtime-image.json.
Install that Linux amd64 Python build and create the additional image layer:

    python3 evoker-port/package-appset.py ./evoker-artex /path/to/python-install ./artex-layer.tgz

Append the layer with crane v0.22.1 `mutate --output` using the pinned base,
entrypoint `/usr/local/bin/python3,-I,/opt/evoker/supervisor.py`, user 1000:1000
and working directory /work. Do not push to a public registry. Verify archive,
config and layer checksums on import and pin the imported manifest digest.
The image contains no GPU or weights. Its supervisor receives a bounded plan,
starts a private PostgreSQL Unix socket and waits for explicit activation.
The mailbox protocol is in evoker-port/runtime. The Evoker controller is an
independent service; the sandbox contains only ARTEX, PostgreSQL and the runtime
supervisor. The exact deployment must independently block network access, mount
no credentials, enforce CPU/RAM/scratch limits, and stop on deadline.
