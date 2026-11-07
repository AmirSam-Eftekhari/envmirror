"""Command-line interface.

Conventions: results go to stdout, progress and diagnostics go to stderr.
In ``--format json`` mode nothing but the JSON document is written to stdout
and no progress output is produced.

Exit codes: 0 success; 1 findings at/above ``--fail-on`` (compare only);
2 usage error (Typer/Click); 3 invalid or unreadable snapshot; 4 output
file could not be written.
"""

import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from . import __version__
from .engine import compare_snapshots
from .errors import EXIT_DIFFERENCES, EnvMirrorError
from .models.comparison import Severity, severity_rank
from .reporting.html_report import render_html
from .reporting.json_report import comparison_to_json
from .reporting.terminal import render_comparison, render_snapshot
from .scanner import scan as run_scan
from .snapshot_io import read_snapshot, write_text_atomic

app = typer.Typer(
    name="envmirror",
    help="Compare development environments. Find configuration drift.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


class FailOn(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"
    none = "none"


@dataclass
class State:
    quiet: bool = False
    verbose: bool = False


def _state(ctx: typer.Context) -> State:
    return ctx.obj if isinstance(ctx.obj, State) else State()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"envmirror {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress progress and summary output.")
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed progress and explanations.")
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """Compare development environments. Find configuration drift."""
    if quiet and verbose:
        raise typer.BadParameter("--quiet and --verbose cannot be used together.")
    ctx.obj = State(quiet=quiet, verbose=verbose)


def _emit(text: str) -> None:
    try:
        typer.echo(text, nl=False)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.flush()


def _fail(message: str, code: int) -> typer.Exit:
    Console(stderr=True).print(f"Error: {message}", markup=False, highlight=False)
    return typer.Exit(code)


def _info(state: State, message: str, *, machine_readable: bool = False) -> None:
    if not state.quiet and not machine_readable:
        Console(stderr=True).print(message, markup=False, highlight=False)


@app.command()
def scan(
    ctx: typer.Context,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write the snapshot JSON to this file."),
    ] = None,
    project: Annotated[
        Path,
        typer.Option(
            "--project",
            "-p",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Project directory whose package.json is inspected (default: current directory).",
        ),
    ] = Path("."),
    no_project: Annotated[
        bool, typer.Option("--no-project", help="Do not read any project directory.")
    ] = False,
    include_env_names: Annotated[
        bool,
        typer.Option(
            "--include-env-names",
            help="PRIVACY: also record the NAMES (never values) of all environment variables. "
            "Names can reveal tools, vendors or internal projects.",
        ),
    ] = False,
    env_value: Annotated[
        Optional[list[str]],
        typer.Option(
            "--env-value",
            help="PRIVACY: record the value of this environment variable (repeatable). "
            "Secret-looking names are always redacted; review the output before sharing.",
        ),
    ] = None,
    fmt: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Terminal output format.")
    ] = OutputFormat.text,
) -> None:
    """Scan this machine and produce a snapshot."""
    state = _state(ctx)
    machine = fmt is OutputFormat.json
    show_steps = state.verbose and not machine

    def step(message: str) -> None:
        if show_steps:
            Console(stderr=True).print(f"  - {message}", markup=False, highlight=False)

    _info(state, "Scanning local environment...", machine_readable=machine)
    try:
        snapshot = run_scan(
            None if no_project else project,
            include_all_env_names=include_env_names,
            include_env_values=env_value or [],
            progress=step,
        )
        text = snapshot.to_json()
        if output is not None:
            write_text_atomic(output, text)
            _info(state, f"Snapshot written to {output}", machine_readable=machine)
    except EnvMirrorError as exc:
        raise _fail(str(exc), exc.exit_code) from exc

    if machine:
        if output is None:
            _emit(text)
    elif not state.quiet:
        render_snapshot(Console(), snapshot)
        if output is None:
            _info(state, "Tip: use --output FILE to save this snapshot.")


@app.command()
def compare(
    ctx: typer.Context,
    baseline: Annotated[Path, typer.Argument(help="Snapshot of the reference (working) machine.")],
    target: Annotated[Path, typer.Argument(help="Snapshot of the machine being investigated.")],
    html: Annotated[
        Optional[Path], typer.Option("--html", help="Also write a self-contained HTML report.")
    ] = None,
    fmt: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format for stdout.")
    ] = OutputFormat.text,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Exit with status 1 if any finding has at least this severity."),
    ] = FailOn.high,
) -> None:
    """Compare two snapshots (baseline first, target second)."""
    state = _state(ctx)
    machine = fmt is OutputFormat.json
    try:
        base_snap, base_warn = read_snapshot(baseline)
        target_snap, target_warn = read_snapshot(target)
        result = compare_snapshots(
            base_snap, target_snap, baseline_label=baseline.name, target_label=target.name
        )
        if html is not None:
            write_text_atomic(html, render_html(result, base_snap, target_snap))
            _info(state, f"HTML report written to {html}", machine_readable=machine)
    except EnvMirrorError as exc:
        raise _fail(str(exc), exc.exit_code) from exc

    if state.verbose and not machine:
        for name, warns in ((baseline.name, base_warn), (target.name, target_warn)):
            for warning in warns:
                _info(state, f"Warning ({name}): {warning}")
    if machine:
        _emit(comparison_to_json(result))
    elif not state.quiet:
        render_comparison(Console(), result, verbose=state.verbose)

    if fail_on is not FailOn.none:
        threshold = severity_rank(Severity(fail_on.value))
        if any(severity_rank(f.severity) >= threshold for f in result.findings):
            raise typer.Exit(EXIT_DIFFERENCES)


@app.command()
def inspect(
    ctx: typer.Context,
    snapshot: Annotated[Path, typer.Argument(help="Snapshot file to display.")],
    fmt: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.text,
) -> None:
    """Show the contents of a snapshot."""
    state = _state(ctx)
    try:
        loaded, warnings = read_snapshot(snapshot)
    except EnvMirrorError as exc:
        raise _fail(str(exc), exc.exit_code) from exc
    if fmt is OutputFormat.json:
        _emit(loaded.to_json())
        return
    if not state.quiet:
        render_snapshot(Console(), loaded)
        for warning in warnings:
            _info(state, f"Warning: {warning}")


@app.command()
def validate(
    ctx: typer.Context,
    snapshot: Annotated[Path, typer.Argument(help="Snapshot file to validate.")],
    fmt: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.text,
) -> None:
    """Check that a file is a valid snapshot (exit status 3 if not)."""
    state = _state(ctx)
    try:
        loaded, warnings = read_snapshot(snapshot)
    except EnvMirrorError as exc:
        if fmt is OutputFormat.json:
            _emit(json.dumps({"valid": False, "error": str(exc)}, indent=2) + "\n")
            raise typer.Exit(exc.exit_code) from exc
        raise _fail(str(exc), exc.exit_code) from exc
    if fmt is OutputFormat.json:
        payload = {"valid": True, "schema_version": loaded.schema_version, "warnings": warnings}
        _emit(json.dumps(payload, indent=2) + "\n")
        return
    if not state.quiet:
        typer.echo(f"OK: {snapshot} is a valid snapshot (schema {loaded.schema_version}).")
        for warning in warnings:
            _info(state, f"Warning: {warning}")


if __name__ == "__main__":
    app()
