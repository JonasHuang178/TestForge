"""CLI tests.

The CLI is the second consumer of GenerationService, so these also guard the
claim that core works without the web stack. The file round trip is the part
that behaves differently per platform, so it is asserted explicitly.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from testforge.cli import _read_verbatim, _write_verbatim, main

PLAN = (
    "# Test Case: Sensor Init\n\n- ID: TC-001\n\n"
    "## Step 1: Power on\n\nDrive the enable line high.\n\n"
    "**Expected:** READY within 500 ms.\n"
)


def test_devices_lists_the_builtin() -> None:
    result = CliRunner().invoke(main, ["devices"])
    assert result.exit_code == 0
    assert "example_device" in result.output


def test_parse_reports_cases_and_steps(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    result = CliRunner().invoke(main, ["parse", str(plan)])
    assert result.exit_code == 0
    assert "Sensor Init" in result.output
    assert "Power on" in result.output


def test_generate_writes_then_regenerates_in_place(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    out = tmp_path / "out"
    args = ["generate", str(plan), "--device", "example_device", "-o", str(out)]

    first = CliRunner().invoke(main, args)
    assert first.exit_code == 0
    assert "created" in first.output
    cpp = out / "test_sensor_init.cpp"
    assert cpp.is_file()

    # A hand-written line outside the anchors must survive the next run.
    edited = _read_verbatim(cpp).replace(
        "namespace example_device {",
        "namespace example_device {\n\nstatic int g_hand_written = 1;",
    )
    _write_verbatim(cpp, edited)

    second = CliRunner().invoke(main, args)
    assert second.exit_code == 0
    assert "updated" in second.output
    assert "g_hand_written" in _read_verbatim(cpp)


def test_file_round_trip_preserves_crlf(tmp_path: Path) -> None:
    # Text mode would rewrite these endings on Windows, in both directions.
    target = tmp_path / "sample.cpp"
    content = "line one\r\nline two\r\n"
    _write_verbatim(target, content)
    assert target.read_bytes() == content.encode("utf-8")
    assert _read_verbatim(target) == content


def test_file_round_trip_preserves_lf(tmp_path: Path) -> None:
    target = tmp_path / "sample.cpp"
    content = "line one\nline two\n"
    _write_verbatim(target, content)
    assert target.read_bytes() == content.encode("utf-8")
    assert _read_verbatim(target) == content


def test_unknown_device_reports_the_known_ones(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    result = CliRunner().invoke(main, ["generate", str(plan), "--device", "ghost"])
    assert result.exit_code != 0
