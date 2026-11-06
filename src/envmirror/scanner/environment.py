"""Environment configuration metadata.

Defaults are deliberately narrow: values are recorded only for a short
allow-list of non-sensitive variables; a few more are recorded as *presence
only*. Anything else requires explicit opt-in.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..models.snapshot import EnvironmentInfo
from ..security.redaction import REDACTED, is_sensitive_name, redact_home, redact_value

# Values recorded by default (not path-like, not secret-bearing).
SAFE_VALUE_VARS = frozenset(
    {"LANG", "LC_ALL", "TZ", "NODE_ENV", "PYTHONUTF8", "PYTHONIOENCODING", "CI"}
)
# Presence recorded, value never stored (may hold paths, names or credentials).
PRESENCE_VARS = frozenset(
    {
        "VIRTUAL_ENV",
        "CONDA_DEFAULT_ENV",
        "PYTHONPATH",
        "PYTHONHOME",
        "NODE_PATH",
        "JAVA_HOME",
        "CARGO_HOME",
        "RUSTUP_HOME",
        "DOCKER_HOST",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    }
)


def collect_environment(
    env: Mapping[str, str],
    *,
    include_all_names: bool = False,
    include_values: Iterable[str] = (),
    home: str | None = None,
) -> EnvironmentInfo:
    """Build environment metadata from ``env`` (injected for testability).

    ``include_all_names`` records the *names* of every variable (never values).
    ``include_values`` records values for the named variables only, after
    redaction; variables with sensitive-looking names are always redacted.
    """
    upper = {name.upper(): value for name, value in env.items()}
    values: dict[str, str] = {}
    present: set[str] = set()

    for name in SAFE_VALUE_VARS:
        if name in upper:
            values[name] = redact_value(upper[name])
    for name in PRESENCE_VARS:
        if name in upper:
            present.add(name)
    if include_all_names:
        present.update(name.upper() for name in env if not _has_control_chars(name))
    for requested in include_values:
        name = requested.strip().upper()
        if not name or name not in upper:
            continue
        if is_sensitive_name(name):
            values[name] = REDACTED
        else:
            values[name] = redact_value(redact_home(upper[name], home))
    return EnvironmentInfo(
        values=dict(sorted(values.items())), present=sorted(present - set(values))
    )


def _has_control_chars(text: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text) or len(text) > 256
