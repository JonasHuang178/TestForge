"""Devices whose rules are written in Python.

The device module owns naming, filenames and code. The framework still owns
anchor injection, so the guarantees that must hold for every device — in-place
regeneration, preserved line endings, determinism — are asserted here against
a Python device too.
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
DEMO_ROOT = Path(__file__).resolve().parents[1] / "devices"

PLAN = textwrap.dedent(
    """\
    # Test Case: LED Blink

    - ID: TC-100

    ## Step 1: Power on the board

    Apply 5V to the main rail.

    **Expected:** The power LED turns on within 200 ms.

    ## Step 2: Power off cleanly

    Drop the main rail.
    """
)


@pytest.fixture
def demo_service() -> GenerationService:
    return GenerationService(DeviceRegistry.from_roots([DEMO_ROOT]))


def test_demo_board_loads_from_a_python_module(demo_service: GenerationService) -> None:
    device = demo_service.registry.get("demo_board")
    assert device.name == "Demo Board"
    assert device.parse_options.step_heading_level == 2


def test_generates_the_files_the_module_asked_for(demo_service: GenerationService) -> None:
    result = demo_service.generate(PLAN, "demo_board")
    assert [a.path for a in result.artifacts] == ["test_led_blink.h", "test_led_blink.cpp"]
    assert result.summary.functions == (
        "TestStep_01_PowerOnTheBoard",
        "TestStep_02_PowerOffCleanly",
    )


def test_template_variables_are_substituted(demo_service: GenerationService) -> None:
    header = demo_service.generate(PLAN, "demo_board").artifacts[0].content
    assert "#ifndef TEST_LED_BLINK_H" in header
    assert "// Test case: LED Blink" in header
    assert "void RunLEDBlink(TestContext& ctx);" in header
    assert "@@" not in header  # every placeholder resolved


def test_anchors_are_filled_by_the_module(demo_service: GenerationService) -> None:
    artifacts = demo_service.generate(PLAN, "demo_board").artifacts
    assert artifacts[0].anchors_filled == ("STEP_DECLS",)
    assert artifacts[1].anchors_filled == ("STEP_CALLS", "STEP_DEFS")
    source = artifacts[1].content
    assert 'DEMO_RUN_STEP(ctx, 1, "Power on the board", TestStep_01_PowerOnTheBoard);' in source
    # A step without an expectation gets no assertion scaffold.
    assert source.count("DEMO_EXPECT") == 1


def test_regeneration_is_idempotent_and_keeps_hand_written_code(
    demo_service: GenerationService,
) -> None:
    first = demo_service.generate(PLAN, "demo_board")
    edited = []
    for artifact in first.artifacts:
        content = artifact.content
        if artifact.path.endswith(".cpp"):
            content = content.replace(
                "namespace demo_board {",
                "namespace demo_board {\n\nstatic int g_mine = 7;",
            )
        edited.append(ExistingFile(path=artifact.path, content=content))

    second = demo_service.generate(PLAN, "demo_board", existing_files=edited)
    assert [a.mode for a in second.artifacts] == ["updated", "updated"]
    source = next(a for a in second.artifacts if a.path.endswith(".cpp"))
    assert "static int g_mine = 7;" in source.content
    # The anchored region is unchanged, so a rerun produces no diff at all.
    assert source.content == edited[1].content


def test_crlf_is_preserved_for_a_python_device(demo_service: GenerationService) -> None:
    first = demo_service.generate(PLAN, "demo_board").artifacts[0]
    crlf = ExistingFile(path=first.path, content=first.content.replace("\n", "\r\n"))
    out = demo_service.generate(PLAN, "demo_board", existing_files=[crlf]).artifacts[0]
    assert out.content == crlf.content


def test_generation_is_deterministic(demo_service: GenerationService) -> None:
    a = demo_service.generate(PLAN, "demo_board")
    b = demo_service.generate(PLAN, "demo_board")
    assert [x.content for x in a.artifacts] == [x.content for x in b.artifacts]


# -- contract enforcement ---------------------------------------------------


def _write_device(root: Path, name: str, module_src: str, templates: dict[str, str] | None = None) -> Path:
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

CONSOLE_PLAN = textwrap.dedent(
    """\
    ## Test Case List

    ### print all info

    #### Step 1 Print the build version

    Call the version helper.

    ### check sensors

    #### Step 1 Read the temperature

    Poll the sensor once.
    """
)

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


def test_missing_template_is_reported_with_the_device_name(tmp_path: Path) -> None:
    _write_device(tmp_path, "d1", MINIMAL.format(id="d1"))  # no t.cpp
    service = GenerationService(DeviceRegistry.from_roots([tmp_path]))
    with pytest.raises(TemplateRenderError, match="t.cpp"):
        service.generate(PLAN, "d1")


def test_unresolved_template_variable_is_an_error(tmp_path: Path) -> None:
    _write_device(
        tmp_path,
        "d1",
        MINIMAL.format(id="d1"),
        {"t.cpp": "// @@MISSING@@\n" + TEMPLATE},
    )
    service = GenerationService(DeviceRegistry.from_roots([tmp_path]))
    with pytest.raises(TemplateRenderError, match="MISSING"):
        service.generate(PLAN, "d1")


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
        service.generate(PLAN, "d1")


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
        service.generate(PLAN, "d1")


# -- the whole-plan device --------------------------------------------------


def test_simple_cpp_puts_every_case_in_one_file(demo_service: GenerationService) -> None:
    result = demo_service.generate(CONSOLE_PLAN, "simple_cpp")
    assert [a.path for a in result.artifacts] == ["test_main.cpp"]
    content = result.artifacts[0].content
    # Both cases survive: build(case) would have had the second overwrite the
    # first, which is why this device defines build_all(cases).
    assert "int printAllInfo()" in content
    assert "int checkSensors()" in content
    assert content.count("return 0;") == 3  # one per case, plus main's


def test_simple_cpp_calls_each_case_from_main(demo_service: GenerationService) -> None:
    content = demo_service.generate(CONSOLE_PLAN, "simple_cpp").artifacts[0].content
    main_body = content.split("int main()", 1)[1]
    assert "printAllInfo();" in main_body
    assert "checkSensors();" in main_body


def test_simple_cpp_inserts_anchors_into_a_plain_template(
    demo_service: GenerationService,
) -> None:
    # The device's own main.cpp carries no markers; the module adds them.
    template = (DEMO_ROOT / "simple_cpp" / "main.cpp").read_text(encoding="utf-8")
    assert "TESTFORGE" not in template

    content = demo_service.generate(CONSOLE_PLAN, "simple_cpp").artifacts[0].content
    assert "// === TESTFORGE:TEST_CASES:BEGIN ===" in content
    assert "// === TESTFORGE:CALLS:BEGIN ===" in content


def test_cases_outside_the_named_section_are_ignored(
    demo_service: GenerationService,
) -> None:
    plan = (
        "## Environment\n\n### Hardware\n\nNot a case.\n\n"
        "## Test Case List\n\n### real case\n\n#### Step 1 Do it\n\nbody\n"
    )
    result = demo_service.generate(plan, "simple_cpp")
    assert result.summary.cases == 1
    assert "int realCase()" in result.artifacts[0].content
    assert "hardware" not in result.artifacts[0].content.lower()


def test_whole_plan_regeneration_keeps_hand_written_code(
    demo_service: GenerationService,
) -> None:
    first = demo_service.generate(CONSOLE_PLAN, "simple_cpp").artifacts[0]
    edited = ExistingFile(
        path=first.path,
        content=first.content.replace(
            "#include <iostream>", "#include <iostream>\n#include <vector>"
        ),
    )
    second = demo_service.generate(
        CONSOLE_PLAN, "simple_cpp", existing_files=[edited]
    ).artifacts[0]
    assert second.mode == "updated"
    assert "#include <vector>" in second.content
    assert second.content == edited.content  # nothing else moved


def test_module_defining_neither_entry_point_fails(tmp_path: Path) -> None:
    _write_device(
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
        load_python_device(tmp_path / "d1")


def test_module_defining_both_entry_points_fails(tmp_path: Path) -> None:
    _write_device(
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
        load_python_device(tmp_path / "d1")
