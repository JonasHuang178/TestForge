"""Golden-file snapshots: the primary check on what actually gets emitted.

Unit tests cover the edge cases; this one covers the thing a user receives. A
diff here is either a regression or an intended template change, and either way
it should be read line by line before being accepted.

Refresh after an intended template change:

    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""

from __future__ import annotations

import os
from pathlib import Path

from testforge.devices.registry import BUILTIN_ROOT, DeviceRegistry
from testforge.service import GenerationService

UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"

# Resolved from this file rather than imported from conftest: `tests` is not an
# importable package, so a cross-module import only works when the repository
# root happens to be on sys.path (as `python -m pytest` arranges but a bare
# `pytest` does not).
TESTS_DIR = Path(__file__).resolve().parent
GOLDEN = TESTS_DIR / "golden"
EXAMPLES = TESTS_DIR.parent / "examples"


def test_generated_output_matches_golden() -> None:
    service = GenerationService(DeviceRegistry.from_roots([BUILTIN_ROOT]))
    source = (EXAMPLES / "sensor_init.md").read_text(encoding="utf-8")
    artifacts = service.generate(source, "example_device").artifacts
    expected_names = {a.path for a in artifacts}

    if UPDATE:
        GOLDEN.mkdir(parents=True, exist_ok=True)
        for stale in GOLDEN.iterdir():
            if stale.is_file() and stale.name not in expected_names:
                stale.unlink()
        for artifact in artifacts:
            (GOLDEN / artifact.path).write_text(artifact.content, encoding="utf-8")

    hint = "\nrun `UPDATE_GOLDEN=1 pytest tests/test_golden.py` to refresh"

    on_disk = {p.name for p in GOLDEN.iterdir() if p.is_file()}
    assert on_disk == expected_names, f"golden file set is out of date{hint}"

    differing = [
        a.path
        for a in artifacts
        if (GOLDEN / a.path).read_text(encoding="utf-8") != a.content
    ]
    assert not differing, f"generated output changed for: {', '.join(differing)}{hint}"
