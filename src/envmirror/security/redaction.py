"""Secret redaction.

Redaction happens *before* data enters a snapshot, not only at report time.
These heuristics are best-effort: they reduce accidental leakage but cannot
prove that a value is free of secrets. See the Privacy section of the README.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

REDACTED = "[REDACTED]"

_SENSITIVE_SUBSTRINGS = (
    "secret",
    "token",
    "password",
    "passwd",
    "passphrase",
    "credential",
    "apikey",
    "privatekey",
    "accesskey",
    "auth",
    "cookie",
    "session",
    "signature",
    "bearer",
    "connectionstring",
)
_SENSITIVE_TOKENS = frozenset({"key", "keys", "pwd", "pass", "sig", "pat", "dsn"})

_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"[A-Za-z0-9+/=_-]{40,}"),
)
_URL_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+(?::[^/\s@]*)?@")

_MAX_VALUE_LENGTH = 256


def is_sensitive_name(name: str) -> bool:
    """Return True if a variable or key name looks like it holds a secret."""
    lowered = name.lower()
    compact = re.sub(r"[^a-z0-9]", "", lowered)
    if any(part in compact for part in _SENSITIVE_SUBSTRINGS):
        return True
    tokens = {t for t in re.split(r"[^a-z0-9]+", lowered) if t}
    # Also split camelCase / PascalCase names such as "githubToken" or "ApiKey".
    tokens.update(t.lower() for t in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", name))
    return bool(tokens & _SENSITIVE_TOKENS)


def redact_value(value: str) -> str:
    """Redact credential-looking substrings and truncate long values."""
    result = _URL_CREDENTIALS.sub(lambda m: f"{m.group(1)}{REDACTED}@", value)
    for pattern in _VALUE_PATTERNS:
        result = pattern.sub(REDACTED, result)
    if len(result) > _MAX_VALUE_LENGTH:
        result = result[:_MAX_VALUE_LENGTH] + "..."
    return result


def redact_home(value: str, home: str | None) -> str:
    """Replace a home-directory prefix with ``~`` so usernames do not leak."""
    if not home or len(home) < 2:
        return value
    normalized_home = home.rstrip("/\\")
    if not normalized_home:
        return value
    pattern = re.compile(re.escape(normalized_home), re.IGNORECASE)
    return pattern.sub("~", value)


def redact_mapping(values: Mapping[str, str]) -> dict[str, str]:
    """Redact a name/value mapping by name sensitivity and value patterns."""
    return {
        name: (REDACTED if is_sensitive_name(name) else redact_value(value))
        for name, value in values.items()
    }
