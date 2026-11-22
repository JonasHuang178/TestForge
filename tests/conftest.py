from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from testforge.api.app import create_app
from testforge.devices.registry import BUILTIN_ROOT, DeviceRegistry
from testforge.service import GenerationService

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture(scope="session")
def plan_source() -> str:
    return (EXAMPLES / "sensor_init.md").read_text(encoding="utf-8")


@pytest.fixture
def registry() -> DeviceRegistry:
    # Pin to the builtin root so a stray ./devices directory or an exported
    # TESTFORGE_DEVICE_PATH cannot change what the tests see.
    return DeviceRegistry.from_roots([BUILTIN_ROOT])


@pytest.fixture
def service(registry: DeviceRegistry) -> GenerationService:
    return GenerationService(registry)


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(device_roots=[BUILTIN_ROOT])) as c:
        yield c
