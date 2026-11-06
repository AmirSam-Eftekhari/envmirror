"""System information. Deliberately omits hostnames, usernames and paths."""

from __future__ import annotations

import os
import platform

from ..models.snapshot import SystemInfo

_ARCH_ALIASES = {
    "amd64": "x86_64",
    "x64": "x86_64",
    "x86_64": "x86_64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "i386": "x86",
    "i686": "x86",
    "x86": "x86",
}


def normalize_architecture(machine: str) -> str:
    """Map platform-specific spellings (AMD64, aarch64, ...) to one name."""
    key = machine.strip().lower()
    return _ARCH_ALIASES.get(key, key or "unknown")


def collect_system() -> SystemInfo:
    return SystemInfo(
        platform=platform.system() or "unknown",
        os_release=platform.release(),
        os_version=platform.version()[:200],
        architecture=normalize_architecture(platform.machine()),
        python_implementation=platform.python_implementation(),
        cpu_count=os.cpu_count() or None,
    )
