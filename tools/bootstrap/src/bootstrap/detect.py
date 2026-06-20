"""Detection of previously bootstrapped repositories.

Lets a re-run recover a target repo's name, languages, features, and code dir
instead of re-interrogating the user. Detection is *authoritative*, not
heuristic: every scaffold writes a ``BOOTSTRAP_MARKER_FILE`` recording the exact
selection, and this module reads it back. The repo name is the one exception —
it stays in ``MODULE.bazel`` where Bazel itself owns it. No marker ⇒ not
detected, so the caller asks the user rather than guessing.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from bootstrap.manifest import BootstrapManifest, read_bootstrap_marker

_MODULE_NAME_RE = re.compile(r'module\(\s*name\s*=\s*"([^"]+)"')

_DEFAULT_MODULE_DIR = "modules"


@dataclass
class DetectedRepo:
    """What was recovered from an existing bootstrapped repo."""

    name: str
    languages: set[str] = field(default_factory=set)
    features: set[str] = field(default_factory=set)
    module_dir: str = _DEFAULT_MODULE_DIR


def detect_repo(target: Path, manifest: BootstrapManifest) -> DetectedRepo | None:
    """Return a :class:`DetectedRepo` for a target a previous bootstrap produced,
    else ``None``.

    Two authoritative reads, no inference: a ``MODULE.bazel`` with a parseable
    ``module(name = ...)`` is the gate and supplies the name; the
    ``BOOTSTRAP_MARKER_FILE`` supplies languages, features, and the code dir.
    A repo missing either is treated as un-detected so the caller asks the user
    rather than guessing from filesystem signals.
    """
    module_bazel = target / "MODULE.bazel"
    if not module_bazel.is_file():
        return None
    name_match = _MODULE_NAME_RE.search(module_bazel.read_text())
    if name_match is None:
        return None

    marker = read_bootstrap_marker(target, manifest)
    if marker is None:
        return None
    languages, features, module_dir = marker
    return DetectedRepo(
        name=name_match.group(1),
        languages=languages,
        features=features,
        module_dir=module_dir,
    )
