"""Scan -> file -> compare -> reports, without the CLI layer."""

import json

from envmirror.engine import compare_snapshots
from envmirror.reporting.html_report import render_html
from envmirror.reporting.json_report import comparison_to_json
from envmirror.scanner import scan
from envmirror.snapshot_io import read_snapshot, write_text_atomic
from helpers import fake_runner, ok


def test_full_pipeline_on_paths_with_spaces(tmp_path):
    folder = tmp_path / "My Machines"
    folder.mkdir()
    a_path, b_path = folder / "machine a.json", folder / "machine b.json"
    write_text_atomic(a_path, scan(None, runner=fake_runner({"node": ok("v22.0.0")}), env={}).to_json())
    write_text_atomic(b_path, scan(None, runner=fake_runner({"node": ok("v18.19.0")}), env={}).to_json())
    a, _ = read_snapshot(a_path)
    b, _ = read_snapshot(b_path)
    result = compare_snapshots(a, b, baseline_label=a_path.name, target_label=b_path.name)
    ids = [f.id for f in result.findings]
    assert "RM-RUNTIME-MAJOR:runtimes.node" in ids
    data = json.loads(comparison_to_json(result))
    assert data["baseline"]["label"] == "machine a.json"
    html = render_html(result, a, b)
    write_text_atomic(folder / "report.html", html)
    assert "RM-RUNTIME-MAJOR" in (folder / "report.html").read_text(encoding="utf-8")


def test_example_snapshots_round_trip_and_compare(machine_a, machine_b):
    a, a_warn = read_snapshot(machine_a)
    b, b_warn = read_snapshot(machine_b)
    assert a_warn == [] and b_warn == []
    assert a.to_json() == machine_a.read_text(encoding="utf-8")
    result = compare_snapshots(a, b, baseline_label="machine-a.json", target_label="machine-b.json")
    by_id = {f.id: f for f in result.findings}
    expected = {
        "RM-ARCH:system.architecture": "high",
        "RM-RUNTIME-MAJOR:runtimes.node": "high",
        "RM-RUNTIME-MINOR:runtimes.python": "medium",
        "RM-RUNTIME-MISSING:runtimes.java": "high",
        "RM-TOOL-MISSING:tools.docker": "medium",
        "RM-PYPKG-MAJOR:packages.python.pydantic": "high",
        "RM-PYPKG-MISSING:packages.python.rich": "medium",
        "RM-NODEDEP-MAJOR:packages.node.dependencies.next": "high",
        "RM-NODEDEP-MISSING:packages.node.dependencies.zod": "high",
        "RM-LOCKFILE-MISSING:packages.node.lockfiles.pnpm-lock.yaml": "medium",
        "RM-ENV-NODE-ENV:environment.values.NODE_ENV": "medium",
    }
    for finding_id, severity in expected.items():
        assert by_id[finding_id].severity.value == severity, finding_id
    assert not any(f.severity.value == "critical" for f in result.findings)
