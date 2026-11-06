"""Safe subprocess execution.

Never uses a shell, applies a timeout, bounds captured output, and never
raises for missing executables or non-zero exit codes.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_OUTPUT = 64 * 1024

Status = Literal["ok", "not_found", "timeout", "error"]


@dataclass(frozen=True)
class CommandResult:
    status: Status
    output: str = ""
    returncode: int | None = None
    truncated: bool = False


Runner = Callable[[Sequence[str]], CommandResult]


def run_command(
    args: Sequence[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_output: int = DEFAULT_MAX_OUTPUT,
    cwd: Path | None = None,
) -> CommandResult:
    """Run ``args`` (argv list) and capture bounded stdout+stderr as text."""
    if not args:
        return CommandResult("error")
    executable = shutil.which(args[0])
    if executable is None:
        return CommandResult("not_found")
    try:
        proc = subprocess.Popen(
            [executable, *args[1:]],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError:
        return CommandResult("not_found")
    except OSError:
        return CommandResult("error")

    timed_out = threading.Event()

    def _kill() -> None:
        timed_out.set()
        try:
            proc.kill()
        except OSError:
            pass

    timer = threading.Timer(timeout, _kill)
    timer.start()
    truncated = False
    data = b""
    try:
        assert proc.stdout is not None
        data = proc.stdout.read(max_output + 1)
        if len(data) > max_output:
            truncated = True
            data = data[:max_output]
            proc.kill()
    finally:
        timer.cancel()
        if proc.stdout is not None:
            proc.stdout.close()
        returncode = proc.wait()

    if timed_out.is_set():
        return CommandResult("timeout", truncated=truncated)
    text = data.decode("utf-8", errors="replace")
    return CommandResult("ok", text, None if truncated else returncode, truncated)
