from __future__ import annotations

import pytest

from testforge.core.errors import AnchorMissingError, UnprocessableDocumentError
from testforge.core.models import ExistingFile
from testforge.core.options import GenerateOptions
from testforge.service import GenerationService


def test_generates_every_case_by_default(service: GenerationService, plan_source: str) -> None:
    result = service.generate(plan_source, "simple_cpp")
    assert result.summary.cases == 2
    assert result.summary.steps == 5
    # Every case lands in one file, so there is one artifact however many
    # cases the plan holds.
    assert [a.path for a in result.artifacts] == ["test_main.cpp"]
    assert all(a.mode == "created" for a in result.artifacts)
    assert "int printAllInfo()" in result.artifacts[0].content
    assert "int checkSensors()" in result.artifacts[0].content


def test_case_selector_narrows_to_one_case(service: GenerationService, plan_source: str) -> None:
    result = service.generate(plan_source, "simple_cpp", GenerateOptions(case_selector=2))
    assert result.summary.cases == 1
    assert [a.path for a in result.artifacts] == ["test_main.cpp"]
    assert "int checkSensors()" in result.artifacts[0].content
    assert "int printAllInfo()" not in result.artifacts[0].content


def test_case_selector_out_of_range_is_unprocessable(
    service: GenerationService, plan_source: str
) -> None:
    with pytest.raises(UnprocessableDocumentError) as excinfo:
        service.generate(plan_source, "simple_cpp", GenerateOptions(case_selector=99))
    # Parse-stage diagnostics are kept too, so the caller sees everything at once.
    assert "case_selector.out_of_range" in [d.code for d in excinfo.value.diagnostics]


def test_generation_is_deterministic(service: GenerationService, plan_source: str) -> None:
    # Golden-file testing depends on this, and so does a reviewable git diff.
    a = service.generate(plan_source, "simple_cpp")
    b = service.generate(plan_source, "simple_cpp")
    assert [x.content for x in a.artifacts] == [x.content for x in b.artifacts]


def test_regeneration_in_place_is_byte_identical(
    service: GenerationService, plan_source: str
) -> None:
    options = GenerateOptions(case_selector=1)
    first = service.generate(plan_source, "simple_cpp", options)
    existing = [ExistingFile(path=a.path, content=a.content) for a in first.artifacts]
    second = service.generate(plan_source, "simple_cpp", options, existing)
    assert [a.mode for a in second.artifacts] == ["updated"]
    assert [a.content for a in second.artifacts] == [a.content for a in first.artifacts]


def test_regeneration_keeps_code_outside_the_anchors(
    service: GenerationService, plan_source: str
) -> None:
    options = GenerateOptions(case_selector=1)
    first = service.generate(plan_source, "simple_cpp", options)
    edited = [
        ExistingFile(
            path=a.path,
            content=a.content.replace(
                "#include <iostream>", "#include <iostream>\n#include <vector>"
            ),
        )
        for a in first.artifacts
    ]

    grown = plan_source.replace(
        "### check sensors",
        "#### Step 4 Power down cleanly\n\nDrop the main rail.\n\n### check sensors",
    )
    result = service.generate(grown, "simple_cpp", options, edited)
    cpp = result.artifacts[0]
    assert "#include <vector>" in cpp.content  # hand edit survived
    assert "Power down cleanly" in cpp.content  # new step injected


def test_existing_file_without_anchors_is_rejected(
    service: GenerationService, plan_source: str
) -> None:
    stripped = [ExistingFile(path="test_main.cpp", content="// no markers\n")]
    with pytest.raises(AnchorMissingError) as excinfo:
        service.generate(
            plan_source, "simple_cpp", GenerateOptions(case_selector=1), stripped
        )
    assert excinfo.value.details["anchors"] == ["TEST_CASES", "CALLS"]


def test_request_options_override_the_device_but_omissions_do_not(
    service: GenerationService,
) -> None:
    src = (
        "## Test Case List\n\n### a case\n\n"
        "##### Step 1 Deep\n\nbody\n"
    )
    # The device says step headings are H4, so H5 yields nothing...
    with pytest.raises(UnprocessableDocumentError):
        service.generate(src, "simple_cpp")
    # ...until the request overrides just that one field.
    result = service.generate(src, "simple_cpp", GenerateOptions(step_heading_level=5))
    assert result.summary.steps == 1


def test_unusable_plan_carries_its_diagnostics(service: GenerationService) -> None:
    with pytest.raises(UnprocessableDocumentError) as excinfo:
        service.generate("no headings at all", "simple_cpp")
    # This device confines cases to a named section, so the first thing wrong
    # with a bare document is that the section is absent.
    assert [d.code for d in excinfo.value.diagnostics] == ["document.section_not_found"]


def test_parse_does_not_require_a_device(
    service: GenerationService, plan_source: str, plan_options
) -> None:
    assert len(service.parse(plan_source, plan_options).cases) == 2
