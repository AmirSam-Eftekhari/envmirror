import tomllib
from pathlib import Path

import envmirror

ROOT = Path(__file__).resolve().parents[2]


def test_version_matches_pyproject():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == envmirror.__version__


def test_template_ships_inside_the_package():
    assert (Path(envmirror.__file__).parent / "templates" / "report.html.j2").is_file()


def test_console_script_target_exists():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["envmirror"] == "envmirror.cli:app"
