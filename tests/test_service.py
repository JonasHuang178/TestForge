from __future__ import annotations

import pytest

from testforge.core.errors import AnchorMissingError, UnprocessableDocumentError
from testforge.core.models import ExistingFile
from testforge.core.options import GenerateOptions
from testforge.service import GenerationService


def test_generates_every_case_by_default(service: GenerationService, plan_source: str) -> None:
    result = service.generate(plan_source, "example_device")
    assert result.summary.cases == 2
    assert result.summary.steps == 6
    assert [a.path for a in result.artifacts] == [
        "test_sensor_initialization_sequence.h",
        "test_sensor_initialization_sequence.cpp",
        "test_sensor_fault_recovery.h",
        "test_sensor_fault_recovery.cpp",
    ]
    assert all(a.mode == "created" for a in result.artifacts)


def test_case_selector_narrows_to_one_case(service: GenerationService, plan_source: str) -> None:
    result = service.generate(plan_source, "example_device", GenerateOptions(case_selector=2))
    assert result.summary.cases == 1
    assert [a.path for a in result.artifacts] == [
        "test_sensor_fault_recovery.h",
        "test_sensor_fault_recovery.cpp",
    ]


def test_case_selector_out_of_range_is_unprocessable(
    service: GenerationService, plan_source: str
) -> None:
    with pytest.raises(UnprocessableDocumentError) as excinfo:
        service.generate(plan_source, "example_device", GenerateOptions(case_selector=99))
    # Parse-stage diagnostics are kept too, so the caller sees everything at once.
    assert "case_selector.out_of_range" in [d.code for d in excinfo.value.diagnostics]


def test_generation_is_deterministic(service: GenerationService, plan_source: str) -> None:
    # Golden-file testing depends on this, and so does a reviewable git diff.
    a = service.generate(plan_source, "example_device")
    b = service.generate(plan_source, "example_device")
    assert [x.content for x in a.artifacts] == [x.content for x in b.artifacts]


def test_regeneration_in_place_is_byte_identical(
    service: GenerationService, plan_source: str
) -> None:
    options = GenerateOptions(case_selector=1)
    first = service.generate(plan_source, "example_device", options)
    existing = [ExistingFile(path=a.path, content=a.content) for a in first.artifacts]
    second = service.generate(plan_source, "example_device", options, existing)
    assert [a.mode for a in second.artifacts] == ["updated", "updated"]
    assert [a.content for a in second.artifacts] == [a.content for a in first.artifacts]


def test_regeneration_keeps_code_outside_the_anchors(
    service: GenerationService, plan_source: str
) -> None:
    options = GenerateOptions(case_selector=1)
    first = service.generate(plan_source, "example_device", options)
    edited = []
    for artifact in first.artifacts:
        content = artifact.content
        if artifact.path.endswith(".cpp"):
            content = content.replace(
                "namespace example_device {",
                "namespace example_device {\n\nstatic int g_retry_budget = 3;",
            )
        edited.append(ExistingFile(path=artifact.path, content=content))

    grown = plan_source.replace(
        "# Test Case: Sensor Fault Recovery",
        "## Step 5: Power down cleanly\n\nDrop the enable line.\n\n"
        "**Expected:** No brown-out reset is logged.\n\n"
        "# Test Case: Sensor Fault Recovery",
    )
    result = service.generate(grown, "example_device", options, edited)
    cpp = next(a for a in result.artifacts if a.path.endswith(".cpp"))
    assert "static int g_retry_budget = 3;" in cpp.content  # hand edit survived
    assert "TestStep_05_PowerDownCleanly" in cpp.content  # new step injected


def test_existing_file_without_anchors_is_rejected(
    service: GenerationService, plan_source: str
) -> None:
    stripped = [
        ExistingFile(path="test_sensor_initialization_sequence.h", content="// no markers\n")
    ]
    with pytest.raises(AnchorMissingError) as excinfo:
        service.generate(
            plan_source, "example_device", GenerateOptions(case_selector=1), stripped
        )
    assert excinfo.value.details["anchors"] == ["STEP_DECLS"]


def test_naming_override_changes_function_names(
    service: GenerationService, plan_source: str
) -> None:
    result = service.generate(
        plan_source,
        "example_device",
        GenerateOptions(case_selector=1, naming_pattern="{case_pascal}_{snake_title}"),
    )
    assert result.summary.functions[0] == "SensorInitializationSequence_power_on_the_device"


def test_request_options_override_the_manifest_but_omissions_do_not(
    service: GenerationService,
) -> None:
    src = "# Test Case: C\n\n### Step 1: Deep\n\nx\n"
    # The manifest says step headings are H2, so H3 yields nothing...
    with pytest.raises(UnprocessableDocumentError):
        service.generate(src, "example_device")
    # ...until the request overrides just that one field.
    result = service.generate(src, "example_device", GenerateOptions(step_heading_level=3))
    assert result.summary.steps == 1


def test_unusable_plan_carries_its_diagnostics(service: GenerationService) -> None:
    with pytest.raises(UnprocessableDocumentError) as excinfo:
        service.generate("no headings at all", "example_device")
    assert [d.code for d in excinfo.value.diagnostics] == ["document.no_test_case"]


def test_parse_does_not_require_a_device(service: GenerationService, plan_source: str) -> None:
    assert len(service.parse(plan_source).cases) == 2
