"""Tests for download_lib.sh — resumable downloads against a misbehaving origin.

Each test spins up a local HTTP server that reproduces one proxy failure mode
and drives download_resumable at it, then asserts on both the bytes written and
the Range offsets the server actually saw. The offsets are the interesting half:
they are what distinguishes resuming from silently re-fetching the same prefix.
"""

import hashlib
import http.server
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

_LIB = ""
for candidate in [
    Path(os.environ.get("TEST_SRCDIR", "")) / "_main" / "tools" / "setup" / "download_lib.sh",
    Path(__file__).resolve().parent.parent / "download_lib.sh",
]:
    if candidate.is_file():
        _LIB = str(candidate)
        break

if not _LIB:
    raise FileNotFoundError("download_lib.sh not found in runfiles or source tree")


def _blob(size: int) -> bytes:
    return bytes((i * 7 + 11) % 251 for i in range(size))


class StallingOrigin:
    """Serves one blob, releasing at most `chunk` bytes per connection.

    After that it either hangs with the socket still open (``stall`` — the
    reported proxy behaviour, invisible to curl) or drops the connection
    (``drop``). ``heal_after`` lets the origin start behaving once enough
    requests have gone through, so a test can reach a successful completion.
    """

    def __init__(self, size, chunk, mode="stall", ranges=True, heal_after=None):
        self.blob = _blob(size)
        self.sha256 = hashlib.sha256(self.blob).hexdigest()
        self.chunk = chunk
        self.mode = mode
        self.ranges = ranges
        self.heal_after = heal_after
        self.offsets = []
        self._lock = threading.Lock()
        origin = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def do_GET(self):
                start = 0
                header = self.headers.get("Range")
                if header and origin.ranges and header.startswith("bytes="):
                    spec = header.split("=", 1)[1].split("-")[0]
                    start = int(spec) if spec else 0

                with origin._lock:
                    origin.offsets.append(start)
                    seen = len(origin.offsets)

                if start >= len(origin.blob):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(origin.blob)}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                body = origin.blob[start:]
                if start and origin.ranges:
                    self.send_response(206)
                    self.send_header(
                        "Content-Range",
                        f"bytes {start}-{len(origin.blob) - 1}/{len(origin.blob)}",
                    )
                else:
                    self.send_response(200)
                self.send_header("Accept-Ranges", "bytes" if origin.ranges else "none")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()

                healed = origin.heal_after is not None and seen > origin.heal_after
                if healed:
                    self.wfile.write(body)
                    self.wfile.flush()
                    return

                self.wfile.write(body[: origin.chunk])
                self.wfile.flush()
                if origin.mode == "stall":
                    # Hold the socket open and send nothing. TCP stays
                    # ESTABLISHED, so only a throughput floor can catch this.
                    time.sleep(300)
                else:
                    self.close_connection = True

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = Server(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.shutdown()
        self._server.server_close()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/blob"


class DownloadLibTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.dest = self.tmpdir / "artifact.bin"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def download(self, url, timeout=180, **env_overrides):
        env = {
            **os.environ,
            # Tight windows so the suite stays fast; production defaults live
            # in download_lib.sh.
            "DOWNLOAD_STALL_SECONDS": "2",
            "DOWNLOAD_RETRY_DELAY": "0",
            "DOWNLOAD_MAX_STALLED_RETRIES": "3",
            "DOWNLOAD_CONNECT_TIMEOUT": "5",
            **env_overrides,
        }
        return subprocess.run(
            [
                "bash",
                "-c",
                f'source "{_LIB}" && download_resumable "$1" "$2" --silent',
                "_",
                url,
                str(self.dest),
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=timeout,
        )

    def sha256(self):
        return hashlib.sha256(self.dest.read_bytes()).hexdigest()

    def test_resumes_through_repeated_stalls(self):
        """The reported failure: bytes arrive, then the proxy goes silent."""
        with StallingOrigin(size=500_000, chunk=100_000) as origin:
            result = self.download(origin.url)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dest.stat().st_size, 500_000)
        self.assertEqual(self.sha256(), origin.sha256)
        # Every attempt must pick up where the last one stopped. A restart-from-
        # zero loop would show repeated 0s here and never terminate.
        self.assertEqual(origin.offsets, [0, 100_000, 200_000, 300_000, 400_000])

    def test_resumes_after_dropped_connections(self):
        with StallingOrigin(size=300_000, chunk=100_000, mode="drop") as origin:
            result = self.download(origin.url)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sha256(), origin.sha256)
        self.assertEqual(origin.offsets, [0, 100_000, 200_000])

    def test_no_bytes_are_refetched(self):
        """Resuming must not re-transfer a prefix already on disk."""
        with StallingOrigin(size=400_000, chunk=100_000) as origin:
            self.download(origin.url)
            served = sum(min(origin.chunk, 400_000 - offset) for offset in origin.offsets)

        # 400_000 of payload delivered in 100_000-byte slices, nothing repeated.
        self.assertEqual(served, 400_000)

    def test_falls_back_to_a_clean_restart_when_ranges_are_refused(self):
        """An origin that ignores Range makes curl exit 33; start over once."""
        with StallingOrigin(size=200_000, chunk=50_000, ranges=False, heal_after=1) as origin:
            result = self.download(origin.url)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sha256(), origin.sha256)
        self.assertIn("restarting from byte 0", result.stderr)

    def test_gives_up_when_no_progress_is_possible(self):
        """A origin that never yields a byte must fail, not spin forever."""
        with StallingOrigin(size=200_000, chunk=0) as origin:
            result = self.download(origin.url, timeout=120)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("giving up", result.stderr)
        # Bounded by DOWNLOAD_MAX_STALLED_RETRIES rather than looping.
        self.assertLessEqual(len(origin.offsets), 4)

    def test_completed_file_is_left_alone(self):
        """A second call over a finished download is a no-op, not a re-fetch."""
        with StallingOrigin(size=150_000, chunk=150_000, heal_after=0) as origin:
            first = self.download(origin.url)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = self.download(origin.url)

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.dest.stat().st_size, 150_000)
        self.assertEqual(self.sha256(), origin.sha256)


if __name__ == "__main__":
    unittest.main()
