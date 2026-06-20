"""Tests for repackage_wheel.py."""

import base64
import csv
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

# Locate the script via runfiles or relative path
_SCRIPT = ""
for candidate in [
    Path(os.environ.get("TEST_SRCDIR", "")) / "_main" / "tools" / "publish" / "repackage_wheel.py",
    Path(__file__).resolve().parent.parent / "repackage_wheel.py",
]:
    if candidate.is_file():
        _SCRIPT = str(candidate)
        break

if not _SCRIPT:
    raise FileNotFoundError("repackage_wheel.py not found in runfiles or source tree")


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _create_wheel(
    tmpdir: Path,
    distribution: str = "test_pkg",
    version: str = "0.0.0",
    python_tag: str = "py3",
) -> Path:
    """Create a minimal valid wheel for testing."""
    dist_info = f"{distribution}-{version}.dist-info"
    filename = f"{distribution}-{version}-{python_tag}-none-any.whl"
    whl_path = tmpdir / filename

    init_data = b"# test package\n"
    metadata_data = (f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n").encode()
    wheel_data = b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"

    entries = {
        f"{distribution}/__init__.py": init_data,
        f"{dist_info}/METADATA": metadata_data,
        f"{dist_info}/WHEEL": wheel_data,
    }

    # Build RECORD
    record_buf = io.StringIO()
    writer = csv.writer(record_buf, lineterminator="\n")
    for name, data in entries.items():
        writer.writerow((name, _record_hash(data), str(len(data))))
    record_name = f"{dist_info}/RECORD"
    writer.writerow((record_name, "", ""))
    entries[record_name] = record_buf.getvalue().encode()

    with zipfile.ZipFile(whl_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)

    return whl_path


class TestRepackageWheel(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.output_dir = Path(tempfile.mkdtemp())

    def _run(self, input_whl: Path, version: str) -> Path:
        result = subprocess.run(
            [sys.executable, _SCRIPT, str(input_whl), version, str(self.output_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())

    def test_basic_repackage(self):
        whl = _create_wheel(self.tmpdir)
        out = self._run(whl, "1.2.3")

        self.assertEqual(out.name, "test_pkg-1.2.3-py3-none-any.whl")
        self.assertTrue(out.exists())

        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            self.assertIn("test_pkg-1.2.3.dist-info/METADATA", names)
            self.assertIn("test_pkg-1.2.3.dist-info/WHEEL", names)
            self.assertIn("test_pkg-1.2.3.dist-info/RECORD", names)
            self.assertIn("test_pkg/__init__.py", names)

            metadata = zf.read("test_pkg-1.2.3.dist-info/METADATA").decode()
            self.assertIn("Version: 1.2.3", metadata)
            self.assertNotIn("Version: 0.0.0", metadata)

    def test_dev_version(self):
        whl = _create_wheel(self.tmpdir)
        out = self._run(whl, "1.2.3.dev5+abc1234")

        self.assertEqual(out.name, "test_pkg-1.2.3.dev5+abc1234-py3-none-any.whl")
        with zipfile.ZipFile(out) as zf:
            metadata = zf.read("test_pkg-1.2.3.dev5+abc1234.dist-info/METADATA").decode()
            self.assertIn("Version: 1.2.3.dev5+abc1234", metadata)

    def test_record_hashes_valid(self):
        whl = _create_wheel(self.tmpdir)
        out = self._run(whl, "2.0.0")

        with zipfile.ZipFile(out) as zf:
            record_data = zf.read("test_pkg-2.0.0.dist-info/RECORD").decode()
            reader = csv.reader(io.StringIO(record_data))
            for row in reader:
                name, hash_str, size_str = row[0], row[1], row[2]
                if not hash_str:
                    continue  # RECORD's own entry
                data = zf.read(name)
                self.assertEqual(hash_str, _record_hash(data), f"Hash mismatch for {name}")
                self.assertEqual(size_str, str(len(data)), f"Size mismatch for {name}")

    def test_record_self_entry(self):
        whl = _create_wheel(self.tmpdir)
        out = self._run(whl, "3.0.0")

        with zipfile.ZipFile(out) as zf:
            record_data = zf.read("test_pkg-3.0.0.dist-info/RECORD").decode()
            reader = csv.reader(io.StringIO(record_data))
            rows = list(reader)
            last = rows[-1]
            self.assertTrue(last[0].endswith("/RECORD"))
            self.assertEqual(last[1], "")
            self.assertEqual(last[2], "")

    def test_preserves_file_contents(self):
        whl = _create_wheel(self.tmpdir)
        out = self._run(whl, "4.0.0")

        with zipfile.ZipFile(whl) as orig, zipfile.ZipFile(out) as repackaged:
            orig_init = orig.read("test_pkg/__init__.py")
            new_init = repackaged.read("test_pkg/__init__.py")
            self.assertEqual(orig_init, new_init)

            orig_wheel = orig.read("test_pkg-0.0.0.dist-info/WHEEL")
            new_wheel = repackaged.read("test_pkg-4.0.0.dist-info/WHEEL")
            self.assertEqual(orig_wheel, new_wheel)

    def test_cli_stdout(self):
        whl = _create_wheel(self.tmpdir)
        result = subprocess.run(
            [sys.executable, _SCRIPT, str(whl), "5.0.0", str(self.output_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        output_path = Path(result.stdout.strip())
        self.assertTrue(output_path.exists())
        self.assertIn("5.0.0", output_path.name)

    def test_missing_metadata_fails(self):
        bad_whl = self.tmpdir / "bad-0.0.0-py3-none-any.whl"
        with zipfile.ZipFile(bad_whl, "w") as zf:
            zf.writestr("some_file.py", b"pass\n")

        result = subprocess.run(
            [sys.executable, _SCRIPT, str(bad_whl), "1.0.0", str(self.output_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
