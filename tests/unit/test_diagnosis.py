from envmirror.engine.diagnosis import describe, suggest
from envmirror.engine.diff import Difference, Kind
from envmirror.models.comparison import Category
import pytest


@pytest.mark.parametrize("category", list(Category))
@pytest.mark.parametrize("kind", list(Kind))
def test_every_category_and_kind_has_description_and_action(category, kind):
    diff = Difference(category, "f.x", "x", kind, "1.0", "2.0")
    assert describe(diff).endswith(".")
    assert len(suggest(diff)) > 10


def test_describe_mentions_both_values():
    diff = Difference(Category.RUNTIME, "runtimes.node", "node", Kind.CHANGED, "22.0.0", "18.2.0")
    text = describe(diff)
    assert "22.0.0" in text and "18.2.0" in text and "node" in text
