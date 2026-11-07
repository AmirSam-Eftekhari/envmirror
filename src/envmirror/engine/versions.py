"""Small, dependency-free version comparison helpers."""

from __future__ import annotations

import re
from enum import StrEnum


class Delta(StrEnum):
    NONE = "none"
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    BUILD = "build"  # same major.minor.patch, different text (pre-release, suffix, range operator)
    UNPARSEABLE = "unparseable"


_LENIENT = re.compile(r"^[\s^~<>=v]*(\d+)(?:\.(\d+))?(?:\.(\d+))?")
_SIMPLE_SPEC = re.compile(r"^[\^~=v]*(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-[0-9A-Za-z.-]+)?$")


def parse_version(
    value: str, *, java: bool = False, simple_spec: bool = False
) -> tuple[int, int, int] | None:
    """Parse ``major[.minor[.patch]]`` from the start of ``value``.

    ``java`` handles the legacy ``1.8.0`` scheme (major is 8). ``simple_spec``
    only accepts plain npm specs such as ``^1.2.3``; ranges like ``>=1 <3``,
    ``workspace:*`` or git URLs return ``None``.
    """
    text = value.strip()
    if java and text.startswith("1."):
        text = text[2:]
    match = (_SIMPLE_SPEC if simple_spec else _LENIENT).match(text)
    if not match:
        return None
    major, minor, patch = (int(g) if g is not None else 0 for g in match.groups())
    return major, minor, patch


def version_delta(
    expected: str, actual: str, *, java: bool = False, simple_spec: bool = False
) -> Delta:
    if expected == actual:
        return Delta.NONE
    a = parse_version(expected, java=java, simple_spec=simple_spec)
    b = parse_version(actual, java=java, simple_spec=simple_spec)
    if a is None or b is None:
        return Delta.UNPARSEABLE
    if a[0] != b[0]:
        return Delta.MAJOR
    if a[1] != b[1]:
        return Delta.MINOR
    if a[2] != b[2]:
        return Delta.PATCH
    return Delta.BUILD
