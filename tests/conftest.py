from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from testforge.api.app import create_app
from testforge.devices.registry import DeviceRegistry
from testforge.service import GenerationService

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
DEVICES = REPO_ROOT / "devices"


@pytest.fixture(scope="session")
def plan_source() -> str:
    """A richer plan: two cases, metadata, a fenced block, a step with no
    expectation. Used wherever the test is about parsing or generation rather
    than about one device."""
    return (EXAMPLES / "sensor_init.md").read_text(encoding="utf-8")


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
