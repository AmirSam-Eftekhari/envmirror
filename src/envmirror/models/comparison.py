"""Comparison result models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
)


def severity_rank(severity: Severity) -> int:
    """Higher means more severe (CRITICAL=4 ... INFO=0)."""
    return len(SEVERITY_ORDER) - 1 - SEVERITY_ORDER.index(severity)


class Classification(StrEnum):
    """What kind of finding this is. None of these claim causality."""

    CONFIRMED = "confirmed_difference"  # unambiguous: something exists on one side only
    POTENTIAL_RISK = "potential_compatibility_risk"  # differs in a way that may matter
    INFORMATIONAL = "informational"  # differs, but rarely relevant on its own


class Category(StrEnum):
    SYSTEM = "system"
    RUNTIME = "runtime"
    TOOL = "tool"
    PYTHON_PACKAGE = "python_package"
    NODE_PACKAGE = "node_package"
    ENVIRONMENT = "environment"


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    category: Category
    field: str
    expected: str | None
    actual: str | None
    severity: Severity
    classification: Classification
    rule_id: str
    explanation: str
    suggested_action: str


class SnapshotRef(BaseModel):
    label: str
    created_at: str
    platform: str
    architecture: str
    envmirror_version: str
    schema_version: str


class Summary(BaseModel):
    total: int
    by_severity: dict[str, int]
    by_classification: dict[str, int]
    by_category: dict[str, int]


class ComparisonResult(BaseModel):
    baseline: SnapshotRef
    target: SnapshotRef
    findings: list[Finding]
    summary: Summary
