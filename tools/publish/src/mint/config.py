"""TOML configuration loading for mint."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import tomllib


@dataclass(frozen=True)
class SchemaConfig:
    """A version schema definition."""

    release: str
    development: str
    auto_increment: str | None = None  # patch | minor | major


@dataclass(frozen=True)
class ComponentSetConfig:
    """A named group of modules sharing a coordinated version."""

    modules: list[str]


@dataclass(frozen=True)
class PublishConfig:
    """Top-level publish configuration."""

    schema: str  # template string, e.g. "{semver}"
    schemas: dict[str, SchemaConfig]
    component_sets: dict[str, ComponentSetConfig]
    independent: list[str]

    def resolve_schema(self) -> tuple[str, SchemaConfig]:
        """Extract the schema name from the template and return (name, config).

        The schema field is a template like "{semver}" or "prefix_{calver}".
        This extracts the first {name} and looks it up in schemas.
        """
        match = re.search(r"\{(\w+)\}", self.schema)
        if not match:
            raise ValueError(f"repo.schema must contain a {{name}} reference to a schema, got: {self.schema}")
        name = match.group(1)
        if name not in self.schemas:
            raise ValueError(
                f"Schema '{name}' referenced in repo.schema not found. Available: {', '.join(self.schemas)}"
            )
        return name, self.schemas[name]

    def format_version(self, raw_version: str) -> str:
        """Apply the repo.schema template wrapper around a raw version string.

        If schema is just "{semver}", returns the version unchanged.
        If schema is "prefix_{semver}_suffix", wraps accordingly.
        """
        schema_name, _ = self.resolve_schema()
        return re.sub(r"\{" + schema_name + r"\}", raw_version, self.schema)

    def all_modules(self) -> list[str]:
        """Return all modules across all component sets and independent."""
        modules = []
        for cs in self.component_sets.values():
            modules.extend(cs.modules)
        modules.extend(self.independent)
        return modules


def load_config(path: Path) -> PublishConfig:
    """Load and validate .publish.toml."""
    with path.open("rb") as f:
        raw = tomllib.load(f)

    # Parse schemas
    schemas: dict[str, SchemaConfig] = {}
    for name, schema_data in raw.get("schemas", {}).items():
        if "release" not in schema_data:
            raise ValueError(f"Schema '{name}' missing 'release' template")
        if "development" not in schema_data:
            raise ValueError(f"Schema '{name}' missing 'development' template")
        auto_inc = schema_data.get("auto_increment")
        if auto_inc is not None and auto_inc not in ("patch", "minor", "major"):
            raise ValueError(f"Schema '{name}' auto_increment must be patch/minor/major, got: {auto_inc}")
        schemas[name] = SchemaConfig(
            release=schema_data["release"],
            development=schema_data["development"],
            auto_increment=auto_inc,
        )

    # Parse repo section
    repo = raw.get("repo", {})
    schema_template = repo.get("schema", "")
    if not schema_template:
        raise ValueError("[repo] section must define 'schema'")

    # Validate schema reference
    match = re.search(r"\{(\w+)\}", schema_template)
    if not match:
        raise ValueError(f"repo.schema must contain a {{name}} reference, got: {schema_template}")
    if match.group(1) not in schemas:
        raise ValueError(
            f"Schema '{match.group(1)}' referenced in repo.schema not found. Available: {', '.join(schemas)}"
        )

    # Parse component sets
    component_sets: dict[str, ComponentSetConfig] = {}
    for name, cs_data in raw.get("component_sets", {}).items():
        modules = cs_data.get("modules", [])
        if not modules:
            raise ValueError(f"Component set '{name}' has no modules")
        for label in modules:
            _validate_label(label)
        component_sets[name] = ComponentSetConfig(modules=list(modules))

    # Parse independent components
    components = raw.get("components", {})
    independent = list(components.get("independent", []))
    for label in independent:
        _validate_label(label)

    # Check for duplicate modules
    seen: dict[str, str] = {}
    for set_name, cs in component_sets.items():
        for label in cs.modules:
            if label in seen:
                raise ValueError(f"Module '{label}' appears in both '{seen[label]}' and '{set_name}'")
            seen[label] = set_name
    for label in independent:
        if label in seen:
            raise ValueError(f"Module '{label}' appears in both '{seen[label]}' and independent")
        seen[label] = "independent"

    return PublishConfig(
        schema=schema_template,
        schemas=schemas,
        component_sets=component_sets,
        independent=independent,
    )


def _validate_label(label: str) -> None:
    """Validate a Bazel label format."""
    if not label.startswith("//"):
        raise ValueError(f"Bazel label must start with '//', got: {label}")
