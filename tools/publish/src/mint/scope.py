"""Scope resolution for mint.

Maps CLI --scope argument to module lists and groups modules
by their version scope (repo-wide, component set, independent).
"""

from __future__ import annotations

from dataclasses import dataclass

from mint.config import PublishConfig
from mint.label import label_to_component_id


@dataclass(frozen=True)
class VersionGroup:
    """A group of modules sharing the same version scope."""

    tag_prefix: str  # "" for repo-wide, "set_name/" for sets, "comp-id/" for independent
    modules: list[str]


def resolve_scope(config: PublishConfig, scope: str | None) -> list[str]:
    """Resolve a CLI scope argument to a list of module labels.

    Args:
        config: The publish configuration.
        scope: None (everything), a component set name, or a Bazel label (//...).

    Returns:
        List of Bazel module labels to publish.
    """
    if scope is None:
        return _all_publishable_modules(config)

    if scope.startswith("//"):
        # Single module — validate it's known
        all_known = set(config.all_modules())
        if scope not in all_known:
            # Allow publishing modules not in config (they use repo-wide versioning)
            pass
        return [scope]

    # Component set name
    if scope in config.component_sets:
        return list(config.component_sets[scope].modules)

    available = ", ".join(sorted(config.component_sets.keys()))
    raise ValueError(f"Unknown scope '{scope}'. Available component sets: {available}")


def group_by_version_scope(config: PublishConfig, modules: list[str]) -> list[VersionGroup]:
    """Group modules by their version scope.

    Each group shares a tag prefix and will receive the same version.

    Returns:
        List of VersionGroup, one per distinct version scope.
    """
    # Build reverse lookup: module -> (scope_type, scope_key)
    module_to_set: dict[str, str] = {}
    for set_name, cs in config.component_sets.items():
        for label in cs.modules:
            module_to_set[label] = set_name

    independent_set = set(config.independent)

    # Group the requested modules
    set_groups: dict[str, list[str]] = {}
    independent_groups: dict[str, list[str]] = {}
    repo_wide: list[str] = []

    for label in modules:
        if label in module_to_set:
            set_name = module_to_set[label]
            set_groups.setdefault(set_name, []).append(label)
        elif label in independent_set:
            comp_id = label_to_component_id(label)
            independent_groups.setdefault(comp_id, []).append(label)
        else:
            repo_wide.append(label)

    groups = []
    if repo_wide:
        groups.append(VersionGroup(tag_prefix="", modules=repo_wide))
    for set_name in sorted(set_groups):
        groups.append(VersionGroup(tag_prefix=f"{set_name}/", modules=set_groups[set_name]))
    for comp_id in sorted(independent_groups):
        groups.append(VersionGroup(tag_prefix=f"{comp_id}/", modules=independent_groups[comp_id]))
    return groups


def _all_publishable_modules(config: PublishConfig) -> list[str]:
    """Return all modules from config (sets + independent)."""
    return config.all_modules()
