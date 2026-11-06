"""Self-contained HTML report (no external resources, no JavaScript)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..models.comparison import SEVERITY_ORDER, Category, ComparisonResult, Finding, severity_rank
from ..models.snapshot import Snapshot

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_SECTIONS: tuple[tuple[str, tuple[Category, ...]], ...] = (
    ("System differences", (Category.SYSTEM,)),
    ("Runtime differences", (Category.RUNTIME,)),
    ("Dependency differences", (Category.PYTHON_PACKAGE, Category.NODE_PACKAGE)),
    ("Tool differences", (Category.TOOL,)),
    ("Environment configuration differences", (Category.ENVIRONMENT,)),
)


def _environment() -> Environment:
    # autoescape=True explicitly: the template name ends in .j2, so extension-based
    # auto-detection would silently leave escaping off.
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _meta(snapshot: Snapshot, label: str) -> dict[str, Any]:
    node = snapshot.packages.node
    return {
        "label": label,
        "created_at": snapshot.created_at,
        "platform": snapshot.system.platform,
        "os_release": snapshot.system.os_release,
        "architecture": snapshot.system.architecture,
        "python_implementation": snapshot.system.python_implementation,
        "envmirror_version": snapshot.envmirror_version,
        "schema_version": snapshot.schema_version,
        "python_package_count": len(snapshot.packages.python),
        "node_included": node is not None,
        "project_scanned": snapshot.metadata.project_scanned,
        "warnings": list(snapshot.metadata.scan_warnings),
    }


def render_html(result: ComparisonResult, baseline: Snapshot, target: Snapshot) -> str:
    findings: list[Finding] = result.findings
    total = len(findings)
    severity_rows = []
    for sev in SEVERITY_ORDER:
        count = result.summary.by_severity.get(sev.value, 0)
        severity_rows.append(
            {"name": sev.value, "count": count, "pct": round(100 * count / total) if total else 0}
        )
    sections = []
    for title, categories in _SECTIONS:
        items = [f for f in findings if f.category in categories]
        sections.append({"title": title, "findings": items})

    recommendations: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for finding in sorted(findings, key=lambda f: -severity_rank(f.severity)):
        if finding.severity.value == "info":
            continue
        entry = seen.get(finding.suggested_action)
        if entry is None:
            entry = {"action": finding.suggested_action, "severity": finding.severity.value, "count": 0}
            seen[finding.suggested_action] = entry
            recommendations.append(entry)
        entry["count"] += 1

    template = _environment().get_template("report.html.j2")
    return template.render(
        result=result.model_dump(mode="json"),
        severity_rows=severity_rows,
        sections=[
            {"title": s["title"], "findings": [f.model_dump(mode="json") for f in s["findings"]]}
            for s in sections
        ],
        findings=[f.model_dump(mode="json") for f in findings],
        recommendations=recommendations,
        baseline=_meta(baseline, result.baseline.label),
        target=_meta(target, result.target.label),
    )
