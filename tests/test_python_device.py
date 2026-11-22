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

from testforge.core.errors import ManifestError, TemplateRenderError
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
    assert device.kind == "python"
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

TEMPLATE = "// === TESTFORGE:BODY:BEGIN ===\n// === TESTFORGE:BODY:END ===\n"


def test_module_missing_a_required_name_fails_to_load(tmp_path: Path) -> None:
    directory = _write_device(tmp_path, "d1", 'ID = "d1"\nNAME = "D1"\n')
    with pytest.raises(ManifestError, match="step_function_name"):
        load_python_device(directory)


def test_module_id_must_match_its_folder(tmp_path: Path) -> None:
    directory = _write_device(
        tmp_path, "wrong", MINIMAL.format(id="d1"), {"t.cpp": TEMPLATE}
    )
    with pytest.raises(ManifestError, match="folder is named"):
        load_python_device(directory)


def test_module_that_raises_on_import_fails_to_load(tmp_path: Path) -> None:
    directory = _write_device(tmp_path, "d1", 'raise RuntimeError("boom")\n')
    with pytest.raises(ManifestError, match="RuntimeError"):
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
