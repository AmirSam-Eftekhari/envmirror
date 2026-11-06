"""Runtime and tool detection. Best-effort; failures never abort a scan."""

from __future__ import annotations

import platform
import re

from ..models.snapshot import Detection
from ._proc import Runner

_GENERIC = re.compile(r"(\d+\.\d+(?:\.\d+)*)")
_JAVA = re.compile(r'version\s+"([^"\s]+)"')

# name -> (argv, regex). Each argv is a fixed list; nothing comes from user input.
_PROBES: dict[str, tuple[list[str], re.Pattern[str]]] = {
    "node": (["node", "--version"], _GENERIC),
    "npm": (["npm", "--version"], _GENERIC),
    "java": (["java", "-version"], _JAVA),
    "rustc": (["rustc", "--version"], _GENERIC),
    "git": (["git", "--version"], _GENERIC),
    "docker": (["docker", "--version"], _GENERIC),
}

RUNTIME_NAMES = ("python", "node", "npm", "java", "rustc")
TOOL_NAMES = ("git", "docker")


def parse_version(output: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(output)
    return match.group(1) if match else None


def detect(name: str, runner: Runner) -> Detection:
    argv, pattern = _PROBES[name]
    result = runner(argv)
    if result.status == "not_found":
        return Detection(status="not_found")
    if result.status == "timeout":
        return Detection(status="timeout", detail="command timed out")
    if result.status == "error":
        return Detection(status="error", detail="command could not be executed")
    if result.returncode not in (0, None):
        return Detection(status="error", detail=f"exited with status {result.returncode}")
    version = parse_version(result.output, pattern)
    if version is None:
        return Detection(status="error", detail="version output not recognised")
    return Detection(status="found", version=version)


def detect_python() -> Detection:
    """The interpreter running EnvMirror (no subprocess needed)."""
    return Detection(status="found", version=platform.python_version())


def detect_runtimes(runner: Runner) -> dict[str, Detection]:
    result = {"python": detect_python()}
    for name in RUNTIME_NAMES:
        if name != "python":
            result[name] = detect(name, runner)
    return result


def detect_tools(runner: Runner) -> dict[str, Detection]:
    return {name: detect(name, runner) for name in TOOL_NAMES}
