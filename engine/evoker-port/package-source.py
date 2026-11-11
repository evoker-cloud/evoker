#!/usr/bin/env python3
"""Package only the reviewed ARTEX source and build inputs, never Evoker's repo."""
import gzip
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent


def main():
    if len(sys.argv) != 4:
        raise SystemExit('package-source.py PREPARED_SOURCE IMAGE_MANIFEST OUTPUT_TAR_GZ')
    source, image_path, output = map(pathlib.Path, sys.argv[1:])
    manifest = json.loads((ROOT / 'source.json').read_text())
    image = json.loads(image_path.read_text())
    if image['inputs']['source'] != manifest:
        raise ValueError('Image source does not match this port')
    for name, digest in manifest['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Source artifact changed: ' + name)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args])
    if git('rev-parse', 'HEAD').decode().strip() != manifest['revision']:
        raise ValueError('Unexpected source revision')
    if git('diff', '--binary') != (ROOT / 'patches/hosted.patch').read_bytes():
        raise ValueError('Prepared tracked source differs from reviewed patch')
    files = {}
    def include(name, path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Only regular source files are allowed: ' + str(path))
        files['artex-evoker/' + name] = path.read_bytes()
    for name in git('ls-files', '-z').decode().split('\0'):
        if name:
            include(name, source / name)
    for path in (ROOT / 'overlay').rglob('*'):
        if path.is_file():
            relative = path.relative_to(ROOT / 'overlay')
            if (source / relative).read_bytes() != path.read_bytes():
                raise ValueError('Prepared overlay differs: ' + str(relative))
            include(str(relative), path)
    for path in (source / 'evoker-norma').rglob('*'):
        if path.is_file():
            include(str(path.relative_to(source)), path)
    # Explicit allowlist: runtime code, patches, notices, manifest and recipes.
    for name in [*manifest['files'], 'source.json', 'README.md', 'package-source.py']:
        include('evoker-port/' + name, ROOT / name)
    files['artex-evoker/evoker-port/runtime-image.json'] = image_path.read_bytes()
    instructions = '''# Modified ARTEX source for Evoker

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
The runtime uses the pinned PostgreSQL base in evoker-port/build-runtime.py.
Install the exact Modal SDK version recorded in runtime-image.json, then run:

    python evoker-port/build-runtime.py ./evoker-artex ./runtime-image.json

Building the container through Modal can incur provider charges. No model
weights or GPU are included. The supervisor receives a bounded plan, starts
a private PostgreSQL socket and waits for explicit activation. Its mailbox
protocol is implemented in evoker-port/runtime. The Evoker application is an
independent service communicating through this protocol; the sandbox contains
only this harness, PostgreSQL and the runtime supervisor.
'''
    if image['image'].startswith('localhost/appset/evoker-artex@sha256:'):
        instructions = instructions[:instructions.index('The runtime uses the pinned PostgreSQL base')] + '''The runtime uses Appset's gVisor Jobs. Its pinned PostgreSQL base, standalone
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
'''
    files['artex-evoker/BUILD-EVOKER.md'] = instructions.encode()
    file_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    files['artex-evoker/SOURCE-FILES.json'] = (json.dumps(file_hashes, indent=2)+'\n').encode()
    # Deterministic metadata allows the source offer to be fingerprinted.
    with output.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as tar:
        for name, data in sorted(files.items()):
            item = tarfile.TarInfo(name);item.size = len(data);item.mode = 0o644
            tar.addfile(item, io.BytesIO(data))
    print(json.dumps({'path':str(output),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'files':len(files),'runtimeImage':image['image']}))


if __name__ == '__main__':
    main()
