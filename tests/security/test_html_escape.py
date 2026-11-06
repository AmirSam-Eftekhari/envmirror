import re
from html.parser import HTMLParser

from envmirror.engine import compare_snapshots
from envmirror.reporting.html_report import render_html
from helpers import make_snapshot

XSS = '<script>alert(1)</script>'
ATTR = '"><img src=x onerror=alert(2)>'


def _render(label_a="a.json", label_b="b.json"):
    a = make_snapshot(packages={"python": {XSS: "1.0.0"}}, system={"os_release": ATTR})
    b = make_snapshot(
        packages={"python": {XSS: ATTR}},
        system={"os_release": "<b>x</b>", "platform": "Linux"},
        metadata={"scan_warnings": [XSS]},
        environment={"values": {"LANG": ATTR}},
    )
    result = compare_snapshots(a, b, baseline_label=label_a, target_label=label_b)
    return render_html(result, a, b)


def test_untrusted_values_are_escaped():
    html = _render()
    assert XSS not in html
    assert ATTR not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>x</b>" not in html


def test_untrusted_labels_are_escaped():
    html = _render(label_a=XSS, label_b=ATTR)
    assert XSS not in html and ATTR not in html


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(name for name, _ in attrs)


def test_report_markup_has_no_scripts_images_or_event_handler_attributes():
    parser = _TagCollector()
    parser.feed(_render())
    assert "script" not in parser.tags and "img" not in parser.tags
    assert not [a for a in parser.attrs if a.startswith("on")]


def test_report_loads_no_external_resources():
    html = _render()
    assert not re.search(r"(?:src|href)\s*=\s*[\"']?(?:https?:)?//", html, re.IGNORECASE)
    assert "@import" not in html and "url(" not in html
    assert "default-src 'none'" in html


def test_empty_comparison_renders():
    a = make_snapshot()
    html = render_html(compare_snapshots(a, a), a, a)
    assert "No differences were found." in html


def test_report_is_deterministic():
    assert _render() == _render()
