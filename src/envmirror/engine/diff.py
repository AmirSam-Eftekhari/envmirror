"""Structural comparison of two snapshots.

Produces neutral ``Difference`` facts. Severity and explanations are assigned
separately (risk.py, diagnosis.py) so every layer can be tested on its own.
Convention: the *baseline* (first snapshot) is the reference environment, the
*target* (second snapshot) is the environment being investigated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..models.comparison import Category
from ..models.snapshot import Detection, NodeProject, Snapshot
from ..security.redaction import REDACTED
from .versions import Delta, version_delta


class Kind(StrEnum):
    MISSING = "missing"  # in baseline, absent in target
    EXTRA = "extra"  # absent in baseline, in target
    CHANGED = "changed"
    INDETERMINATE = "indeterminate"  # could not be compared reliably


@dataclass(frozen=True)
class Difference:
    category: Category
    field: str
    name: str
    kind: Kind
    expected: str | None
    actual: str | None
    delta: Delta = Delta.NONE
    group: str = ""


def _describe(det: Detection | None) -> str:
    if det is None:
        return "not probed"
    if det.status == "found":
        return det.version or "found"
    return f"{det.status}: {det.detail}" if det.detail else det.status


def _compare_detections(
    category: Category,
    prefix: str,
    baseline: dict[str, Detection],
    target: dict[str, Detection],
) -> list[Difference]:
    out: list[Difference] = []
    for name in sorted(set(baseline) | set(target)):
        a, b = baseline.get(name), target.get(name)
        field = f"{prefix}.{name}"
        if a is not None and b is not None and a.status == "not_found" and b.status == "not_found":
            continue
        if a is not None and b is not None and a.status == "found" and b.status == "found":
            assert a.version is not None and b.version is not None
            delta = version_delta(a.version, b.version, java=(name == "java"))
            if delta is not Delta.NONE:
                out.append(
                    Difference(category, field, name, Kind.CHANGED, a.version, b.version, delta)
                )
        elif a is not None and a.status == "found" and b is not None and b.status == "not_found":
            out.append(Difference(category, field, name, Kind.MISSING, a.version, None))
        elif a is not None and a.status == "not_found" and b is not None and b.status == "found":
            out.append(Difference(category, field, name, Kind.EXTRA, None, b.version))
        else:
            out.append(
                Difference(category, field, name, Kind.INDETERMINATE, _describe(a), _describe(b))
            )
    return out


def _compare_versions(
    category: Category,
    prefix: str,
    group: str,
    baseline: dict[str, str],
    target: dict[str, str],
    *,
    simple_spec: bool = False,
) -> list[Difference]:
    out: list[Difference] = []
    for name in sorted(set(baseline) | set(target)):
        field = f"{prefix}.{name}"
        a, b = baseline.get(name), target.get(name)
        if a is not None and b is None:
            out.append(Difference(category, field, name, Kind.MISSING, a, None, group=group))
        elif a is None and b is not None:
            out.append(Difference(category, field, name, Kind.EXTRA, None, b, group=group))
        elif a is not None and b is not None and a != b:
            delta = version_delta(a, b, simple_spec=simple_spec)
            out.append(Difference(category, field, name, Kind.CHANGED, a, b, delta, group))
    return out


def _compare_package_manager(a: str | None, b: str | None) -> list[Difference]:
    field, cat = "packages.node.package_manager", Category.NODE_PACKAGE
    if a == b:
        return []
    if a is not None and b is None:
        return [Difference(cat, field, "packageManager", Kind.MISSING, a, None, group="package_manager")]
    if a is None and b is not None:
        return [Difference(cat, field, "packageManager", Kind.EXTRA, None, b, group="package_manager")]
    assert a is not None and b is not None
    a_name, _, a_ver = a.partition("@")
    b_name, _, b_ver = b.partition("@")
    delta = Delta.MAJOR if a_name != b_name else version_delta(a_ver, b_ver)
    return [Difference(cat, field, "packageManager", Kind.CHANGED, a, b, delta, "package_manager")]


def _compare_node(a: NodeProject, b: NodeProject) -> list[Difference]:
    cat = Category.NODE_PACKAGE
    out = _compare_package_manager(a.package_manager, b.package_manager)
    out += _compare_versions(
        cat, "packages.node.dependencies", "dependencies", a.dependencies, b.dependencies,
        simple_spec=True,
    )
    out += _compare_versions(
        cat, "packages.node.dev_dependencies", "dev_dependencies",
        a.dev_dependencies, b.dev_dependencies, simple_spec=True,
    )
    out += _compare_versions(
        cat, "packages.node.engines", "engines", a.engines, b.engines, simple_spec=False
    )
    for lock in sorted(set(a.lockfiles) - set(b.lockfiles)):
        out.append(Difference(cat, f"packages.node.lockfiles.{lock}", lock, Kind.MISSING, lock, None, group="lockfile"))
    for lock in sorted(set(b.lockfiles) - set(a.lockfiles)):
        out.append(Difference(cat, f"packages.node.lockfiles.{lock}", lock, Kind.EXTRA, None, lock, group="lockfile"))
    return out


def _compare_environment(a: Snapshot, b: Snapshot) -> list[Difference]:
    cat = Category.ENVIRONMENT
    out: list[Difference] = []
    a_names = set(a.environment.values) | set(a.environment.present)
    b_names = set(b.environment.values) | set(b.environment.present)
    for name in sorted(a_names - b_names):
        out.append(Difference(cat, f"environment.{name}", name, Kind.MISSING, "set", None, group="presence"))
    for name in sorted(b_names - a_names):
        out.append(Difference(cat, f"environment.{name}", name, Kind.EXTRA, None, "set", group="presence"))
    for name in sorted(set(a.environment.values) & set(b.environment.values)):
        va, vb = a.environment.values[name], b.environment.values[name]
        if va != vb and REDACTED not in (va, vb):
            out.append(Difference(cat, f"environment.values.{name}", name, Kind.CHANGED, va, vb, group="value"))
    return out


def _compare_system(a: Snapshot, b: Snapshot) -> list[Difference]:
    cat = Category.SYSTEM
    fields = ["platform", "architecture"]
    if a.system.platform == b.system.platform:
        fields += ["os_release", "os_version"]
    fields.append("python_implementation")
    out: list[Difference] = []
    for f in fields:
        va, vb = getattr(a.system, f), getattr(b.system, f)
        if va != vb:
            out.append(Difference(cat, f"system.{f}", f, Kind.CHANGED, va or None, vb or None))
    return out


def compare_differences(baseline: Snapshot, target: Snapshot) -> list[Difference]:
    """All differences between two snapshots, in deterministic order."""
    out = _compare_system(baseline, target)
    out += _compare_detections(Category.RUNTIME, "runtimes", baseline.runtimes, target.runtimes)
    out += _compare_detections(Category.TOOL, "tools", baseline.tools, target.tools)
    out += _compare_versions(
        Category.PYTHON_PACKAGE, "packages.python", "python",
        baseline.packages.python, target.packages.python,
    )
    a_node, b_node = baseline.packages.node, target.packages.node
    if a_node is not None and b_node is not None:
        out += _compare_node(a_node, b_node)
    elif a_node is not None or b_node is not None:
        out.append(
            Difference(
                Category.NODE_PACKAGE, "packages.node", "node project", Kind.INDETERMINATE,
                "present" if a_node else "absent", "present" if b_node else "absent",
                group="project",
            )
        )
    out += _compare_environment(baseline, target)
    return out
