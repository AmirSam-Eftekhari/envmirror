from datetime import UTC, datetime

from envmirror.scanner import scan
from helpers import fake_runner, ok


def test_scan_builds_valid_snapshot_without_any_tools_installed(tmp_path):
    snap = scan(tmp_path, runner=fake_runner({}), env={})
    assert snap.runtimes["node"].status == "not_found"
    assert snap.runtimes["python"].status == "found"
    assert snap.tools["git"].status == "not_found"
    assert snap.packages.node is None
    assert snap.metadata.project_scanned is True


def test_scan_without_project_does_not_read_directories():
    snap = scan(None, runner=fake_runner({}), env={})
    assert snap.metadata.project_scanned is False and snap.packages.node is None


def test_scan_uses_detected_versions_and_fixed_timestamp(tmp_path):
    runner = fake_runner({"node": ok("v22.0.0"), "git": ok("git version 2.45.0")})
    snap = scan(tmp_path, runner=runner, env={}, now=datetime(2026, 11, 4, 12, 0, tzinfo=UTC))
    assert snap.runtimes["node"].version == "22.0.0"
    assert snap.tools["git"].version == "2.45.0"
    assert snap.created_at == "2026-11-04T12:00:00Z"


def test_scan_never_runs_package_manager_commands_beyond_version_probes(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"postinstall": "x"}}', encoding="utf-8")
    calls = []
    scan(tmp_path, runner=fake_runner({}, calls), env={})
    forbidden = {"install", "run", "ci", "exec", "npx"}
    assert all(not (forbidden & set(argv)) for argv in calls)


def test_progress_callback_receives_steps():
    steps = []
    scan(None, runner=fake_runner({}), env={}, progress=steps.append)
    assert len(steps) >= 4
