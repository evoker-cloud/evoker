#!/usr/bin/env python3
"""Verify the exact ARTEX source snapshot without executing it."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1] / "engine"
manifest = json.loads((root / "SOURCE-FILES.json").read_text())
expected = {"SOURCE-FILES.json"}
for name, digest in manifest.items():
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "artex-evoker":
        raise SystemExit("Invalid source path: " + name)
    relative = Path(*relative.parts[1:])
    target = root / relative
    if target.is_symlink() or not target.is_file():
        raise SystemExit("Missing or unsafe source file: " + str(relative))
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise SystemExit("Source checksum differs: " + str(relative))
    expected.add(str(relative))
actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
if actual != expected:
    raise SystemExit("Unmanifested or missing files: " + repr(sorted(actual ^ expected)))
print(f"Verified {len(manifest)} source files.")
