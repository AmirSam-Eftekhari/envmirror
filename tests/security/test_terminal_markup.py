import io

from rich.console import Console

from envmirror.engine import compare_snapshots
from envmirror.reporting.terminal import render_comparison, safe_text
from helpers import make_snapshot


def test_rich_markup_in_values_is_printed_literally_and_control_chars_neutralised():
    a = make_snapshot(packages={"python": {"[bold red]pkg[/]": "1.0.0"}})
    b = make_snapshot(packages={"python": {"[bold red]pkg[/]": "2.0.0"}})
    buffer = io.StringIO()
    console = Console(file=buffer, width=200, force_terminal=False, color_system=None)
    render_comparison(console, compare_snapshots(a, b), verbose=True)
    assert "[bold red]pkg[/]" in buffer.getvalue()


def test_safe_text_strips_escape_sequences():
    assert "\x1b" not in safe_text("a\x1b[31mred").plain
