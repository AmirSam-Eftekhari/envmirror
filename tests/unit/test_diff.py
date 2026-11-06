from envmirror.engine import compare_snapshots
from envmirror.engine.diff import Kind, compare_differences
from envmirror.models.comparison import Category, Severity
from helpers import found, make_snapshot


def by_field(snapshot_a, snapshot_b):
    return {d.field: d for d in compare_differences(snapshot_a, snapshot_b)}


def test_identical_snapshots_have_no_differences():
    assert compare_differences(make_snapshot(), make_snapshot()) == []
    assert compare_snapshots(make_snapshot(), make_snapshot()).findings == []


def test_architecture_and_os_differences():
    b = make_snapshot(system={"platform": "Windows", "architecture": "arm64", "os_release": "11"})
    diffs = by_field(make_snapshot(), b)
    assert diffs["system.architecture"].expected == "x86_64"
    assert diffs["system.architecture"].actual == "arm64"
    assert "system.platform" in diffs
    # release/version are meaningless across operating systems and are not reported
    assert "system.os_release" not in diffs


def test_os_release_reported_when_platform_matches():
    diffs = by_field(make_snapshot(), make_snapshot(system={"os_release": "6.9.0"}))
    assert "system.os_release" in diffs


def test_runtime_version_changed_missing_and_extra():
    a = make_snapshot()
    b = make_snapshot(
        runtimes={"node": found("20.11.0"), "npm": {"status": "not_found", "version": None},
                  "java": found("21.0.2")}
    )
    diffs = by_field(a, b)
    assert diffs["runtimes.node"].kind is Kind.CHANGED
    assert diffs["runtimes.npm"].kind is Kind.MISSING
    assert diffs["runtimes.java"].kind is Kind.EXTRA
    assert "runtimes.rustc" not in diffs  # missing on both sides: nothing to report


def test_tool_missing():
    b = make_snapshot(tools={"git": {"status": "not_found", "version": None}})
    assert by_field(make_snapshot(), b)["tools.git"].kind is Kind.MISSING


def test_probe_failure_is_indeterminate_not_missing():
    b = make_snapshot(runtimes={"node": {"status": "timeout", "version": None}})
    diff = by_field(make_snapshot(), b)["runtimes.node"]
    assert diff.kind is Kind.INDETERMINATE


def test_python_packages():
    b = make_snapshot(packages={"python": {"requests": "3.0.0", "numpy": "2.0.0"}})
    b.packages.python.pop("pytest")
    diffs = by_field(make_snapshot(), b)
    assert diffs["packages.python.requests"].kind is Kind.CHANGED
    assert diffs["packages.python.pytest"].kind is Kind.MISSING
    assert diffs["packages.python.numpy"].kind is Kind.EXTRA


NODE_A = {"package_manager": "pnpm@9.1.0", "dependencies": {"react": "^18.2.0", "zod": "^3.0.0"},
          "dev_dependencies": {"vitest": "^1.0.0"}, "engines": {"node": ">=20"},
          "lockfiles": ["pnpm-lock.yaml"]}


def test_node_project_on_one_side_only_is_single_indeterminate_finding():
    diffs = compare_differences(make_snapshot(packages={"node": NODE_A}), make_snapshot())
    node = [d for d in diffs if d.category is Category.NODE_PACKAGE]
    assert len(node) == 1 and node[0].kind is Kind.INDETERMINATE


def test_node_project_both_sides():
    other = {"package_manager": "yarn@1.22.0", "dependencies": {"react": "^17.0.0"},
             "dev_dependencies": {}, "engines": {"node": ">=18"}, "lockfiles": []}
    a = make_snapshot(packages={"node": NODE_A})
    b = make_snapshot(packages={"node": other})
    diffs = {d.field: d for d in compare_differences(a, b)}
    assert diffs["packages.node.dependencies.react"].kind is Kind.CHANGED
    assert diffs["packages.node.dependencies.zod"].kind is Kind.MISSING
    assert diffs["packages.node.dev_dependencies.vitest"].group == "dev_dependencies"
    assert diffs["packages.node.package_manager"].kind is Kind.CHANGED
    assert diffs["packages.node.lockfiles.pnpm-lock.yaml"].kind is Kind.MISSING
    assert diffs["packages.node.engines.node"].kind is Kind.CHANGED


def test_environment_differences_skip_redacted_values():
    a = make_snapshot(environment={"values": {"LANG": "en_US.UTF-8", "TOKEN_X": "[REDACTED]"},
                                   "present": ["JAVA_HOME"]})
    b = make_snapshot(environment={"values": {"LANG": "C.UTF-8", "TOKEN_X": "[REDACTED]"},
                                   "present": []})
    diffs = by_field(a, b)
    assert diffs["environment.values.LANG"].kind is Kind.CHANGED
    assert diffs["environment.JAVA_HOME"].kind is Kind.MISSING
    assert "environment.values.TOKEN_X" not in diffs


def test_comparison_is_deterministic_and_sorted():
    a = make_snapshot()
    b = make_snapshot(system={"architecture": "arm64"}, runtimes={"node": found("18.0.0")},
                      packages={"python": {"requests": "1.0.0"}})
    first = compare_snapshots(a, b).model_dump(mode="json")
    second = compare_snapshots(a, b).model_dump(mode="json")
    assert first == second
    severities = [f["severity"] for f in first["findings"]]
    order = ["critical", "high", "medium", "low", "info"]
    assert severities == sorted(severities, key=order.index)
    ids = [f["id"] for f in first["findings"]]
    assert len(ids) == len(set(ids))


def test_every_finding_has_required_content():
    a = make_snapshot()
    b = make_snapshot(system={"architecture": "arm64"}, runtimes={"node": found("18.0.0")})
    for finding in compare_snapshots(a, b).findings:
        assert finding.id and finding.field and finding.explanation and finding.suggested_action
        assert finding.severity in set(Severity)


def test_summary_counts_add_up():
    b = make_snapshot(system={"architecture": "arm64"}, runtimes={"node": found("18.0.0")})
    result = compare_snapshots(make_snapshot(), b)
    assert sum(result.summary.by_severity.values()) == result.summary.total == len(result.findings)
    assert sum(result.summary.by_category.values()) == result.summary.total
