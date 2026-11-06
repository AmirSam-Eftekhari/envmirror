"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def machine_a(fixtures_dir: Path) -> Path:
    return fixtures_dir / "machine-a.json"


@pytest.fixture
def machine_b(fixtures_dir: Path) -> Path:
    return fixtures_dir / "machine-b.json"
