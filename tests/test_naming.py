from __future__ import annotations

import pytest

from testforge.core.diagnostics import DiagnosticCollector
from testforge.core.errors import NamingPatternError
from testforge.core.models import TestCase, TestStep
from testforge.core.naming import (
    StepNamer,
    sanitize_identifier,
    to_pascal,
    to_snake,
    validate_pattern,
)


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Power on the device", "PowerOnTheDevice"),
        ("ADC read", "ADCRead"),  # acronyms stay intact
        ("read  multiple   spaces", "ReadMultipleSpaces"),
        ("Prüfung läuft", "PrufungLauft"),  # accents fold to ASCII
        ("step-with-dashes", "StepWithDashes"),
        ("2nd attempt", "2ndAttempt"),
        ("初始化裝置", ""),  # no ASCII equivalent at all
    ],
)
def test_to_pascal(title: str, expected: str) -> None:
    assert to_pascal(title) == expected


def test_to_snake() -> None:
    assert to_snake("Read Baseline Sample") == "read_baseline_sample"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("class", "class_"),  # C++ keyword
        ("2nd", "_2nd"),  # cannot start with a digit
        ("has spaces", "hasspaces"),
        ("", "Unnamed"),
    ],
)
def test_sanitize_identifier(raw: str, expected: str) -> None:
    assert sanitize_identifier(raw) == expected


def test_validate_pattern_rejects_unknown_placeholder() -> None:
    with pytest.raises(NamingPatternError) as excinfo:
        validate_pattern("Step_{nope}")
    assert "nope" in excinfo.value.message


def _case(*titles: str) -> TestCase:
    return TestCase(
        index=1,
        title="Case",
        source_line=1,
        steps=tuple(
            TestStep(index=i, title=t, source_line=i * 2) for i, t in enumerate(titles, 1)
        ),
    )


def test_index_prefixed_names_are_stable_and_ordered() -> None:
    case = _case("Power on the device", "Read firmware version")
    namer = StepNamer("TestStep_{index:02d}_{pascal_title}", case, "dev")
    assert [namer.name_for(s) for s in case.steps] == [
        "TestStep_01_PowerOnTheDevice",
        "TestStep_02_ReadFirmwareVersion",
    ]


def test_duplicate_titles_are_deduped_with_a_diagnostic() -> None:
    case = _case("Reset", "Reset")
    diag = DiagnosticCollector()
    # A pattern without {index} is what makes a collision possible at all.
    namer = StepNamer("Step_{pascal_title}", case, "dev", diag)
    assert [namer.name_for(s) for s in case.steps] == ["Step_Reset", "Step_Reset_2"]
    assert [d.code for d in diag.items] == ["naming.duplicate"]


def test_unrepresentable_title_falls_back_and_warns() -> None:
    case = _case("初始化裝置")
    diag = DiagnosticCollector()
    namer = StepNamer("TestStep_{index:02d}_{pascal_title}", case, "dev", diag)
    assert namer.name_for(case.steps[0]) == "TestStep_01_Step1"
    assert [d.code for d in diag.items] == ["naming.title_not_representable"]
