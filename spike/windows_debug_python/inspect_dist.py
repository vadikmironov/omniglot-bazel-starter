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


def check_artifacts(install: pathlib.Path, stem: str) -> list[str]:
    """The _d files an embedder links against have to exist."""
    errors = []
    for name in (
        f"{stem}.dll",
        f"libs/{stem}.lib",
        "include/Python.h",
        "include/pyconfig.h",
    ):
        path = install / name
        if path.exists():
            print(f"  present: {name:<28} {path.stat().st_size:>10,} bytes")
        else:
            errors.append(f"missing artifact: {name}")

    # Free-threaded builds carry the full ABI tag, so the marker is not always
    # the last thing before .pyd: _asyncio_d.pyd but _asyncio_d.cp314t-win32.pyd.
    pyds = sorted(p.name for p in (install / "DLLs").glob("*.pyd") if "_d" in p.name)
    print(f"  debug extension modules: {len(pyds)}")
    for name in pyds[:5]:
        print(f"    {name}")
    if not pyds:
        errors.append("no debug extension modules")
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
    # Py_DEBUG and ABIFLAGS only reach Windows config vars from 3.14, so they
    # are reported but not asserted. EXT_SUFFIX carries the marker everywhere.
    # ABIFLAGS is only emulated on Windows from 3.14, so EXT_SUFFIX is the
    # signal that holds across every version PBS supports.
    if "_d" not in str(config_vars.get("EXT_SUFFIX", "")):
        errors.append(f"EXT_SUFFIX is {config_vars.get('EXT_SUFFIX')!r}, expected to contain _d")
    return errors


def main() -> int:
    # Everything in the tar is prefixed with python/, and PYTHON.json sits at
    # the top of that rather than beside it.
    root = unpack() / "python"

    # The interpreter library is named for the version, plus t when
    # free-threaded and _d for a debug build, so build the stem from metadata
    # rather than assuming any of it.
    meta = json.loads((root / "PYTHON.json").read_text())
    major, minor, _ = meta["python_version"].split(".")
    freethreaded = "freethreaded" in meta.get("build_options", "")
    stem = f"python{major}{minor}{'t' if freethreaded else ''}_d"

    print(f"=== artifacts ({stem}) ===")
    errors = check_artifacts(root / "install", stem)
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
