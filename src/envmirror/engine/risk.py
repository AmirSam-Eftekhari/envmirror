"""Transparent, rule-based risk classification.

Each ``Rule`` is declarative data plus a ``matches`` predicate, so rules can be
tested one at a time. The first matching rule wins; order matters. A rule's
``reason`` is shown to the user. A classification is a heuristic about
*compatibility risk*, never a claim about what caused a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models.comparison import Category, Classification, Severity
from ..scanner.environment import PRESENCE_VARS
from .diff import Difference, Kind
from .versions import Delta

C, K, D, S, CL = Category, Kind, Delta, Severity, Classification


@dataclass(frozen=True)
class Context:
    """Facts about the snapshots that some rules need."""

    baseline_uses_node: bool = False


@dataclass(frozen=True)
class Assessment:
    rule_id: str
    severity: Severity
    classification: Classification
    reason: str


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    severity: Severity
    classification: Classification
    reason: str
    categories: frozenset[Category] | None = None
    kinds: frozenset[Kind] | None = None
    deltas: frozenset[Delta] | None = None
    groups: frozenset[str] | None = None
    names: frozenset[str] | None = None
    exclude_names: frozenset[str] = frozenset()
    fields: frozenset[str] | None = None
    requires_baseline_node: bool = False

    def matches(self, diff: Difference, ctx: Context) -> bool:
        return (
            (self.categories is None or diff.category in self.categories)
            and (self.kinds is None or diff.kind in self.kinds)
            and (self.deltas is None or diff.delta in self.deltas)
            and (self.groups is None or diff.group in self.groups)
            and (self.names is None or diff.name in self.names)
            and diff.name not in self.exclude_names
            and (self.fields is None or diff.field in self.fields)
            and (not self.requires_baseline_node or ctx.baseline_uses_node)
        )

    def evaluate(self, diff: Difference, ctx: Context) -> Assessment | None:
        if self.matches(diff, ctx):
            return Assessment(self.id, self.severity, self.classification, self.reason)
        return None


def _fs(*items: Any) -> frozenset[Any]:
    return frozenset(items)


_MINOR_OR_PATCH_NOTE = "Minor and patch releases are usually compatible, but not always."
_SPEC_NOTE = (
    "Only declared version ranges from package.json were compared; the versions "
    "actually installed (lockfile) were not examined."
)
_ENV = _fs(C.ENVIRONMENT)
_RT = _fs(C.RUNTIME)
_TOOL = _fs(C.TOOL)
_PY = _fs(C.PYTHON_PACKAGE)
_NODE = _fs(C.NODE_PACKAGE)
_MINOR = _fs(D.MINOR)
_PATCH = _fs(D.PATCH)
_BUILD = _fs(D.BUILD)
_UNPARSE = _fs(D.UNPARSEABLE)

RULES: tuple[Rule, ...] = (
    Rule("RM-NODE-REQUIRED", "Node.js missing although the baseline describes a Node project",
         S.CRITICAL, CL.CONFIRMED,
         "The baseline snapshot includes a Node project, but Node.js was not found in the target.",
         categories=_RT, kinds=_fs(K.MISSING), names=_fs("node"), requires_baseline_node=True),
    Rule("RM-ARCH", "CPU architecture differs", S.HIGH, CL.POTENTIAL_RISK,
         "Native binaries, prebuilt wheels/addons and container images are architecture-specific.",
         categories=_fs(C.SYSTEM), fields=_fs("system.architecture")),
    Rule("RM-OS", "Operating system differs", S.INFO, CL.INFORMATIONAL,
         "Different operating systems are common and often fine; it matters mainly for "
         "paths, line endings, native dependencies and shell scripts.",
         categories=_fs(C.SYSTEM), fields=_fs("system.platform")),
    Rule("RM-OS-RELEASE", "OS release or version differs", S.INFO, CL.INFORMATIONAL,
         "Minor OS release differences rarely matter unless native libraries are involved.",
         categories=_fs(C.SYSTEM)),
    Rule("RM-RUNTIME-MISSING", "Runtime missing in target", S.HIGH, CL.CONFIRMED,
         "The runtime was detected in the baseline but not found in the target.",
         categories=_RT, kinds=_fs(K.MISSING)),
    Rule("RM-TOOL-MISSING", "Tool missing in target", S.MEDIUM, CL.CONFIRMED,
         "The tool was detected in the baseline but not found in the target.",
         categories=_TOOL, kinds=_fs(K.MISSING)),
    Rule("RM-RUNTIME-MAJOR", "Runtime major version differs", S.HIGH, CL.POTENTIAL_RISK,
         "Major versions may remove or change language and standard-library behavior.",
         categories=_RT, kinds=_fs(K.CHANGED), deltas=_fs(D.MAJOR)),
    Rule("RM-TOOL-MAJOR", "Tool major version differs", S.MEDIUM, CL.POTENTIAL_RISK,
         "Major versions of tools may change command-line behavior or defaults.",
         categories=_TOOL, kinds=_fs(K.CHANGED), deltas=_fs(D.MAJOR)),
    Rule("RM-RUNTIME-MINOR", "Runtime minor version differs", S.MEDIUM, CL.POTENTIAL_RISK,
         "Minor runtime releases can deprecate or add features the project relies on.",
         categories=_RT, kinds=_fs(K.CHANGED), deltas=_MINOR),
    Rule("RM-TOOL-MINOR", "Tool minor version differs", S.LOW, CL.POTENTIAL_RISK,
         _MINOR_OR_PATCH_NOTE, categories=_TOOL, kinds=_fs(K.CHANGED), deltas=_MINOR),
    Rule("RM-RUNTIME-PATCH", "Runtime patch version differs", S.LOW, CL.POTENTIAL_RISK,
         _MINOR_OR_PATCH_NOTE, categories=_RT, kinds=_fs(K.CHANGED), deltas=_PATCH),
    Rule("RM-TOOL-PATCH", "Tool patch version differs", S.LOW, CL.INFORMATIONAL,
         _MINOR_OR_PATCH_NOTE, categories=_TOOL, kinds=_fs(K.CHANGED), deltas=_PATCH),
    Rule("RM-RT-BUILD", "Runtime/tool differs only in suffix", S.INFO, CL.INFORMATIONAL,
         "Version numbers match; only a suffix such as a pre-release tag differs.",
         categories=_RT | _TOOL, kinds=_fs(K.CHANGED), deltas=_BUILD),
    Rule("RM-RT-UNPARSEABLE", "Runtime/tool version could not be ranked", S.LOW, CL.POTENTIAL_RISK,
         "The version strings differ but could not be compared numerically.",
         categories=_RT | _TOOL, kinds=_fs(K.CHANGED), deltas=_UNPARSE),
    Rule("RM-DETECTION-UNKNOWN", "Detection inconclusive", S.LOW, CL.INFORMATIONAL,
         "A probe timed out, failed, or was not run on one side, so presence and "
         "version cannot be compared reliably.",
         categories=_RT | _TOOL, kinds=_fs(K.INDETERMINATE)),
    Rule("RM-NODE-PROJECT-ONE-SIDED", "Node project data in only one snapshot", S.INFO,
         CL.INFORMATIONAL,
         "One snapshot has no package.json data (no project scanned, or none present), "
         "so Node dependencies were not compared.",
         categories=_NODE, kinds=_fs(K.INDETERMINATE), groups=_fs("project")),
    Rule("RM-PYPKG-MISSING", "Python package missing in target", S.MEDIUM, CL.CONFIRMED,
         "Installed in the baseline but not the target. Snapshots do not record which "
         "packages the project requires, so this is not rated higher.",
         categories=_PY, kinds=_fs(K.MISSING)),
    Rule("RM-PYPKG-MAJOR", "Python package major version differs", S.HIGH, CL.POTENTIAL_RISK,
         "Major releases of libraries often include breaking API changes.",
         categories=_PY, kinds=_fs(K.CHANGED), deltas=_fs(D.MAJOR)),
    Rule("RM-PYPKG-MINOR", "Python package minor version differs", S.MEDIUM, CL.POTENTIAL_RISK,
         "Minor releases may deprecate behavior or change defaults.",
         categories=_PY, kinds=_fs(K.CHANGED), deltas=_MINOR),
    Rule("RM-PYPKG-PATCH", "Python package patch version differs", S.LOW, CL.POTENTIAL_RISK,
         _MINOR_OR_PATCH_NOTE, categories=_PY, kinds=_fs(K.CHANGED), deltas=_PATCH),
    Rule("RM-PYPKG-OTHER", "Python package version text differs", S.LOW, CL.INFORMATIONAL,
         "Version numbers match or could not be ranked; the version text differs.",
         categories=_PY, kinds=_fs(K.CHANGED)),
    Rule("RM-NODEDEP-MISSING", "Declared Node dependency missing in target", S.HIGH, CL.CONFIRMED,
         "Declared under dependencies in the baseline package.json but absent in the target's.",
         categories=_NODE, kinds=_fs(K.MISSING), groups=_fs("dependencies")),
    Rule("RM-NODEDEV-MISSING", "Declared Node devDependency missing in target", S.MEDIUM,
         CL.CONFIRMED,
         "Declared under devDependencies in the baseline but absent in the target's.",
         categories=_NODE, kinds=_fs(K.MISSING), groups=_fs("dev_dependencies")),
    Rule("RM-NODEDEP-MAJOR", "Node dependency range major differs", S.HIGH, CL.POTENTIAL_RISK,
         _SPEC_NOTE, categories=_NODE, kinds=_fs(K.CHANGED), groups=_fs("dependencies"),
         deltas=_fs(D.MAJOR)),
    Rule("RM-NODEDEV-MAJOR", "Node devDependency range major differs", S.MEDIUM, CL.POTENTIAL_RISK,
         _SPEC_NOTE, categories=_NODE, kinds=_fs(K.CHANGED), groups=_fs("dev_dependencies"),
         deltas=_fs(D.MAJOR)),
    Rule("RM-NODEDEP-MINOR", "Node dependency range minor differs", S.MEDIUM, CL.POTENTIAL_RISK,
         _SPEC_NOTE, categories=_NODE, kinds=_fs(K.CHANGED), groups=_fs("dependencies"),
         deltas=_MINOR | _UNPARSE),
    Rule("RM-NODEDEV-MINOR", "Node devDependency range minor differs", S.LOW, CL.POTENTIAL_RISK,
         _SPEC_NOTE, categories=_NODE, kinds=_fs(K.CHANGED), groups=_fs("dev_dependencies"),
         deltas=_MINOR | _UNPARSE),
    Rule("RM-NODEDEP-PATCH", "Node dependency range patch/suffix differs", S.LOW,
         CL.INFORMATIONAL, _SPEC_NOTE, categories=_NODE, kinds=_fs(K.CHANGED),
         groups=_fs("dependencies", "dev_dependencies"), deltas=_PATCH | _BUILD),
    Rule("RM-PKGMGR-MAJOR", "Package manager or its major version differs", S.MEDIUM,
         CL.POTENTIAL_RISK,
         "Different package managers or major versions can resolve and install dependencies differently.",
         categories=_NODE, kinds=_fs(K.CHANGED), groups=_fs("package_manager"),
         deltas=_fs(D.MAJOR, D.UNPARSEABLE)),
    Rule("RM-PKGMGR-OTHER", "Package manager pin differs", S.LOW, CL.POTENTIAL_RISK,
         "The packageManager field differs in a minor, patch or missing way.",
         categories=_NODE, groups=_fs("package_manager"), kinds=_fs(K.CHANGED, K.MISSING)),
    Rule("RM-LOCKFILE-MISSING", "Lockfile missing in target", S.MEDIUM, CL.POTENTIAL_RISK,
         "Without the same lockfile, installs may resolve different dependency versions.",
         categories=_NODE, kinds=_fs(K.MISSING), groups=_fs("lockfile")),
    Rule("RM-ENGINES", "Node engines constraint differs", S.LOW, CL.POTENTIAL_RISK,
         "The declared engine requirements differ between package.json files.",
         categories=_NODE, groups=_fs("engines")),
    Rule("RM-ENV-NODE-ENV", "NODE_ENV differs", S.MEDIUM, CL.POTENTIAL_RISK,
         "NODE_ENV changes behavior of many Node libraries and build tools.",
         categories=_ENV, kinds=_fs(K.CHANGED), names=_fs("NODE_ENV")),
    Rule("RM-ENV-VALUE", "Environment variable value differs", S.LOW, CL.POTENTIAL_RISK,
         "Locale, timezone and CI flags can change tool and test behavior.",
         categories=_ENV, kinds=_fs(K.CHANGED)),
    Rule("RM-ENV-PRESENCE-KNOWN", "Tooling-related variable set on one side only", S.LOW,
         CL.POTENTIAL_RISK,
         "Variables such as PYTHONPATH, JAVA_HOME or proxy settings can change which "
         "files and networks tools use. Values are intentionally not recorded.",
         categories=_ENV, groups=_fs("presence"), names=frozenset(PRESENCE_VARS)),
    Rule("RM-ENV-PRESENCE", "Variable name set on one side only", S.INFO, CL.INFORMATIONAL,
         "Variable names were recorded by opt-in; presence alone says little.",
         categories=_ENV, groups=_fs("presence")),
    Rule("RM-EXTRA", "Present only in the target", S.INFO, CL.INFORMATIONAL,
         "The target has something the baseline lacks; this rarely explains a failure on the target.",
         kinds=_fs(K.EXTRA)),
    Rule("RM-DEFAULT", "Unclassified difference", S.INFO, CL.INFORMATIONAL,
         "No specific rule applies to this difference."),
)


def assess(diff: Difference, ctx: Context, rules: tuple[Rule, ...] = RULES) -> Assessment:
    """Return the assessment from the first matching rule."""
    for rule in rules:
        result = rule.evaluate(diff, ctx)
        if result is not None:
            return result
    raise LookupError("no rule matched and no default rule present")
