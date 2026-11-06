import subprocess
import sys

from envmirror.scanner import _proc
from envmirror.scanner._proc import run_command


def test_missing_executable_is_not_found():
    assert run_command(["definitely-not-a-real-executable-envmirror"]).status == "not_found"


def test_empty_argv_is_error():
    assert run_command([]).status == "error"


def test_captures_output_and_exit_code():
    result = run_command([sys.executable, "-c", "print('hello world')"])
    assert result.status == "ok"
    assert result.output.strip() == "hello world"
    assert result.returncode == 0


def test_nonzero_exit_is_reported_not_raised():
    result = run_command([sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"])
    assert result.status == "ok"
    assert result.returncode == 3


def test_timeout_kills_process():
    result = run_command([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)
    assert result.status == "timeout"


def test_output_is_bounded():
    result = run_command(
        [sys.executable, "-c", "print('x' * 200000)"], max_output=1000, timeout=10
    )
    assert result.truncated
    assert len(result.output) <= 1000


def test_undecodable_output_does_not_crash():
    code = "import sys; sys.stdout.buffer.write(b'\\xff\\xfe v1.2.3')"
    result = run_command([sys.executable, "-c", code])
    assert result.status == "ok"
    assert "1.2.3" in result.output


def test_never_uses_shell_and_passes_argv_list(monkeypatch):
    seen = {}
    real_popen = subprocess.Popen

    def spy(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return real_popen(args, **kwargs)

    monkeypatch.setattr(_proc.subprocess, "Popen", spy)
    run_command([sys.executable, "-c", "print(1)"])
    assert isinstance(seen["args"], list)
    assert not seen["kwargs"].get("shell", False)


def test_arguments_with_spaces_are_passed_intact():
    result = run_command([sys.executable, "-c", "import sys; print(sys.argv[1])", "a b  c"])
    assert result.output.strip() == "a b  c"
