#!/usr/bin/env python3
"""Rewrites the overlay hashes in source.json from the files under overlay/.

Bazel checks every overlay file against the hash recorded in source.json, so
this runs after any edit to the overlay. The BCR repo's own tool
(bazel run //tools:update_integrity) does the same when the module moves there.

    tools/update_integrity.py            # sdl3@3.4.16
    tools/update_integrity.py 3.4.18
"""

import base64
import hashlib
import json
import pathlib
import sys

version = sys.argv[1] if len(sys.argv) > 1 else "3.4.16"
version_dir = pathlib.Path(__file__).resolve().parent.parent / "registry" / "modules" / "sdl3" / version
overlay = version_dir / "overlay"
source_json = version_dir / "source.json"

source = json.loads(source_json.read_text())
hashes = {}
for path in sorted(overlay.rglob("*")):
    relative = path.relative_to(overlay)
    # A local run leaves bazel-* symlinks and a lockfile in the test module.
    if path.is_symlink() or path.is_dir() or path.name == "MODULE.bazel.lock":
        continue
    if any(part.startswith("bazel-") for part in relative.parts):
        continue
    digest = hashlib.sha256(path.read_bytes()).digest()
    hashes[relative.as_posix()] = "sha256-" + base64.b64encode(digest).decode()
source["overlay"] = hashes
# Upstream fixes carried until a release has them; applied with -p1.
patches = version_dir / "patches"
if patches.is_dir():
    source["patches"] = {
        patch.name: "sha256-" + base64.b64encode(hashlib.sha256(patch.read_bytes()).digest()).decode()
        for patch in sorted(patches.glob("*.patch"))
    }
    source["patch_strip"] = 1
source_json.write_text(json.dumps(source, indent=4) + "\n")
print(f"{source_json}: {len(hashes)} overlay files")
