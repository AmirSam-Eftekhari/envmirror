"""Human-readable explanations and suggested diagnostic actions.

Wording is deliberately cautious: a difference is a lead to investigate, not
proof of what caused a failure.
"""

from __future__ import annotations

from ..models.comparison import Category
from .diff import Difference, Kind


def _label(diff: Difference) -> str:
    cat = diff.category
    if cat is Category.SYSTEM:
        return f"System field '{diff.name}'"
    if cat is Category.RUNTIME:
        return f"Runtime '{diff.name}'"
    if cat is Category.TOOL:
        return f"Tool '{diff.name}'"
    if cat is Category.PYTHON_PACKAGE:
        return f"Python package '{diff.name}'"
    if cat is Category.NODE_PACKAGE:
        if diff.group == "project":
            return "Node project data"
        group = diff.group.replace("_", " ")
        return f"Node {group} entry '{diff.name}'"
    return f"Environment variable '{diff.name}'"


def describe(diff: Difference) -> str:
    """One factual sentence about what differs (no claims about impact)."""
    label = _label(diff)
    if diff.kind is Kind.CHANGED:
        return f"{label} is {diff.expected} in the baseline and {diff.actual} in the target."
    if diff.kind is Kind.MISSING:
        return f"{label} is present in the baseline ({diff.expected}) but not found in the target."
    if diff.kind is Kind.EXTRA:
        return f"{label} is present in the target ({diff.actual}) but not in the baseline."
    return f"{label} could not be compared reliably (baseline: {diff.expected}; target: {diff.actual})."


_ACTIONS: dict[Category, dict[Kind, str]] = {
    Category.SYSTEM: {
        Kind.CHANGED: "Check whether the project uses native extensions, containers or "
        "OS-specific scripts; if so, confirm they are built or tested for the target system.",
    },
    Category.RUNTIME: {
        Kind.CHANGED: "Compare against the version the project declares (for example .nvmrc, "
        "engines, python_requires or CI config) and run the project's tests on the target "
        "with the baseline version.",
        Kind.MISSING: "Install the runtime on the target (or confirm the project does not "
        "need it) and re-run `envmirror scan`.",
        Kind.EXTRA: "No action needed unless the extra runtime shadows another on PATH.",
        Kind.INDETERMINATE: "Run the runtime's version command by hand on the target and "
        "check PATH, then re-scan.",
    },
    Category.TOOL: {
        Kind.CHANGED: "Check the tool's release notes between the two versions if a "
        "command behaves differently.",
        Kind.MISSING: "Install the tool on the target if the workflow needs it, then re-scan.",
        Kind.EXTRA: "No action needed.",
        Kind.INDETERMINATE: "Run the tool's version command by hand on the target and re-scan.",
    },
    Category.PYTHON_PACKAGE: {
        Kind.CHANGED: "Compare against the project's requirements or lock file; reinstall "
        "from it into a fresh virtual environment on the target.",
        Kind.MISSING: "Check whether the project needs this package; if so, install it from "
        "the project's requirements into the target environment.",
        Kind.EXTRA: "No action needed unless an import or version conflict appears.",
        Kind.INDETERMINATE: "Re-scan and compare again.",
    },
    Category.NODE_PACKAGE: {
        Kind.CHANGED: "Compare package.json and lockfile in version control, then reinstall "
        "using the project's documented package manager.",
        Kind.MISSING: "Check which branch or commit each machine has checked out, and that "
        "the lockfile was committed and installed.",
        Kind.EXTRA: "Check whether the target has uncommitted or branch-specific changes.",
        Kind.INDETERMINATE: "Run `envmirror scan --project <dir>` on both machines so both "
        "snapshots include the project, then compare again.",
    },
    Category.ENVIRONMENT: {
        Kind.CHANGED: "Check shell profile, CI settings or container configuration for "
        "where this variable is set.",
        Kind.MISSING: "Check shell profile, CI settings or container configuration for "
        "where this variable is set on the baseline.",
        Kind.EXTRA: "No action needed unless behavior differs.",
        Kind.INDETERMINATE: "Re-scan and compare again.",
    },
}


def suggest(diff: Difference) -> str:
    """A concrete diagnostic step for this difference."""
    by_kind = _ACTIONS.get(diff.category, {})
    return by_kind.get(diff.kind) or by_kind.get(Kind.CHANGED) or "Investigate manually."
