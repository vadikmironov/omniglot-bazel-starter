# /// script
# requires-python = ">=3.11"
# dependencies = ["zstandard"]
# ///
"""Unpack a PBS distribution and check it really is a debug build.

Run from the python-build-standalone checkout:

    uv run --no-project --script ../spike/windows_debug_python/inspect_dist.py
"""

import glob
import json
import pathlib
import sys
import tarfile

import zstandard

OUT = pathlib.Path("unpacked")


def unpack() -> pathlib.Path:
    matches = glob.glob("dist/*.tar.zst")
    if not matches:
        sys.exit("no distribution under dist/")
    src = matches[0]
    print(f"unpacking {src}")
    with open(src, "rb") as fh, zstandard.ZstdDecompressor().stream_reader(fh) as z:
        with tarfile.open(fileobj=z, mode="r|") as tar:
            tar.extractall(OUT, filter="data")
    return OUT


def check_artifacts(install: pathlib.Path) -> list[str]:
    """The _d files an embedder links against have to exist."""
    errors = []
    for name in ("python_d.exe", "python314_d.dll", "libs/python314_d.lib"):
        path = install / name
        if path.exists():
            print(f"  present: {name:<28} {path.stat().st_size:>10,} bytes")
        else:
            errors.append(f"missing artifact: {name}")

    pyds = sorted(p.name for p in (install / "DLLs").glob("*_d.pyd"))
    print(f"  debug extension modules: {len(pyds)}")
    for name in pyds[:5]:
        print(f"    {name}")
    if not pyds:
        errors.append("no _d.pyd extension modules")
    return errors


def check_metadata(root: pathlib.Path) -> list[str]:
    """PYTHON.json has to declare the build it actually is."""
    errors = []
    meta = json.loads((root / "PYTHON.json").read_text())
    for key in ("version", "target_triple", "build_options", "python_version"):
        print(f"  {key:<16}: {meta.get(key)}")

    config_vars = meta["python_config_vars"]
    for key in ("Py_DEBUG", "ABIFLAGS", "EXT_SUFFIX"):
        print(f"  {key:<16}: {config_vars.get(key)}")

    if "debug" not in meta.get("build_options", ""):
        errors.append(f"build_options does not contain debug: {meta.get('build_options')}")
    if str(config_vars.get("Py_DEBUG")) != "1":
        errors.append(f"Py_DEBUG is {config_vars.get('Py_DEBUG')}, expected 1")
    if "_d" not in str(config_vars.get("ABIFLAGS", "")):
        errors.append(f"ABIFLAGS is {config_vars.get('ABIFLAGS')!r}, expected to contain _d")
    return errors


def main() -> int:
    root = unpack()
    install = root / "python" / "install"

    print("=== artifacts ===")
    errors = check_artifacts(install)
    print("=== metadata ===")
    errors += check_metadata(root)

    if errors:
        print("\nFAIL")
        for err in errors:
            print(f"  {err}")
        return 1
    print("\nPASS: distribution is a debug build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
