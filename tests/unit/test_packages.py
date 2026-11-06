import json

from envmirror.scanner.packages import (
    collect_node_project,
    collect_python_packages,
    normalize_name,
)
import pytest


class FakeDist:
    def __init__(self, name, version):
        self.metadata = {"Name": name} if name else {}
        self.version = version


@pytest.mark.parametrize(
    "raw,expected",
    [("Requests", "requests"), ("typing_extensions", "typing-extensions"),
     ("zope.interface", "zope-interface"), ("A__b--c..d", "a-b-c-d")],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_python_packages_normalized_sorted_and_deduplicated(monkeypatch):
    dists = [FakeDist("Typing_Extensions", "4.9.0"), FakeDist("requests", "2.31.0"),
             FakeDist("Requests", "2.32.0"), FakeDist(None, "1.0"), FakeDist("broken", "")]
    monkeypatch.setattr("importlib.metadata.distributions", lambda: dists)
    packages = collect_python_packages()
    assert packages == {"requests": "2.32.0", "typing-extensions": "4.9.0"}
    assert list(packages) == sorted(packages)


def test_collect_real_python_packages_does_not_crash():
    assert isinstance(collect_python_packages(), dict)


def _write_pkg(tmp_path, data):
    (tmp_path / "package.json").write_text(json.dumps(data), encoding="utf-8")


def test_node_project_parsed(tmp_path):
    _write_pkg(tmp_path, {
        "dependencies": {"react": "^18.2.0"},
        "devDependencies": {"vitest": "~1.6.0"},
        "engines": {"node": ">=20"},
        "packageManager": "pnpm@9.1.0",
    })
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9", encoding="utf-8")
    project, warnings = collect_node_project(tmp_path)
    assert project is not None
    assert project.dependencies == {"react": "^18.2.0"}
    assert project.dev_dependencies == {"vitest": "~1.6.0"}
    assert project.package_manager == "pnpm@9.1.0"
    assert project.lockfiles == ["pnpm-lock.yaml"]
    assert warnings == []


def test_missing_lockfile_warns(tmp_path):
    _write_pkg(tmp_path, {"dependencies": {"a": "1.0.0"}})
    project, warnings = collect_node_project(tmp_path)
    assert project is not None and project.lockfiles == []
    assert any("lockfile" in w.lower() for w in warnings)


def test_no_package_json_returns_none(tmp_path):
    assert collect_node_project(tmp_path) == (None, [])


@pytest.mark.parametrize("content", ["{not json", "[]", "\"text\"", ""])
def test_malformed_package_json_is_skipped(tmp_path, content):
    (tmp_path / "package.json").write_text(content, encoding="utf-8")
    project, warnings = collect_node_project(tmp_path)
    assert project is None and warnings


def test_oversized_package_json_is_skipped(tmp_path, monkeypatch):
    _write_pkg(tmp_path, {"dependencies": {"a": "1.0.0"}})
    monkeypatch.setattr("envmirror.scanner.packages.MAX_PACKAGE_JSON_BYTES", 5)
    project, warnings = collect_node_project(tmp_path)
    assert project is None and warnings


def test_non_string_dependency_entries_are_dropped(tmp_path):
    _write_pkg(tmp_path, {"dependencies": {"ok": "1.0.0", "bad": 5, "worse": None}})
    project, _ = collect_node_project(tmp_path)
    assert project.dependencies == {"ok": "1.0.0"}


def test_credentials_in_dependency_specs_are_redacted(tmp_path):
    _write_pkg(tmp_path, {"dependencies": {"private": "git+https://user:s3cretpass@example.com/r.git"}})
    project, _ = collect_node_project(tmp_path)
    assert "s3cretpass" not in project.dependencies["private"]


def test_home_directory_in_file_spec_is_scrubbed(tmp_path):
    _write_pkg(tmp_path, {"dependencies": {"local": "file:/home/alice/code/lib"}})
    project, _ = collect_node_project(tmp_path, home="/home/alice")
    assert "alice" not in project.dependencies["local"]


def test_package_scripts_are_never_read_or_executed(tmp_path):
    _write_pkg(tmp_path, {"scripts": {"preinstall": "touch pwned"}, "dependencies": {}})
    collect_node_project(tmp_path)
    assert not (tmp_path / "pwned").exists()


def test_project_path_with_spaces(tmp_path):
    folder = tmp_path / "My Project (v2)"
    folder.mkdir()
    _write_pkg(folder, {"dependencies": {"a": "1.0.0"}})
    project, _ = collect_node_project(folder)
    assert project is not None
