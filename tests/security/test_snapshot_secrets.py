"""End-to-end: secrets must not reach the serialized snapshot."""

import json

from envmirror.scanner import scan
from helpers import fake_runner, ok

SECRETS = {
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI-K7MDENG-bPxRfiCYEXAMPLEKEY",
    "GITHUB_TOKEN": "ghp_" + "s" * 36,
    "DATABASE_URL": "postgres://admin:topsecretpw@db.internal/app",
    "NPM_TOKEN": "npm_" + "t" * 36,
    "USERNAME": "alice",
}
ENV = {**SECRETS, "LANG": "en_US.UTF-8", "NODE_ENV": "production"}


def _scan(tmp_path, **kwargs):
    return scan(tmp_path, runner=fake_runner({"git": ok("git version 2.45.0")}), env=ENV, **kwargs).to_json()


def test_default_scan_contains_no_secret_values(tmp_path):
    text = _scan(tmp_path)
    for value in SECRETS.values():
        assert value not in text


def test_default_scan_contains_no_secret_variable_names(tmp_path):
    text = _scan(tmp_path)
    for name in SECRETS:
        assert name not in text


def test_opt_in_values_still_redact_secrets(tmp_path):
    secret_names = [name for name in SECRETS if name != "USERNAME"]
    text = _scan(tmp_path, include_env_values=secret_names, include_all_env_names=True)
    for name, value in SECRETS.items():
        if name == "USERNAME":
            continue
        assert value not in text
    assert "[REDACTED]" in text


def test_package_json_secrets_do_not_reach_snapshot(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"p": "git+https://bob:pw12345@example.com/p.git"}}), encoding="utf-8"
    )
    assert "pw12345" not in _scan(tmp_path)


def test_snapshot_has_no_hostname_username_or_home(tmp_path):
    import getpass
    import os
    import platform

    text = _scan(tmp_path)
    for personal in {platform.node(), os.path.expanduser("~")}:
        if len(personal) > 3:
            assert personal not in text
    user = getpass.getuser()
    if len(user) > 3:
        assert f'"{user}"' not in text
