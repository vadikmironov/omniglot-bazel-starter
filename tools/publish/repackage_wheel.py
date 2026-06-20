#!/usr/bin/env python3
"""Repackage a wheel with a new version.

Reads a wheel file (a zip archive), patches the Version in METADATA,
renames the .dist-info directory, regenerates RECORD hashes, and writes
a new wheel with the corrected filename.

Usage:
    python3 repackage_wheel.py <input.whl> <new_version> <output_dir>

Prints the absolute path to the output wheel on stdout.
Uses only Python stdlib.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path


def _record_hash(data: bytes) -> str:
    """Compute a PEP 376 RECORD hash: ``sha256=<urlsafe-b64-no-padding>``."""
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _patch_metadata(content: bytes, new_version: str) -> bytes:
    """Replace the ``Version:`` field in METADATA with *new_version*."""
    text = content.decode("utf-8")
    patched = re.sub(r"^Version: .+$", f"Version: {new_version}", text, count=1, flags=re.MULTILINE)
    return patched.encode("utf-8")


def _find_dist_info(names: list[str]) -> str:
    """Return the dist-info directory prefix (e.g. ``pkg-0.0.0.dist-info``)."""
    for name in names:
        parts = name.split("/")
        if len(parts) >= 2 and parts[0].endswith(".dist-info"):
            return parts[0]
    raise ValueError("No .dist-info directory found in wheel")


def repackage_wheel(input_path: str, new_version: str, output_dir: str) -> str:
    """Repackage *input_path* wheel with *new_version*.

    Returns the absolute path to the new wheel in *output_dir*.
    """
    input_whl = Path(input_path)
    old_filename = input_whl.name

    with zipfile.ZipFile(input_whl, "r") as zin:
        old_dist_info = _find_dist_info(zin.namelist())

    # Derive old version from dist-info dir: "pkg-0.0.0.dist-info" → "0.0.0"
    dist_name = old_dist_info.rsplit(".dist-info", 1)[0]
    # Split on the last hyphen to get (distribution, version)
    sep_idx = dist_name.rfind("-")
    if sep_idx < 0:
        raise ValueError(f"Cannot parse version from dist-info: {old_dist_info}")
    distribution = dist_name[:sep_idx]
    old_version = dist_name[sep_idx + 1 :]

    new_dist_info = f"{distribution}-{new_version}.dist-info"

    # Build new wheel filename: replace old version with new
    new_filename = old_filename.replace(f"{distribution}-{old_version}", f"{distribution}-{new_version}", 1)
    output_path = Path(output_dir) / new_filename

    record_entries: list[tuple[str, str, str]] = []

    with zipfile.ZipFile(input_whl, "r") as zin, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith("/"):
                continue  # skip directory entries

            data = zin.read(item.filename)

            # Rename paths under old dist-info → new dist-info
            new_name = item.filename.replace(old_dist_info, new_dist_info, 1)

            # Patch Version in METADATA
            if item.filename == f"{old_dist_info}/METADATA":
                data = _patch_metadata(data, new_version)

            # Skip RECORD — regenerated below
            if item.filename == f"{old_dist_info}/RECORD":
                continue

            zout.writestr(new_name, data, compress_type=item.compress_type)
            record_entries.append((new_name, _record_hash(data), str(len(data))))

        # Write regenerated RECORD
        record_name = f"{new_dist_info}/RECORD"
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        for entry in record_entries:
            writer.writerow(entry)
        writer.writerow((record_name, "", ""))  # RECORD's own entry: empty hash/size
        record_data = buf.getvalue().encode("utf-8")
        zout.writestr(record_name, record_data)

    return str(output_path.resolve())


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <input.whl> <new_version> <output_dir>", file=sys.stderr)
        sys.exit(1)
    result = repackage_wheel(sys.argv[1], sys.argv[2], sys.argv[3])
    print(result)
