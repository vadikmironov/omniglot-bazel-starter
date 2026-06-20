"""Tests for docker_login_helper.py."""

import base64
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = ""
for candidate in [
    Path(os.environ.get("TEST_SRCDIR", "")) / "_main" / "tools" / "publish" / "docker_login_helper.py",
    Path(__file__).resolve().parent.parent / "docker_login_helper.py",
]:
    if candidate.is_file():
        _SCRIPT = str(candidate)
        break

if not _SCRIPT:
    raise FileNotFoundError("docker_login_helper.py not found in runfiles or source tree")


def _run(*args):
    return subprocess.run(
        [sys.executable, _SCRIPT, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _expected_auth(login: str, password: str) -> str:
    return base64.b64encode(f"{login}:{password}".encode()).decode()


class DockerLoginHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.netrc_path = self.tmpdir / "netrc"
        self.config_path = self.tmpdir / "docker" / "config.json"
        self.host = "artifactory.invalid"
        self.netrc_path.write_text(
            f"machine {self.host}\n  login alice\n  password t0p-s3cr3t\n",
        )
        self.netrc_path.chmod(0o600)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_default(self):
        return _run(
            "--registry",
            self.host,
            "--config-path",
            str(self.config_path),
            "--netrc-path",
            str(self.netrc_path),
        )

    def _seed_config(self, content):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            self.config_path.write_text(json.dumps(content))
        else:
            self.config_path.write_text(content)

    def test_creates_file_when_absent(self):
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.config_path.is_file())
        config = json.loads(self.config_path.read_text())
        self.assertEqual(
            config["auths"][self.host]["auth"],
            _expected_auth("alice", "t0p-s3cr3t"),
        )
        self.assertEqual(stat.S_IMODE(self.config_path.stat().st_mode), 0o600)

    def test_adds_to_empty_object(self):
        self._seed_config({})
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertIn(self.host, config["auths"])

    def test_preserves_unrelated_registry(self):
        self._seed_config({"auths": {"other.invalid": {"auth": "OTHER"}}})
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertEqual(config["auths"]["other.invalid"]["auth"], "OTHER")
        self.assertEqual(
            config["auths"][self.host]["auth"],
            _expected_auth("alice", "t0p-s3cr3t"),
        )

    def test_overwrites_stale_auth(self):
        self._seed_config({"auths": {self.host: {"auth": "STALE"}}})
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertEqual(
            config["auths"][self.host]["auth"],
            _expected_auth("alice", "t0p-s3cr3t"),
        )

    def test_replaces_registrytoken_with_basic(self):
        self._seed_config({"auths": {self.host: {"registrytoken": "STALE_JWT"}}})
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertEqual(
            config["auths"][self.host],
            {"auth": _expected_auth("alice", "t0p-s3cr3t")},
        )

    def test_fails_on_credhelpers_conflict(self):
        original = json.dumps({"credHelpers": {self.host: "ecr-login"}})
        self._seed_config(original)
        result = self._run_default()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credHelpers", result.stderr)
        self.assertEqual(self.config_path.read_text(), original)

    def test_warns_on_credsstore(self):
        self._seed_config({"credsStore": "osxkeychain"})
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING", result.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertIn(self.host, config["auths"])
        self.assertEqual(config["credsStore"], "osxkeychain")

    def test_fails_on_malformed_json(self):
        original = "not valid json{"
        self._seed_config(original)
        result = self._run_default()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR", result.stderr)
        self.assertEqual(self.config_path.read_text(), original)

    def test_preserves_unknown_top_level_fields(self):
        self._seed_config(
            {
                "plugins": {"foo": "bar"},
                "currentContext": "default",
                "experimental": "enabled",
            }
        )
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertEqual(config["plugins"], {"foo": "bar"})
        self.assertEqual(config["currentContext"], "default")
        self.assertEqual(config["experimental"], "enabled")
        self.assertIn(self.host, config["auths"])

    def test_forces_0600_mode(self):
        self._seed_config({})
        self.config_path.chmod(0o644)
        result = self._run_default()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(self.config_path.stat().st_mode), 0o600)

    def test_idempotent(self):
        result1 = self._run_default()
        self.assertEqual(result1.returncode, 0, result1.stderr)
        content1 = self.config_path.read_text()
        result2 = self._run_default()
        self.assertEqual(result2.returncode, 0, result2.stderr)
        content2 = self.config_path.read_text()
        self.assertEqual(content1, content2)

    def test_multiple_registries_sequentially(self):
        self.netrc_path.write_text(
            f"machine {self.host}\n  login alice\n  password t0p-s3cr3t\n"
            "machine other.invalid\n  login bob\n  password 0th3r-p4ss\n",
        )
        result1 = self._run_default()
        self.assertEqual(result1.returncode, 0, result1.stderr)
        result2 = _run(
            "--registry",
            "other.invalid",
            "--config-path",
            str(self.config_path),
            "--netrc-path",
            str(self.netrc_path),
        )
        self.assertEqual(result2.returncode, 0, result2.stderr)
        config = json.loads(self.config_path.read_text())
        self.assertEqual(
            config["auths"][self.host]["auth"],
            _expected_auth("alice", "t0p-s3cr3t"),
        )
        self.assertEqual(
            config["auths"]["other.invalid"]["auth"],
            _expected_auth("bob", "0th3r-p4ss"),
        )

    def test_fails_when_no_netrc_match(self):
        result = _run(
            "--registry",
            "missing.invalid",
            "--config-path",
            str(self.config_path),
            "--netrc-path",
            str(self.netrc_path),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing.invalid", result.stderr)

    def test_fails_when_netrc_absent(self):
        absent = self.tmpdir / "no_netrc"
        result = _run(
            "--registry",
            self.host,
            "--config-path",
            str(self.config_path),
            "--netrc-path",
            str(absent),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
