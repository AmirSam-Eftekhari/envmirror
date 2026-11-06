from envmirror.scanner.environment import collect_environment
from envmirror.security.redaction import REDACTED

ENV = {
    "LANG": "en_US.UTF-8", "NODE_ENV": "production", "JAVA_HOME": "/home/alice/jdk",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "MY_APP_COLOR": "blue",
    "VIRTUAL_ENV": "/home/alice/venv", "USERNAME": "alice",
}


def test_defaults_record_only_allowlisted_values_and_presence():
    info = collect_environment(ENV)
    assert info.values == {"LANG": "en_US.UTF-8", "NODE_ENV": "production"}
    assert sorted(info.present) == ["JAVA_HOME", "VIRTUAL_ENV"]


def test_defaults_never_contain_other_variables_or_values():
    dumped = str(collect_environment(ENV).model_dump())
    for leaked in ("alice", "wJalr", "AWS_SECRET", "MY_APP_COLOR", "blue"):
        assert leaked not in dumped


def test_include_names_records_names_not_values():
    info = collect_environment(ENV, include_all_names=True)
    assert "MY_APP_COLOR" in info.present and "AWS_SECRET_ACCESS_KEY" in info.present
    assert "blue" not in str(info.model_dump())


def test_opt_in_value_recorded():
    assert collect_environment(ENV, include_values=["my_app_color"]).values["MY_APP_COLOR"] == "blue"


def test_opt_in_secret_named_value_is_always_redacted():
    info = collect_environment(ENV, include_values=["AWS_SECRET_ACCESS_KEY"])
    assert info.values["AWS_SECRET_ACCESS_KEY"] == REDACTED
    assert "wJalr" not in str(info.model_dump())


def test_opt_in_value_has_home_directory_scrubbed():
    info = collect_environment({"MY_DIR": "/home/alice/work"}, include_values=["MY_DIR"], home="/home/alice")
    assert info.values["MY_DIR"] == "~/work"


def test_names_are_case_insensitive_like_windows():
    assert "NODE_ENV" in collect_environment({"node_env": "dev"}).values


def test_output_is_sorted_for_determinism():
    info = collect_environment({"TZ": "UTC", "LANG": "C", "CI": "true"})
    assert list(info.values) == sorted(info.values)
