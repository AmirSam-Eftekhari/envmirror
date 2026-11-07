"""StrEnum behaviour that the CLI, JSON output and reports depend on."""

import json
from enum import StrEnum

from envmirror.engine.diff import Kind
from envmirror.engine.versions import Delta
from envmirror.models.comparison import Category, Classification, Finding, Severity
import pytest

ALL_ENUMS = [Severity, Classification, Category, Kind, Delta]


@pytest.mark.parametrize("enum_cls", ALL_ENUMS)
def test_enums_are_str_enums_with_string_behaviour(enum_cls):
    assert issubclass(enum_cls, StrEnum)
    for member in enum_cls:
        assert isinstance(member, str)
        assert member == member.value
        assert str(member) == member.value
        assert f"{member}" == member.value
        assert enum_cls(member.value) is member
        assert json.dumps(member) == json.dumps(member.value)
        assert {member.value: 1}[member] == 1  # hashes like the plain string


def test_severity_values_are_stable_public_strings():
    assert [s.value for s in Severity] == ["critical", "high", "medium", "low", "info"]


def test_unknown_value_is_rejected():
    with pytest.raises(ValueError):
        Severity("urgent")


def test_finding_json_dump_uses_plain_values_and_round_trips():
    finding = Finding(
        id="RM-X:f", category=Category.RUNTIME, field="runtimes.node", expected="1", actual="2",
        severity=Severity.HIGH, classification=Classification.POTENTIAL_RISK, rule_id="RM-X",
        explanation="e", suggested_action="a",
    )
    dumped = finding.model_dump(mode="json")
    assert dumped["severity"] == "high" and type(dumped["severity"]) is str
    assert dumped["category"] == "runtime"
    assert json.loads(json.dumps(dumped))["classification"] == "potential_compatibility_risk"
    assert Finding.model_validate(dumped) == finding
    assert Finding.model_validate({**dumped, "severity": Severity.LOW}).severity is Severity.LOW
