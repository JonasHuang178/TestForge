from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from testforge.api.app import create_app
from testforge.core.options import ParseOptions
from testforge.devices.registry import DeviceRegistry
from testforge.service import GenerationService

REPO_ROOT = Path(__file__).resolve().parents[1]
DEVICES = REPO_ROOT / "devices"

#: The device every test generates with, and the plan it ships.
DEVICE_ID = "simple_cpp"
PLAN_PATH = DEVICES / DEVICE_ID / "example_plan.md"


@pytest.fixture(scope="session")
def plan_source() -> str:
    """The device's own sample: two cases, metadata, a fenced block, a step
    with no expectation, and sections that must not be read as cases."""
    return PLAN_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def plan_options() -> ParseOptions:
    """The conventions that sample is written in, for tests that parse it
    without going through a device."""
    return ParseOptions(
        case_heading_level=3,
        case_section="Test Case List",
        step_style="line",
        case_table=True,
    )


@pytest.fixture
def registry() -> DeviceRegistry:
    # Pinned to the repository's own devices so a stray TESTFORGE_DEVICE_PATH
    # cannot change what the tests see.
    return DeviceRegistry.from_roots([DEVICES])


@pytest.fixture
def service(registry: DeviceRegistry) -> GenerationService:
    return GenerationService(registry)


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(device_roots=[DEVICES])) as c:
        yield c
