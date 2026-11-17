# SPDX-License-Identifier: AGPL-3.0-only
"""Create an allowlisted OCI layer; never includes the application or credentials.

Usage: package-appset.py linux-artifact python-install layer.tgz
Append with the digest-pinned postgres base using crane mutate --output.
"""
import hashlib
import copy
import io
import json
import pathlib
import sys
import tarfile

root = pathlib.Path(__file__).resolve().parent
binary, python, output = map(pathlib.Path, sys.argv[1:])
assert binary.read_bytes()[:4] == b'\x7fELF'
source = json.loads((root / 'source.json').read_text())
for name, digest in source['files'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name

def metadata(info):
    info.uid = info.gid = 0
    info.uname = info.gname = 'root'
    info.mtime = 0
    info.mode &= ~0o022
    return info

with tarfile.open(output, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
    if python.is_file():
        # Preserve Linux case-sensitive names and symlinks when packaging on
        # macOS. Extracting terminfo to a case-insensitive disk corrupts links.
        with tarfile.open(python, 'r:*') as runtime:
            for original in runtime:
                path = pathlib.PurePosixPath(original.name)
                if path.is_absolute() or '..' in path.parts or path.parts[0] != 'python':
                    raise ValueError('Unexpected Python archive path')
                item = copy.copy(original)
                item.name = str(pathlib.PurePosixPath('opt/python') / path.relative_to('python'))
                if item.islnk():
                    target = pathlib.PurePosixPath(item.linkname)
                    if target.is_absolute() or '..' in target.parts or target.parts[0] != 'python':
                        raise ValueError('Unexpected Python hard link')
                    item.linkname = str(pathlib.PurePosixPath('opt/python') / target.relative_to('python'))
                if not (item.isfile() or item.isdir() or item.issym() or item.islnk()):
                    raise ValueError('Unexpected Python archive entry')
                archive.addfile(metadata(item), runtime.extractfile(original) if item.isfile() else None)
    else:
        archive.add(python, arcname='opt/python', filter=metadata)
    archive.add(binary, arcname='opt/evoker/evoker-artex', filter=metadata)
    for name in ('supervisor.py', 'mailbox.py'):
        archive.add(root / 'runtime' / name, arcname='opt/evoker/' + name, filter=metadata)
    for name in ('LICENSE-ARTEX', 'LICENSE-NORMA'):
        archive.add(root / name, arcname='opt/evoker/' + name, filter=metadata)
    files = {
        'etc/passwd': 'root:x:0:0:root:/root:/bin/sh\npostgres:x:999:999:PostgreSQL:/var/lib/postgresql:/bin/sh\nevoker:x:1000:1000:Evoker:/work:/usr/sbin/nologin\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n',
        'etc/group': 'root:x:0:\npostgres:x:999:\nevoker:x:1000:\nnogroup:x:65534:\n',
    }
    for name, content in files.items():
        data = content.encode()
        info = tarfile.TarInfo(name)
        info.size, info.mode = len(data), 0o444
        archive.addfile(metadata(info), io.BytesIO(data))
    link = tarfile.TarInfo('usr/local/bin/python3')
    link.type, link.linkname, link.mode = tarfile.SYMTYPE, '/opt/python/bin/python3.13', 0o777
    archive.addfile(metadata(link))
    directory = tarfile.TarInfo('work')
    directory.type, directory.uid, directory.gid, directory.mode = tarfile.DIRTYPE, 1000, 1000, 0o700
    archive.addfile(directory)
print(json.dumps({'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
                  'layerSha256':hashlib.sha256(output.read_bytes()).hexdigest()}))
