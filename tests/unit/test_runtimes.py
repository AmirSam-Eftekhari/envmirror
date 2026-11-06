import platform

from envmirror.scanner._proc import CommandResult
from envmirror.scanner.runtimes import detect, detect_runtimes, detect_tools
from helpers import fake_runner, ok


def test_node_version_parsed():
    det = detect("node", fake_runner({"node": ok("v22.0.0\n")}))
    assert (det.status, det.version) == ("found", "22.0.0")


def test_java_modern_version_from_stderr_style_output():
    out = 'openjdk version "21.0.2" 2024-01-16\nOpenJDK Runtime Environment (build 21.0.2+13)'
    assert detect("java", fake_runner({"java": ok(out)})).version == "21.0.2"


def test_java_legacy_version_scheme():
    out = 'java version "1.8.0_392"\nJava(TM) SE Runtime Environment'
    assert detect("java", fake_runner({"java": ok(out)})).version == "1.8.0_392"


def test_git_windows_suffix_is_stripped():
    det = detect("git", fake_runner({"git": ok("git version 2.45.0.windows.1")}))
    assert det.version == "2.45.0"


def test_docker_and_rustc_formats():
    runner = fake_runner(
        {
            "docker": ok("Docker version 26.1.0, build 9714adc"),
            "rustc": ok("rustc 1.78.0 (9b00956e5 2024-04-29)"),
        }
    )
    assert detect("docker", runner).version == "26.1.0"
    assert detect("rustc", runner).version == "1.78.0"


def test_missing_executable():
    assert detect("node", fake_runner({})).status == "not_found"


def test_malformed_output_is_error_without_raw_output():
    det = detect("node", fake_runner({"node": ok("SECRET-looking garbage")}))
    assert det.status == "error"
    assert "SECRET" not in (det.detail or "")


def test_nonzero_exit_is_error():
    det = detect("node", fake_runner({"node": ok("v22.0.0", returncode=1)}))
    assert det.status == "error"


def test_timeout_is_recorded():
    det = detect("npm", fake_runner({"npm": CommandResult("timeout")}))
    assert det.status == "timeout"


def test_scan_survives_when_nothing_is_installed():
    runtimes = detect_runtimes(fake_runner({}))
    tools = detect_tools(fake_runner({}))
    assert runtimes["python"].version == platform.python_version()
    assert runtimes["node"].status == "not_found"
    assert tools["docker"].status == "not_found"


def test_runner_receives_fixed_argv_only():
    calls = []
    detect_runtimes(fake_runner({}, calls))
    detect_tools(fake_runner({}, calls))
    assert all(len(argv) <= 2 for argv in calls)
    assert {argv[0] for argv in calls} == {"node", "npm", "java", "rustc", "git", "docker"}
