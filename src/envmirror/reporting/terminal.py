"""Rich terminal rendering.

Snapshot values are untrusted input. Everything is wrapped in ``rich.text.Text``
(never parsed as markup) and stripped of control characters.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..models.comparison import SEVERITY_ORDER, ComparisonResult, Severity
from ..models.snapshot import Detection, Snapshot

_STYLES = {
    Severity.CRITICAL: "bold white on red",
    Severity.HIGH: "bold red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "cyan",
    Severity.INFO: "dim",
}


def safe_text(value: object, style: str = "") -> Text:
    raw = "" if value is None else str(value)
    cleaned = "".join(ch if ch.isprintable() else "?" for ch in raw)
    return Text(cleaned, style=style)


def render_comparison(
    console: Console, result: ComparisonResult, *, verbose: bool = False, max_rows: int = 200
) -> None:
    summary = result.summary
    console.print(
        safe_text(
            f"Baseline: {result.baseline.label} ({result.baseline.platform}/{result.baseline.architecture})"
        )
    )
    console.print(
        safe_text(
            f"Target:   {result.target.label} ({result.target.platform}/{result.target.architecture})"
        )
    )
    if not result.findings:
        console.print(Text("\nNo differences found.", style="green"))
        return

    counts = Text("\n" + f"{summary.total} difference(s): ")
    parts = [(s, summary.by_severity.get(s.value, 0)) for s in SEVERITY_ORDER]
    for index, (sev, n) in enumerate([p for p in parts if p[1]]):
        if index:
            counts.append(", ")
        counts.append(f"{n} {sev.value}", style=_STYLES[sev])
    console.print(counts)

    table = Table(show_lines=False, header_style="bold")
    table.add_column("Severity", no_wrap=True)
    table.add_column("Field", overflow="fold")
    table.add_column("Baseline", overflow="fold")
    table.add_column("Target", overflow="fold")
    for finding in result.findings[:max_rows]:
        table.add_row(
            safe_text(finding.severity.value.upper(), _STYLES[finding.severity]),
            safe_text(finding.field),
            safe_text(finding.expected if finding.expected is not None else "-"),
            safe_text(finding.actual if finding.actual is not None else "-"),
        )
    console.print(table)
    if len(result.findings) > max_rows:
        console.print(
            safe_text(f"... {len(result.findings) - max_rows} more not shown; use --format json or --html for all.")
        )
    if verbose:
        for finding in result.findings[:max_rows]:
            console.print(safe_text(f"\n[{finding.id}]", "bold"))
            console.print(safe_text(finding.explanation))
            console.print(safe_text("Next step: " + finding.suggested_action, "cyan"))
    console.print(
        Text(
            "\nDifferences show where environments diverge; they do not prove that any one "
            "of them caused a failure.",
            style="dim",
        )
    )


def _fmt(det: Detection) -> str:
    if det.status == "found":
        return det.version or "found"
    return det.status.replace("_", " ") + (f" ({det.detail})" if det.detail else "")


def render_snapshot(console: Console, snapshot: Snapshot) -> None:
    system = snapshot.system
    console.print(safe_text(f"EnvMirror snapshot (schema {snapshot.schema_version})", "bold"))
    console.print(safe_text(f"Created:      {snapshot.created_at}"))
    console.print(safe_text(f"System:       {system.platform} {system.os_release} ({system.architecture})"))
    console.print(safe_text(f"Python impl.: {system.python_implementation}"))

    table = Table(header_style="bold")
    table.add_column("Kind")
    table.add_column("Name")
    table.add_column("Version / status", overflow="fold")
    for name, det in sorted(snapshot.runtimes.items()):
        table.add_row("runtime", safe_text(name), safe_text(_fmt(det)))
    for name, det in sorted(snapshot.tools.items()):
        table.add_row("tool", safe_text(name), safe_text(_fmt(det)))
    console.print(table)

    console.print(safe_text(f"Python packages: {len(snapshot.packages.python)}"))
    node = snapshot.packages.node
    if node is None:
        console.print(safe_text("Node project: not included"))
    else:
        console.print(
            safe_text(
                f"Node project: {len(node.dependencies)} dependencies, "
                f"{len(node.dev_dependencies)} devDependencies, "
                f"lockfiles: {', '.join(node.lockfiles) or 'none'}"
            )
        )
    env = snapshot.environment
    console.print(safe_text(f"Environment: {len(env.values)} value(s), {len(env.present)} name(s) recorded"))
    for warning in snapshot.metadata.scan_warnings:
        console.print(safe_text(f"Warning: {warning}", "yellow"))
