from envmirror.engine.versions import Delta, parse_version, version_delta
import pytest


@pytest.mark.parametrize(
    "a,b,expected",
    [("3.12.1", "3.12.1", Delta.NONE), ("3.12.1", "4.0.0", Delta.MAJOR),
     ("3.11.9", "3.12.0", Delta.MINOR), ("3.12.1", "3.12.4", Delta.PATCH),
     ("3.12.0", "3.12.0rc1", Delta.BUILD), ("weird", "3.1", Delta.UNPARSEABLE),
     ("20", "22", Delta.MAJOR), ("2.45", "2.45.0", Delta.BUILD)],
)
def test_version_delta(a, b, expected):
    assert version_delta(a, b) is expected


def test_java_legacy_numbering():
    assert version_delta("1.8.0_392", "17.0.9", java=True) is Delta.MAJOR
    assert version_delta("1.8.0_392", "8.0.392", java=True) is not Delta.MAJOR
    assert parse_version("1.8.0_392", java=True) == (8, 0, 0)


def test_simple_npm_specs():
    assert version_delta("^1.2.3", "^2.0.0", simple_spec=True) is Delta.MAJOR
    assert version_delta("^1.2.3", "~1.2.3", simple_spec=True) is Delta.BUILD


@pytest.mark.parametrize("spec", [">=1 <3", "workspace:*", "git+https://x/y.git", "latest", "1.x || 2.x"])
def test_complex_npm_specs_are_unparseable(spec):
    assert parse_version(spec, simple_spec=True) is None
    assert version_delta("^1.0.0", spec, simple_spec=True) is Delta.UNPARSEABLE
