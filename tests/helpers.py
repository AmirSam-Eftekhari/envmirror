"""Shared test helpers (importable because pyproject sets pythonpath=tests)."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from envmirror.models.snapshot import Snapshot
from envmirror.scanner._proc import CommandResult


def base_snapshot_dict() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "envmirror_version": "0.1.0",
        "created_at": "2026-11-04T12:00:00Z",
        "system": {
            "platform": "Linux",
            "os_release": "6.8.0",
            "os_version": "#1 SMP",
            "architecture": "x86_64",
            "python_implementation": "CPython",
            "cpu_count": 8,
        },
        "runtimes": {
            "python": {"status": "found", "version": "3.12.1"},
            "node": {"status": "found", "version": "22.0.0"},
            "npm": {"status": "found", "version": "10.5.0"},
            "java": {"status": "not_found"},
            "rustc": {"status": "not_found"},
        },
        "tools": {
            "git": {"status": "found", "version": "2.45.0"},
            "docker": {"status": "not_found"},
        },
        "packages": {"python": {"requests": "2.32.0", "pytest": "8.2.0"}, "node": None},
        "environment": {"values": {"LANG": "en_US.UTF-8"}, "present": []},
        "metadata": {"scanner_version": "0.1.0", "project_scanned": False, "scan_warnings": []},
    }


def deep_update(target: dict[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in changes.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
    return target


def snapshot_dict(**changes: Any) -> dict[str, Any]:
    return deep_update(base_snapshot_dict(), changes)


def make_snapshot(**changes: Any) -> Snapshot:
    return Snapshot.model_validate(snapshot_dict(**changes))


def found(version: str) -> dict[str, Any]:
    return {"status": "found", "version": version}


def fake_runner(
    results: Mapping[str, CommandResult | Callable[[], CommandResult]],
    calls: list[Sequence[str]] | None = None,
) -> Callable[[Sequence[str]], CommandResult]:
    """Runner returning canned results keyed by executable name (default: not found)."""

    def run(argv: Sequence[str]) -> CommandResult:
        if calls is not None:
            calls.append(list(argv))
        entry = results.get(argv[0], CommandResult("not_found"))
        return entry() if callable(entry) else entry

    return run


def ok(output: str, returncode: int = 0) -> CommandResult:
    return CommandResult("ok", output, returncode)
