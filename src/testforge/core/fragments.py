"""Building the context that device templates are rendered against.

The shape produced here is the template contract. Device authors write against
it, so it changes only deliberately.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from testforge.core.models import TestCase
from testforge.core.naming import StepNamer, to_pascal, to_snake, to_upper_snake


def header_guard(path: str) -> str:
    """``test_sensor.h`` -> ``TEST_SENSOR_H``, for include guards."""
    name = PurePosixPath(path).name
    return to_upper_snake(name.replace(".", " ")) or "TESTFORGE_GENERATED_H"


def output_view(path: str) -> dict[str, str]:
    pure = PurePosixPath(path)
    return {
        "path": path,
        "basename": pure.name,
        "stem": pure.stem,
        "extension": pure.suffix,
        "guard": header_guard(path),
    }


def step_views(case: TestCase, namer: StepNamer) -> list[dict[str, object]]:
    views: list[dict[str, object]] = []
    for step in case.steps:
        views.append(
            {
                "index": step.index,
                "declared_index": step.declared_index,
                "title": step.title,
                "function_name": namer.name_for(step),
                "description_md": step.description_md,
                "expected": step.expected,
                "has_expected": step.expected is not None,
                "source_line": step.source_line,
                "is_first": step.index == 1,
                "is_last": step.index == len(case.steps),
            }
        )
    return views


def build_context(
    *,
    device_id: str,
    device_name: str,
    case: TestCase,
    steps: list[dict[str, object]],
    current_output: dict[str, str],
    all_outputs: list[dict[str, str]],
) -> dict[str, object]:
    """The single dictionary every template and fragment is rendered with."""
    return {
        "device": {"id": device_id, "name": device_name},
        "case": {
            "index": case.index,
            "title": case.title,
            "id": case.case_id,
            "pascal": to_pascal(case.title) or f"Case{case.index}",
            "snake": to_snake(case.title) or f"case{case.index}",
            "metadata": dict(case.metadata),
            "description_md": case.description_md,
            "step_count": len(case.steps),
            "source_line": case.source_line,
        },
        "steps": steps,
        "output": current_output,
        "outputs": all_outputs,
    }
