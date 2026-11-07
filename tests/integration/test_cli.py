"""CLI tests. Require Typer and Rich. All external executables are mocked."""

import json

from typer.testing import CliRunner

from envmirror.cli import FailOn, OutputFormat, app
from envmirror.scanner._proc import CommandResult
from helpers import ok

runner = CliRunner()


def _fake_run_command(versions):
    def run(argv, **_kwargs):
        text = versions.get(argv[0])
        return ok(text) if text else CommandResult("not_found")

    return run


def _patch_tools(monkeypatch, **versions):
    monkeypatch.setattr("envmirror.scanner.run_command", _fake_run_command(versions))


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("scan", "compare", "inspect", "validate"):
        assert command in result.stdout


def test_no_arguments_shows_help():
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0 and "envmirror 0.1.0" in result.stdout


def test_scan_writes_valid_snapshot_and_validate_accepts_it(tmp_path, monkeypatch):
    _patch_tools(monkeypatch, node="v22.0.0", git="git version 2.45.0")
    out = tmp_path / "dir with spaces" / "machine a.json"
    out.parent.mkdir()
    result = runner.invoke(app, ["scan", "--no-project", "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text(encoding="utf-8"))["runtimes"]["node"]["version"] == "22.0.0"
    assert runner.invoke(app, ["validate", str(out)]).exit_code == 0


def test_scan_json_format_emits_only_json_on_stdout(monkeypatch):
    _patch_tools(monkeypatch)
    result = runner.invoke(app, ["scan", "--no-project", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["schema_version"] == "1.0"


def test_scan_with_project_reads_package_json(tmp_path, monkeypatch):
    _patch_tools(monkeypatch)
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}', encoding="utf-8")
    result = runner.invoke(app, ["scan", "--project", str(tmp_path), "--format", "json"])
    assert json.loads(result.stdout)["packages"]["node"]["dependencies"] == {"react": "^18.0.0"}


def test_scan_invalid_project_is_usage_error(tmp_path):
    result = runner.invoke(app, ["scan", "--project", str(tmp_path / "missing")])
    assert result.exit_code == 2


def test_scan_output_in_missing_directory_exits_4(tmp_path, monkeypatch):
    _patch_tools(monkeypatch)
    result = runner.invoke(app, ["scan", "--no-project", "-o", str(tmp_path / "nope" / "x.json")])
    assert result.exit_code == 4


def test_quiet_and_verbose_conflict():
    assert runner.invoke(app, ["-q", "-v", "scan"]).exit_code == 2


def test_compare_identical_exits_zero(machine_a):
    result = runner.invoke(app, ["compare", str(machine_a), str(machine_a)])
    assert result.exit_code == 0
    assert "No differences" in result.stdout


def test_compare_different_exits_one_by_default(machine_a, machine_b):
    assert runner.invoke(app, ["compare", str(machine_a), str(machine_b)]).exit_code == 1


def test_fail_on_none_always_zero(machine_a, machine_b):
    assert runner.invoke(app, ["compare", str(machine_a), str(machine_b), "--fail-on", "none"]).exit_code == 0


def test_fail_on_critical_ignores_lower_severities(machine_a, machine_b):
    assert runner.invoke(app, ["compare", str(machine_a), str(machine_b), "--fail-on", "critical"]).exit_code == 0


def test_compare_json_stdout_is_pure_json(machine_a, machine_b):
    result = runner.invoke(app, ["compare", str(machine_a), str(machine_b), "--format", "json", "--fail-on", "none"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["summary"]["total"] == len(data["findings"]) > 0


def test_compare_writes_html_report(tmp_path, machine_a, machine_b):
    report = tmp_path / "my report.html"
    result = runner.invoke(app, ["compare", str(machine_a), str(machine_b), "--html", str(report), "--fail-on", "none"])
    assert result.exit_code == 0
    assert "<!DOCTYPE html>" in report.read_text(encoding="utf-8")


def test_compare_missing_file_exits_3(tmp_path, machine_a):
    result = runner.invoke(app, ["compare", str(machine_a), str(tmp_path / "nope.json")])
    assert result.exit_code == 3


def test_compare_malformed_json_exits_3(tmp_path, machine_a):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert runner.invoke(app, ["compare", str(machine_a), str(bad)]).exit_code == 3


def test_quiet_compare_prints_nothing_but_keeps_exit_code(machine_a, machine_b):
    result = runner.invoke(app, ["-q", "compare", str(machine_a), str(machine_b)])
    assert result.exit_code == 1 and result.stdout.strip() == ""


def test_verbose_compare_includes_explanations(machine_a, machine_b):
    result = runner.invoke(app, ["-v", "compare", str(machine_a), str(machine_b), "--fail-on", "none"])
    assert "Next step:" in result.stdout


def test_inspect_text_and_json(machine_a):
    assert "snapshot" in runner.invoke(app, ["inspect", str(machine_a)]).stdout.lower()
    data = json.loads(runner.invoke(app, ["inspect", str(machine_a), "--format", "json"]).stdout)
    assert data["system"]["platform"] == "Linux"


def test_validate_rejects_invalid_snapshot(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert runner.invoke(app, ["validate", str(bad)]).exit_code == 3
    as_json = runner.invoke(app, ["validate", str(bad), "--format", "json"])
    assert json.loads(as_json.stdout)["valid"] is False


def test_cli_enums_behave_like_their_string_values():
    assert str(OutputFormat.json) == "json" and OutputFormat("text") is OutputFormat.text
    assert [m.value for m in FailOn] == ["critical", "high", "medium", "low", "info", "none"]


def test_unknown_enum_option_values_are_usage_errors(machine_a):
    for option, bad in (("--format", "yaml"), ("--fail-on", "urgent")):
        result = runner.invoke(app, ["compare", str(machine_a), str(machine_a), option, bad])
        assert result.exit_code == 2, option


def test_enum_options_accept_every_documented_value(machine_a):
    for value in ("critical", "high", "medium", "low", "info", "none"):
        result = runner.invoke(app, ["compare", str(machine_a), str(machine_a), "--fail-on", value])
        assert result.exit_code == 0, value
    assert runner.invoke(app, ["inspect", str(machine_a), "--format", "text"]).exit_code == 0
