from envmirror.engine.diff import Difference, Kind
from envmirror.engine.risk import RULES, Context, Rule, assess
from envmirror.engine.versions import Delta
from envmirror.models.comparison import Category, Classification, Severity
import pytest

C, K, D = Category, Kind, Delta


def diff(category, kind, delta=Delta.NONE, *, name="x", group="", field=None, exp="1", act="2"):
    return Difference(category, field or f"{category.value}.{name}", name, kind, exp, act, delta, group)


@pytest.mark.parametrize(
    "difference,severity,classification",
    [
        (diff(C.SYSTEM, K.CHANGED, name="architecture", field="system.architecture"), Severity.HIGH, Classification.POTENTIAL_RISK),
        (diff(C.SYSTEM, K.CHANGED, name="platform", field="system.platform"), Severity.INFO, Classification.INFORMATIONAL),
        (diff(C.SYSTEM, K.CHANGED, name="os_release", field="system.os_release"), Severity.INFO, Classification.INFORMATIONAL),
        (diff(C.RUNTIME, K.CHANGED, D.MAJOR, name="node"), Severity.HIGH, Classification.POTENTIAL_RISK),
        (diff(C.RUNTIME, K.CHANGED, D.MINOR, name="node"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.RUNTIME, K.CHANGED, D.PATCH, name="node"), Severity.LOW, Classification.POTENTIAL_RISK),
        (diff(C.RUNTIME, K.CHANGED, D.BUILD, name="python"), Severity.INFO, Classification.INFORMATIONAL),
        (diff(C.RUNTIME, K.MISSING, name="java"), Severity.HIGH, Classification.CONFIRMED),
        (diff(C.RUNTIME, K.INDETERMINATE, name="node"), Severity.LOW, Classification.INFORMATIONAL),
        (diff(C.TOOL, K.MISSING, name="git"), Severity.MEDIUM, Classification.CONFIRMED),
        (diff(C.TOOL, K.CHANGED, D.MAJOR, name="docker"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.TOOL, K.CHANGED, D.PATCH, name="git"), Severity.LOW, Classification.INFORMATIONAL),
        (diff(C.PYTHON_PACKAGE, K.MISSING), Severity.MEDIUM, Classification.CONFIRMED),
        (diff(C.PYTHON_PACKAGE, K.CHANGED, D.MAJOR), Severity.HIGH, Classification.POTENTIAL_RISK),
        (diff(C.PYTHON_PACKAGE, K.CHANGED, D.PATCH), Severity.LOW, Classification.POTENTIAL_RISK),
        (diff(C.PYTHON_PACKAGE, K.EXTRA), Severity.INFO, Classification.INFORMATIONAL),
        (diff(C.NODE_PACKAGE, K.MISSING, group="dependencies"), Severity.HIGH, Classification.CONFIRMED),
        (diff(C.NODE_PACKAGE, K.MISSING, group="dev_dependencies"), Severity.MEDIUM, Classification.CONFIRMED),
        (diff(C.NODE_PACKAGE, K.CHANGED, D.MAJOR, group="dependencies"), Severity.HIGH, Classification.POTENTIAL_RISK),
        (diff(C.NODE_PACKAGE, K.CHANGED, D.MAJOR, group="dev_dependencies"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.NODE_PACKAGE, K.CHANGED, D.UNPARSEABLE, group="dependencies"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.NODE_PACKAGE, K.MISSING, group="lockfile"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.NODE_PACKAGE, K.CHANGED, D.MAJOR, group="package_manager"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.NODE_PACKAGE, K.INDETERMINATE, group="project"), Severity.INFO, Classification.INFORMATIONAL),
        (diff(C.ENVIRONMENT, K.CHANGED, name="NODE_ENV", group="value"), Severity.MEDIUM, Classification.POTENTIAL_RISK),
        (diff(C.ENVIRONMENT, K.CHANGED, name="LANG", group="value"), Severity.LOW, Classification.POTENTIAL_RISK),
        (diff(C.ENVIRONMENT, K.MISSING, name="JAVA_HOME", group="presence"), Severity.LOW, Classification.POTENTIAL_RISK),
        (diff(C.ENVIRONMENT, K.MISSING, name="MY_VAR", group="presence"), Severity.INFO, Classification.INFORMATIONAL),
    ],
)
def test_rule_classification(difference, severity, classification):
    result = assess(difference, Context())
    assert (result.severity, result.classification) == (severity, classification), result.rule_id


def test_critical_requires_node_project_context():
    missing_node = diff(C.RUNTIME, K.MISSING, name="node")
    assert assess(missing_node, Context(baseline_uses_node=True)).severity is Severity.CRITICAL
    assert assess(missing_node, Context(baseline_uses_node=False)).severity is Severity.HIGH


def test_rules_can_be_evaluated_independently():
    rule = Rule("T-1", "demo", Severity.LOW, Classification.INFORMATIONAL, "because",
                categories=frozenset({C.TOOL}), kinds=frozenset({K.MISSING}))
    assert rule.evaluate(diff(C.TOOL, K.MISSING), Context()).rule_id == "T-1"
    assert rule.evaluate(diff(C.RUNTIME, K.MISSING), Context()) is None


def test_custom_rule_set_first_match_wins():
    first = Rule("A", "a", Severity.LOW, Classification.INFORMATIONAL, "r1")
    second = Rule("B", "b", Severity.HIGH, Classification.INFORMATIONAL, "r2")
    assert assess(diff(C.TOOL, K.MISSING), Context(), rules=(first, second)).rule_id == "A"


def test_rule_ids_are_unique_and_reasons_present():
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids))
    assert all(r.reason.strip() and r.description.strip() for r in RULES)


def test_default_rule_matches_everything():
    assert RULES[-1].id == "RM-DEFAULT"
    assert assess(diff(C.SYSTEM, K.CHANGED, name="weird", field="system.weird"), Context()).severity is Severity.INFO


def test_reasons_do_not_claim_causality():
    banned = ("caused by", "root cause", "is the cause", "will fail", "breaks")
    for rule in RULES:
        assert not any(phrase in rule.reason.lower() for phrase in banned), rule.id
