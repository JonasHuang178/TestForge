"""Devices, whose rules are written in Python.

The device module owns naming, filenames and code. The framework still owns
anchor injection, so the guarantees that must hold for every device — in-place
regeneration, preserved line endings, determinism — are asserted here too.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from testforge.core.errors import DeviceDefinitionError, TemplateRenderError
from testforge.core.models import ExistingFile
from testforge.devices.python_device import load_python_device
from testforge.devices.registry import DeviceRegistry
from testforge.service import GenerationService

# Resolved here rather than imported from another test module: `tests` is not
# an importable package under a bare `pytest`.
DEVICES = Path(__file__).resolve().parents[1] / "devices"

#: Written in simple_cpp's conventions: a named section, H3 cases, H4 steps.
PLAN = (
    '## Test Case List\n'
    '\n'
    '| ID | Test Name |\n'
    '|---|---|\n'
    '| TC-100 | print all info |\n'
    '\n'
    '### print all info\n'
    'Step 1 Print the build version  \n'
    'Step 2 Print the device id  \n'
)

TWO_CASES = (
    '## Test Case List\n'
    '\n'
    '| ID | Test Name |\n'
    '|---|---|\n'
    '| TC-100 | print all info |\n'
    '| TC-101 | check sensors |\n'
    '\n'
    '### print all info\n'
    'Step 1 Print the build version  \n'
    'Step 2 Print the device id  \n'
    '\n'
    '### check sensors\n'
    'Step 1 Read the temperature  \n'
)

#: For devices built in a temporary directory, which take the default
#: conventions: H1 cases, H2 steps, no section.
DEFAULT_PLAN = "# A case\n\n## Step 1: Do it\n\nbody\n"


@pytest.fixture
def device_service() -> GenerationService:
    return GenerationService(DeviceRegistry.from_roots([DEVICES]))


# -- the shipped device -----------------------------------------------------


def test_device_loads_from_a_python_module(device_service: GenerationService) -> None:
    device = device_service.registry.get("simple_cpp")
    assert device.name == "Simple C++"
    assert device.parse_options.case_heading_level == 3
    assert device.parse_options.case_section == "Test Case List"
    assert device.parse_options.step_style == "line"
    assert device.parse_options.case_table
    assert device.builds_whole_plan


def test_generates_the_file_the_module_asked_for(device_service: GenerationService) -> None:
    result = device_service.generate(PLAN, "simple_cpp")
    assert [a.path for a in result.artifacts] == ["test_main.cpp"]
    assert "int printAllInfo()" in result.artifacts[0].content


def test_no_placeholder_survives_generation(device_service: GenerationService) -> None:
    content = device_service.generate(PLAN, "simple_cpp").artifacts[0].content
    assert "@@" not in content


def test_anchors_are_filled_by_the_module(device_service: GenerationService) -> None:
    artifact = device_service.generate(PLAN, "simple_cpp").artifacts[0]
    assert artifact.anchors_filled == ("TEST_CASES", "CALLS")
    assert "// Step1 Print the build version" in artifact.content
    assert "printAllInfo();" in artifact.content


def test_markers_are_inserted_into_a_template_that_has_none(
    device_service: GenerationService,
) -> None:
    template = (DEVICES / "simple_cpp" / "main.cpp").read_text(encoding="utf-8")
    assert "TESTFORGE" not in template

    content = device_service.generate(PLAN, "simple_cpp").artifacts[0].content
    assert "// === TESTFORGE:TEST_CASES:BEGIN ===" in content
    assert "// === TESTFORGE:CALLS:BEGIN ===" in content


def test_every_case_lands_in_one_file(device_service: GenerationService) -> None:
    result = device_service.generate(TWO_CASES, "simple_cpp")
    assert [a.path for a in result.artifacts] == ["test_main.cpp"]
    content = result.artifacts[0].content
    # Both survive: with build(case) the second would have overwritten the
    # first, which is why this device defines build_all(cases).
    assert "int printAllInfo()" in content
    assert "int checkSensors()" in content


def test_main_calls_every_case(device_service: GenerationService) -> None:
    content = device_service.generate(TWO_CASES, "simple_cpp").artifacts[0].content
    main_body = content.split("int main()", 1)[1]
    assert "printAllInfo();" in main_body
    assert "checkSensors();" in main_body


def test_headings_outside_the_named_section_are_ignored(
    device_service: GenerationService,
) -> None:
    plan = (
        "## Environment\n\n### Hardware\n\nNot a case.\n\n"
        "## Test Case List\n\n### real case\nStep 1 Do it\n"
    )
    result = device_service.generate(plan, "simple_cpp")
    assert result.summary.cases == 1
    assert "int realCase()" in result.artifacts[0].content
    assert "hardware" not in result.artifacts[0].content.lower()


def test_regeneration_keeps_hand_written_code(device_service: GenerationService) -> None:
    first = device_service.generate(PLAN, "simple_cpp").artifacts[0]
    edited = [
        ExistingFile(
            path=first.path,
            content=first.content.replace(
                "#include <iostream>", "#include <iostream>\n\nstatic int g_mine = 7;"
            ),
        )
    ]
    second = device_service.generate(PLAN, "simple_cpp", existing_files=edited).artifacts[0]
    assert second.mode == "updated"
    assert "static int g_mine = 7;" in second.content
    # The anchored region is unchanged, so a rerun produces no diff at all.
    assert second.content == edited[0].content


def test_crlf_is_preserved(device_service: GenerationService) -> None:
    first = device_service.generate(PLAN, "simple_cpp").artifacts[0]
    crlf = ExistingFile(path=first.path, content=first.content.replace("\n", "\r\n"))
    out = device_service.generate(PLAN, "simple_cpp", existing_files=[crlf]).artifacts[0]
    assert out.content == crlf.content


def test_generation_is_deterministic(device_service: GenerationService) -> None:
    a = device_service.generate(PLAN, "simple_cpp")
    b = device_service.generate(PLAN, "simple_cpp")
    assert [x.content for x in a.artifacts] == [x.content for x in b.artifacts]


def test_the_device_ships_an_example_plan(device_service: GenerationService) -> None:
    # The web page offers it, so it must exist and must parse under the
    # device's own conventions.
    device = device_service.registry.get("simple_cpp")
    assert device.example_plan
    assert device_service.generate(device.example_plan, "simple_cpp").summary.cases == 2


# -- contract enforcement ---------------------------------------------------


def _write_device(
    root: Path, name: str, module_src: str, templates: dict[str, str] | None = None
) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "device.py").write_text(textwrap.dedent(module_src), encoding="utf-8")
    for filename, body in (templates or {}).items():
        (directory / filename).write_text(body, encoding="utf-8")
    return directory


MINIMAL = '''
    from testforge.device_api import output
    ID = "{id}"
    NAME = "Minimal"
    def step_function_name(step):
        return f"Step{{step.index}}"
    def build(case):
        return [output("out.cpp", "t.cpp", {{"BODY": "// x"}})]
'''

TEMPLATE = "// === TESTFORGE:BODY:BEGIN ===\n// === TESTFORGE:BODY:END ===\n"


def test_module_missing_a_required_name_fails_to_load(tmp_path: Path) -> None:
    directory = _write_device(tmp_path, "d1", 'ID = "d1"\nNAME = "D1"\n')
    with pytest.raises(DeviceDefinitionError, match="step_function_name"):
        load_python_device(directory)


def test_module_id_must_match_its_folder(tmp_path: Path) -> None:
    directory = _write_device(
        tmp_path, "wrong", MINIMAL.format(id="d1"), {"t.cpp": TEMPLATE}
    )
    with pytest.raises(DeviceDefinitionError, match="folder is named"):
        load_python_device(directory)


def test_module_that_raises_on_import_fails_to_load(tmp_path: Path) -> None:
    directory = _write_device(tmp_path, "d1", 'raise RuntimeError("boom")\n')
    with pytest.raises(DeviceDefinitionError, match="RuntimeError"):
        load_python_device(directory)


def test_module_defining_neither_entry_point_fails(tmp_path: Path) -> None:
    directory = _write_device(
        tmp_path,
        "d1",
        '''
        ID = "d1"
        NAME = "D1"
        def step_function_name(step):
            return "x"
        ''',
    )
    with pytest.raises(DeviceDefinitionError, match="build_all"):
        load_python_device(directory)


def test_module_defining_both_entry_points_fails(tmp_path: Path) -> None:
    directory = _write_device(
        tmp_path,
        "d1",
        '''
        ID = "d1"
        NAME = "D1"
        def step_function_name(step):
            return "x"
        def build(case):
            return []
        def build_all(cases):
            return []
        ''',
    )
    with pytest.raises(DeviceDefinitionError, match="exactly one"):
        load_python_device(directory)


def test_missing_template_is_reported_with_the_device_name(tmp_path: Path) -> None:
    _write_device(tmp_path, "d1", MINIMAL.format(id="d1"))  # no t.cpp
    service = GenerationService(DeviceRegistry.from_roots([tmp_path]))
    with pytest.raises(TemplateRenderError, match="t.cpp"):
        service.generate(DEFAULT_PLAN, "d1")


def test_unresolved_template_variable_is_an_error(tmp_path: Path) -> None:
    _write_device(
        tmp_path,
        "d1",
        MINIMAL.format(id="d1"),
        {"t.cpp": "// @@MISSING@@\n" + TEMPLATE},
    )
    service = GenerationService(DeviceRegistry.from_roots([tmp_path]))
    with pytest.raises(TemplateRenderError, match="MISSING"):
        service.generate(DEFAULT_PLAN, "d1")


def test_build_returning_the_wrong_type_is_reported(tmp_path: Path) -> None:
    _write_device(
        tmp_path,
        "d1",
        '''
        ID = "d1"
        NAME = "D1"
        def step_function_name(step):
            return f"Step{step.index}"
        def build(case):
            return ["not an OutputFile"]
        ''',
        {"t.cpp": TEMPLATE},
    )
    service = GenerationService(DeviceRegistry.from_roots([tmp_path]))
    with pytest.raises(TemplateRenderError, match="OutputFile"):
        service.generate(DEFAULT_PLAN, "d1")


def test_step_function_name_returning_nothing_is_reported(tmp_path: Path) -> None:
    _write_device(
        tmp_path,
        "d1",
        '''
        from testforge.device_api import output
        ID = "d1"
        NAME = "D1"
        def step_function_name(step):
            return ""
        def build(case):
            return [output("out.cpp", "t.cpp", {"BODY": "// x"})]
        ''',
        {"t.cpp": TEMPLATE},
    )
    service = GenerationService(DeviceRegistry.from_roots([tmp_path]))
    with pytest.raises(TemplateRenderError, match="non-empty string"):
        service.generate(DEFAULT_PLAN, "d1")


def test_a_folder_without_a_module_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "shared_headers").mkdir()
    (tmp_path / "shared_headers" / "common.h").write_text("// shared\n")
    _write_device(tmp_path, "d1", MINIMAL.format(id="d1"), {"t.cpp": TEMPLATE})
    registry = DeviceRegistry.from_roots([tmp_path])
    assert [d.id for d in registry.list()] == ["d1"]


def test_a_later_root_shadows_an_earlier_one(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    _write_device(first, "d1", MINIMAL.format(id="d1"), {"t.cpp": TEMPLATE})
    _write_device(
        second,
        "d1",
        MINIMAL.format(id="d1").replace('NAME = "Minimal"', 'NAME = "Override"'),
        {"t.cpp": TEMPLATE},
    )
    registry = DeviceRegistry.from_roots([first, second])
    assert registry.get("d1").name == "Override"
