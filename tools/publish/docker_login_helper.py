"""Populate ~/.docker/config.json with basic auth from .netrc.

Reads .netrc for the configured registry host, merges an auths.<host>
entry into ~/.docker/config.json (preserving every other field), and exits.
Invoked by the :publish_image wrapper before oci_push; go-containerregistry
(which oci_push wraps) then performs the Docker Registry v2 token exchange
itself at push time.

Owns exactly one key in config.json: auths.<registry-host>. Never touches
other registries' auths entries or any top-level fields (credsStore,
credHelpers, plugins, currentContext, ...).

Fails when:
- the existing config.json is malformed JSON
- credHelpers.<our-host> is set (auth-delegation conflict)
- .netrc has no credentials for our host

Warns and proceeds when:
- top-level credsStore is set (writes may be shadowed; if pushes fail
  with 401, run `docker logout <host>`)

Concurrency: serialised via flock(2) on ~/.docker/config.json.lock.
Atomicity: tempfile + rename. Mode forced to 0600 after every write.
"""

import argparse
import base64
import contextlib
import fcntl
import json
import netrc
import os
import sys
import tempfile
from pathlib import Path


def load_credentials(netrc_path: Path, host: str) -> tuple[str, str]:
    if not netrc_path.is_file():
        sys.exit(f"ERROR: {netrc_path} not found; cannot resolve credentials for {host}.")
    try:
        rc = netrc.netrc(str(netrc_path))
    except netrc.NetrcParseError as exc:
        sys.exit(f"ERROR: failed to parse {netrc_path}: {exc}")
    auth = rc.authenticators(host)
    if not auth:
        sys.exit(f"ERROR: no credentials in {netrc_path} for host {host!r}.")
    login, _account, password = auth
    if not login or not password:
        sys.exit(f"ERROR: incomplete credentials in {netrc_path} for host {host!r}.")
    return login, password


def read_existing_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except json.JSONDecodeError as exc:
        sys.exit(
            f"ERROR: existing {config_path} is not valid JSON ({exc}); "
            "refusing to overwrite. Inspect or remove the file."
        )
    if not isinstance(data, dict):
        sys.exit(f"ERROR: existing {config_path} is JSON but not an object.")
    return data


def check_conflicts(config: dict, host: str, config_path: Path) -> None:
    cred_helpers = config.get("credHelpers")
    if isinstance(cred_helpers, dict) and host in cred_helpers:
        sys.exit(
            f"ERROR: {config_path} delegates auth for {host} to credential "
            f"helper {cred_helpers[host]!r}. Remove credHelpers.{host} from "
            "config.json or unconfigure the helper before publishing images."
        )
    creds_store = config.get("credsStore")
    if creds_store:
        print(
            f"WARNING: {config_path} has credsStore={creds_store!r} set; auth "
            f"writes for {host} may be shadowed. If pushes fail with 401, run "
            f"`docker logout {host}` and retry.",
            file=sys.stderr,
        )


def merge_auth(config: dict, host: str, login: str, password: str) -> dict:
    auths = config.setdefault("auths", {})
    if not isinstance(auths, dict):
        sys.exit("ERROR: existing config.json has non-object auths field; refusing to overwrite.")
    encoded = base64.b64encode(f"{login}:{password}".encode()).decode()
    # Replace entire entry — drops any stale registrytoken / identitytoken.
    auths[host] = {"auth": encoded}
    return config


def atomic_write(config_path: Path, config: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=config_path.name + ".",
        suffix=".tmp",
        dir=str(config_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(config, fp, indent=2)
            fp.write("\n")
            fp.flush()
            os.fsync(fp.fileno())
        tmp_path.chmod(0o600)
        tmp_path.replace(config_path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
        raise


@contextlib.contextmanager
def lock_file(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Populate ~/.docker/config.json with basic auth from .netrc.",
    )
    parser.add_argument(
        "--registry",
        required=True,
        help="Registry hostname (e.g., artifactory.invalid).",
    )
    parser.add_argument(
        "--config-path",
        default=str(Path.home() / ".docker" / "config.json"),
        help="Override path to docker config.json (for testing).",
    )
    parser.add_argument(
        "--netrc-path",
        default=str(Path.home() / ".netrc"),
        help="Override path to .netrc (for testing).",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config_path)
    netrc_path = Path(args.netrc_path)
    lock_path = Path(str(config_path) + ".lock")

    login, password = load_credentials(netrc_path, args.registry)

    with lock_file(lock_path):
        config = read_existing_config(config_path)
        check_conflicts(config, args.registry, config_path)
        config = merge_auth(config, args.registry, login, password)
        atomic_write(config_path, config)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
