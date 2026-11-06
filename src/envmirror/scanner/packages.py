"""Python and Node package inspection. Never executes pip, npm or scripts."""

from __future__ import annotations

import json
import re
from importlib import metadata
from pathlib import Path
from typing import Any

from ..models.snapshot import NodeProject
from ..security.redaction import redact_home, redact_value

MAX_PACKAGE_JSON_BYTES = 2 * 1024 * 1024
LOCKFILES = (
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
)


def normalize_name(name: str) -> str:
    """PEP 503 normalization: lowercase, runs of ``-_.`` become ``-``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def collect_python_packages() -> dict[str, str]:
    """Installed distributions of the running interpreter, via importlib.metadata."""
    found: dict[str, str] = {}
    for dist in metadata.distributions():
        raw_name = dist.metadata["Name"] if dist.metadata else None
        version = dist.version
        if not raw_name or not version:
            continue
        name = normalize_name(raw_name)
        # Deterministic when a distribution is installed twice on sys.path.
        if name not in found or version > found[name]:
            found[name] = version
    return dict(sorted(found.items()))


def _string_map(value: Any, home: str | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, spec in value.items():
        if isinstance(key, str) and isinstance(spec, str):
            cleaned[key] = redact_value(redact_home(spec, home))
    return dict(sorted(cleaned.items()))


def collect_node_project(
    project_dir: Path, home: str | None = None
) -> tuple[NodeProject | None, list[str]]:
    """Read ``package.json`` and detect lockfiles in ``project_dir`` only.

    Returns (project or None, warnings). Lockfile *contents* are never read.
    """
    package_json = project_dir / "package.json"
    if not package_json.is_file():
        return None, []
    warnings: list[str] = []
    try:
        if package_json.stat().st_size > MAX_PACKAGE_JSON_BYTES:
            return None, ["package.json is too large; skipped"]
        data = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return None, ["package.json could not be read; skipped"]
    except (json.JSONDecodeError, RecursionError):
        return None, ["package.json is not valid JSON; skipped"]
    if not isinstance(data, dict):
        return None, ["package.json is not a JSON object; skipped"]

    manager = data.get("packageManager")
    engines = data.get("engines")
    project = NodeProject(
        package_manager=manager[:256] if isinstance(manager, str) else None,
        dependencies=_string_map(data.get("dependencies"), home),
        dev_dependencies=_string_map(data.get("devDependencies"), home),
        engines=_string_map(engines, home),
        lockfiles=[name for name in LOCKFILES if (project_dir / name).is_file()],
    )
    if not project.lockfiles:
        warnings.append("No Node lockfile found next to package.json")
    return project, warnings
