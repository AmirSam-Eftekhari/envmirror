"""Snapshot data model (schema version 1.x).

Schema evolution policy
-----------------------
* ``schema_version`` is ``"<major>.<minor>"``.
* Minor bumps only *add* optional fields. Readers ignore unknown fields and
  report them as warnings, so a 1.0 reader can open a 1.3 file.
* Major bumps may break compatibility. A reader refuses files with a major
  version newer than it supports, and upgrades older majors through the
  ``MIGRATIONS`` registry (empty for now: 1 is the first major version).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"
SUPPORTED_MAJOR = 1

# Printable text only: control characters could corrupt terminals or reports.
SafeStr = Annotated[
    str,
    StringConstraints(max_length=256, pattern=r"^[^\x00-\x1f\x7f-\x9f]*$"),
]
Timestamp = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]
SchemaVersionStr = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}$")]

MAX_PACKAGES = 20_000

# Maps an old major version to a function upgrading raw data to the next major.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


class _Model(BaseModel):
    # Unknown fields are ignored (forward compatibility) and reported by the loader.
    model_config = ConfigDict(extra="ignore")


class SystemInfo(_Model):
    platform: SafeStr
    os_release: SafeStr = ""
    os_version: SafeStr = ""
    architecture: SafeStr
    python_implementation: SafeStr = ""
    cpu_count: Annotated[int, Field(ge=1, le=100_000)] | None = None


class Detection(_Model):
    """Outcome of probing for one runtime or tool."""

    status: Literal["found", "not_found", "timeout", "error"]
    version: SafeStr | None = None
    detail: SafeStr | None = None

    @model_validator(mode="after")
    def _found_needs_version(self) -> Detection:
        if self.status == "found" and not self.version:
            raise ValueError("status 'found' requires a version")
        return self


class NodeProject(_Model):
    package_manager: SafeStr | None = None
    dependencies: dict[SafeStr, SafeStr] = Field(default_factory=dict, max_length=MAX_PACKAGES)
    dev_dependencies: dict[SafeStr, SafeStr] = Field(
        default_factory=dict, max_length=MAX_PACKAGES
    )
    engines: dict[SafeStr, SafeStr] = Field(default_factory=dict, max_length=64)
    lockfiles: list[SafeStr] = Field(default_factory=list, max_length=16)


class Packages(_Model):
    python: dict[SafeStr, SafeStr] = Field(default_factory=dict, max_length=MAX_PACKAGES)
    node: NodeProject | None = None


class EnvironmentInfo(_Model):
    """Non-sensitive environment metadata. Never holds raw variable dumps."""

    values: dict[SafeStr, SafeStr] = Field(default_factory=dict, max_length=256)
    present: list[SafeStr] = Field(default_factory=list, max_length=4096)


class Metadata(_Model):
    scanner_version: SafeStr
    project_scanned: bool = False
    scan_warnings: list[SafeStr] = Field(default_factory=list, max_length=64)


class Snapshot(_Model):
    schema_version: SchemaVersionStr
    envmirror_version: SafeStr
    created_at: Timestamp
    system: SystemInfo
    runtimes: dict[SafeStr, Detection] = Field(default_factory=dict, max_length=64)
    tools: dict[SafeStr, Detection] = Field(default_factory=dict, max_length=64)
    packages: Packages = Field(default_factory=Packages)
    environment: EnvironmentInfo = Field(default_factory=EnvironmentInfo)
    metadata: Metadata

    @model_validator(mode="after")
    def _check_major(self) -> Snapshot:
        major = int(self.schema_version.split(".")[0])
        if major > SUPPORTED_MAJOR:
            raise ValueError(
                f"schema_version {self.schema_version} is newer than supported "
                f"major version {SUPPORTED_MAJOR}; upgrade EnvMirror"
            )
        return self

    def to_json(self) -> str:
        """Deterministic serialization: sorted keys, 2-space indent, trailing newline."""
        data = self.model_dump(mode="json")
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def top_level_unknown_fields(raw: dict[str, Any]) -> list[str]:
    """Names of top-level keys that this version of the schema does not define."""
    return sorted(k for k in raw if k not in Snapshot.model_fields)


def migrate_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade raw snapshot data to the supported major version if needed."""
    version = raw.get("schema_version")
    if not isinstance(version, str) or not re.fullmatch(r"\d{1,3}\.\d{1,3}", version):
        return raw
    major = int(version.split(".")[0])
    while major < SUPPORTED_MAJOR and major in MIGRATIONS:
        raw = MIGRATIONS[major](raw)
        major += 1
    return raw
