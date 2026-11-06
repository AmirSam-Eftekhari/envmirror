"""Environment scanner: orchestrates collectors into a Snapshot."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from ..models.snapshot import SCHEMA_VERSION, Metadata, Packages, Snapshot
from ._proc import Runner, run_command
from .environment import collect_environment
from .packages import collect_node_project, collect_python_packages
from .runtimes import detect_runtimes, detect_tools
from .system import collect_system

__all__ = ["scan", "run_command"]


def scan(
    project_dir: Path | None = None,
    *,
    runner: Runner | None = None,
    env: Mapping[str, str] | None = None,
    include_all_env_names: bool = False,
    include_env_values: Iterable[str] = (),
    progress: Callable[[str], None] | None = None,
    now: datetime | None = None,
) -> Snapshot:
    """Collect a snapshot of the local environment.

    ``runner`` and ``env`` are injectable so tests never touch real tools.
    """
    run = runner or run_command
    environment = os.environ if env is None else env
    home = os.path.expanduser("~")
    note = progress or (lambda _msg: None)
    warnings: list[str] = []

    note("Collecting system information")
    system = collect_system()
    note("Detecting runtimes")
    runtimes = detect_runtimes(run)
    note("Detecting tools")
    tools = detect_tools(run)
    note("Inspecting Python packages")
    python_packages = collect_python_packages()

    node = None
    if project_dir is not None:
        note("Reading package.json")
        node, node_warnings = collect_node_project(project_dir, home)
        warnings.extend(node_warnings)
    note("Reading environment metadata")
    env_info = collect_environment(
        environment,
        include_all_names=include_all_env_names,
        include_values=include_env_values,
        home=home,
    )
    created = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Snapshot(
        schema_version=SCHEMA_VERSION,
        envmirror_version=__version__,
        created_at=created,
        system=system,
        runtimes=runtimes,
        tools=tools,
        packages=Packages(python=python_packages, node=node),
        environment=env_info,
        metadata=Metadata(
            scanner_version=__version__,
            project_scanned=project_dir is not None,
            scan_warnings=warnings,
        ),
    )
