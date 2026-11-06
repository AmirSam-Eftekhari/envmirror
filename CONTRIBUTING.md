# Contributing

Thanks for helping. EnvMirror's priorities are, in order: privacy, correctness, determinism, simplicity.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check . && mypy && pytest
```

## Ground rules

- No network access, telemetry, shells (`shell=True`) or execution of anything read from a snapshot.
- Tests must be offline and deterministic. Mock external executables (see `tests/helpers.py`);
  never require Docker, Node, Java or Rust to be installed.
- New data in snapshots needs a privacy justification and redaction tests. Prefer presence over values.
- New risk rules go in `engine/risk.py` with a plain-language `reason` and a test in
  `tests/unit/test_risk.py`. Rules must not claim causality.
- Do not weaken assertions or skip tests to get CI green.

## Pull requests

Keep changes focused, update `CHANGELOG.md`, and describe how you verified the change.
