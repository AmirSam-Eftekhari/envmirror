from envmirror.models.snapshot import SystemInfo
from envmirror.scanner.system import collect_system, normalize_architecture
import pytest


@pytest.mark.parametrize(
    "raw,expected",
    [("AMD64", "x86_64"), ("x86_64", "x86_64"), ("aarch64", "arm64"), ("ARM64", "arm64"),
     ("i686", "x86"), ("riscv64", "riscv64"), ("", "unknown")],
)
def test_architecture_normalization(raw, expected):
    assert normalize_architecture(raw) == expected


def test_collect_system_has_core_fields_and_no_python_path():
    info = collect_system()
    assert info.platform and info.architecture
    assert "python_executable" not in SystemInfo.model_fields
