from envmirror.security.redaction import (
    REDACTED, is_sensitive_name, redact_home, redact_mapping, redact_value,
)
import pytest


@pytest.mark.parametrize(
    "name",
    ["AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "db_password", "API_KEY", "ApiKey", "githubToken",
     "MY_PASSWD", "NPM_AUTH", "SESSION_ID", "PRIVATE_KEY", "ssh-key", "COOKIE", "DB_PWD",
     "AZURE_CLIENT_SECRET", "STRIPE-SECRET", "Authorization"],
)
def test_sensitive_names_detected(name):
    assert is_sensitive_name(name)


@pytest.mark.parametrize("name", ["PATH", "LANG", "NODE_ENV", "KEYBOARD_LAYOUT", "HOME", "TZ", "MONKEY"])
def test_ordinary_names_not_flagged(name):
    assert not is_sensitive_name(name)


@pytest.mark.parametrize(
    "value",
    ["ghp_" + "a" * 36, "github_pat_" + "B" * 40, "AKIAABCDEFGHIJKLMNOP", "sk-" + "x" * 30,
     "xoxb-1234567890-abcdefghij", "glpat-" + "z" * 20,
     "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk",
     "Bearer abcdefgh12345678", "-----BEGIN RSA PRIVATE KEY-----", "A" * 60],
)
def test_token_shaped_values_redacted(value):
    assert REDACTED in redact_value(f"prefix {value} suffix")
    assert value not in redact_value(f"prefix {value} suffix")


def test_url_credentials_redacted_but_host_kept():
    result = redact_value("https://alice:hunter2@registry.example.com/pkg")
    assert "hunter2" not in result and "alice" not in result
    assert "registry.example.com" in result


def test_plain_values_untouched():
    assert redact_value("en_US.UTF-8") == "en_US.UTF-8"
    assert redact_value("production") == "production"


def test_long_values_truncated():
    assert len(redact_value("a b " * 500)) < 300


def test_redact_mapping_uses_name_and_value_rules():
    out = redact_mapping({"DB_PASSWORD": "x", "NOTE": "ghp_" + "q" * 36, "LANG": "C"})
    assert out["DB_PASSWORD"] == REDACTED
    assert REDACTED in out["NOTE"]
    assert out["LANG"] == "C"


def test_redact_home_posix():
    assert redact_home("/home/alice/project", "/home/alice") == "~/project"


def test_redact_home_windows_paths_case_insensitive():
    assert redact_home(r"C:\Users\Alice\proj", r"C:\Users\Alice") == "~\\proj"
    assert redact_home(r"c:\users\alice\proj", r"C:\Users\Alice") == "~\\proj"


def test_redact_home_ignores_unusable_home():
    assert redact_home("/anything", "") == "/anything"
    assert redact_home("/anything", "/") == "/anything"
    assert redact_home("/anything", None) == "/anything"
