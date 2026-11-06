# Changelog

All notable changes are documented here. Format based on Keep a Changelog; versioning follows SemVer.

## [0.1.0] - Unreleased

### Added
- `scan`, `compare`, `inspect` and `validate` commands with exit codes, quiet/verbose and JSON modes.
- Versioned snapshot schema 1.0 with strict validation and deterministic serialization.
- Scanners for system info, Python/Node/npm/Java/rustc runtimes, Git/Docker, Python packages,
  `package.json`, and allow-listed environment metadata.
- Rule-based risk engine with stable finding ids and cautious explanations.
- Self-contained dark HTML report (no JavaScript, no external resources).
- Secret redaction before serialization; opt-in environment names/values.
