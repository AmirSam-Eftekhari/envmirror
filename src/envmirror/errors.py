"""Exception types and process exit codes."""

from __future__ import annotations

EXIT_OK = 0
EXIT_DIFFERENCES = 1  # compare: findings at or above --fail-on threshold
# Exit code 2 is reserved by Click/Typer for command-line usage errors.
EXIT_INVALID_SNAPSHOT = 3
EXIT_OUTPUT_ERROR = 4


class EnvMirrorError(Exception):
    """Base class for expected, user-facing errors."""

    exit_code = 1


class SnapshotError(EnvMirrorError):
    """A snapshot file is missing, unreadable, malformed or invalid."""

    exit_code = EXIT_INVALID_SNAPSHOT


class OutputError(EnvMirrorError):
    """An output file could not be written."""

    exit_code = EXIT_OUTPUT_ERROR
