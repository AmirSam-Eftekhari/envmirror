"""Comparison engine: diff -> risk assessment -> findings."""

from __future__ import annotations

from ..models.comparison import (
    ComparisonResult,
    Finding,
    SnapshotRef,
    Summary,
    severity_rank,
)
from ..models.snapshot import Snapshot
from .diagnosis import describe, suggest
from .diff import Difference, compare_differences
from .risk import Assessment, Context, assess

__all__ = ["build_finding", "compare_snapshots", "summarize"]


def build_finding(diff: Difference, assessment: Assessment) -> Finding:
    return Finding(
        id=f"{assessment.rule_id}:{diff.field}",
        category=diff.category,
        field=diff.field,
        expected=diff.expected,
        actual=diff.actual,
        severity=assessment.severity,
        classification=assessment.classification,
        rule_id=assessment.rule_id,
        explanation=f"{describe(diff)} {assessment.reason}",
        suggested_action=suggest(diff),
    )


def _ref(snapshot: Snapshot, label: str) -> SnapshotRef:
    return SnapshotRef(
        label=label,
        created_at=snapshot.created_at,
        platform=snapshot.system.platform,
        architecture=snapshot.system.architecture,
        envmirror_version=snapshot.envmirror_version,
        schema_version=snapshot.schema_version,
    )


def summarize(findings: list[Finding]) -> Summary:
    def count(values: list[str]) -> dict[str, int]:
        result: dict[str, int] = {}
        for value in values:
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))

    return Summary(
        total=len(findings),
        by_severity=count([f.severity.value for f in findings]),
        by_classification=count([f.classification.value for f in findings]),
        by_category=count([f.category.value for f in findings]),
    )


def compare_snapshots(
    baseline: Snapshot,
    target: Snapshot,
    *,
    baseline_label: str = "baseline",
    target_label: str = "target",
) -> ComparisonResult:
    """Compare two snapshots. Deterministic: same inputs give identical output."""
    ctx = Context(baseline_uses_node=baseline.packages.node is not None)
    findings = [
        build_finding(diff, assess(diff, ctx)) for diff in compare_differences(baseline, target)
    ]
    findings.sort(key=lambda f: (-severity_rank(f.severity), f.category.value, f.field, f.id))
    return ComparisonResult(
        baseline=_ref(baseline, baseline_label),
        target=_ref(target, target_label),
        findings=findings,
        summary=summarize(findings),
    )

