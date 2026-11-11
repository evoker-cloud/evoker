# SPDX-License-Identifier: AGPL-3.0-only
"""Build the reviewed CPU-only ARTEX runtime. Never starts a sandbox or GPU.

Usage: python build-runtime.py <linux-binary> <output-manifest>
Credentials come from the calling process environment, never the image.
"""
import hashlib
import json
import pathlib
import sys
import modal

ROOT = pathlib.Path(__file__).resolve().parent
BASE = 'docker.io/library/postgres@sha256:ff87138949ad9a46f32ff23bd6852b52ce024a13dffe9b4087be98292cdd3b4f'


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    binary, output = map(pathlib.Path, sys.argv[1:])
    if binary.read_bytes()[:4] != b'\x7fELF':
        raise ValueError('Expected the Linux binary from the pinned source build')
    source = json.loads((ROOT / 'source.json').read_text())
    for name, digest in source['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Source artifact changed: ' + name)
    inputs = dict(source=source, base=BASE, binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  builderSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), modalVersion=modal.__version__)
    source_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    # Upload only the reviewed harness binary and two mailbox scripts. No repo
    # directory, configuration files, local secrets or customer data are sent.
    image = (modal.Image.from_registry(BASE, add_python='3.13')
             .entrypoint([])
             .run_commands('useradd --uid 1000 --create-home --shell /usr/sbin/nologin evoker',
                           'mkdir -p /work /opt/evoker && chown 1000:1000 /work && chmod 700 /work')
             .add_local_file(binary, '/opt/evoker/evoker-artex', copy=True)
             .add_local_file(ROOT / 'runtime/supervisor.py', '/opt/evoker/supervisor.py', copy=True)
             .add_local_file(ROOT / 'runtime/mailbox.py', '/opt/evoker/mailbox.py', copy=True)
             .run_commands('chmod 555 /opt/evoker/evoker-artex && chmod 444 /opt/evoker/*.py')
             .dockerfile_commands('WORKDIR /work'))
    app = modal.App.lookup('evoker-security', create_if_missing=True)
    with modal.enable_output():
        image.build(app)
    output.write_text(json.dumps(dict(image=image.object_id, sourceHash=source_hash, inputs=inputs), indent=2)+'\n')
    print(json.dumps(dict(image=image.object_id, sourceHash=source_hash)))


if __name__ == '__main__':
    main()
