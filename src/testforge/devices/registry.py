"""Discovery and lookup of devices.

The registry is built once at startup. Any manifest problem raises there, so a
running service is guaranteed to hold only valid devices.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jinja2 import Environment

from testforge.core.errors import DeviceNotFoundError, ManifestError
from testforge.core.templating import make_environment
from testforge.devices.manifest import (
    MANIFEST_FILENAME,
    TEMPLATE_DIRNAME,
    DeviceManifest,
    load_manifest,
)

#: Devices shipped with the package.
BUILTIN_ROOT = Path(__file__).parent / "builtin"

#: Colon-separated extra roots, e.g. TESTFORGE_DEVICE_PATH=/srv/devices
DEVICE_PATH_ENV = "TESTFORGE_DEVICE_PATH"


@dataclass(frozen=True)
class LoadedDevice:
    manifest: DeviceManifest
    directory: Path
    environment: Environment

    @property
    def id(self) -> str:
        return self.manifest.id


def default_roots(cwd: Path | None = None) -> list[Path]:
    """Where to look for devices when the caller does not say.

    Order is builtin, then ``./devices`` of the working directory, then
    ``TESTFORGE_DEVICE_PATH``. Later roots win on an id clash, so a project can
    shadow a builtin device with its own.
    """
    roots = [BUILTIN_ROOT]
    local = (cwd or Path.cwd()) / "devices"
    if local.is_dir():
        roots.append(local)
    for entry in os.environ.get(DEVICE_PATH_ENV, "").split(os.pathsep):
        if entry.strip():
            roots.append(Path(entry.strip()))
    return roots


class DeviceRegistry:
    def __init__(self, devices: dict[str, LoadedDevice]) -> None:
        self._devices = devices

    @classmethod
    def from_roots(cls, roots: Iterable[Path] | None = None) -> DeviceRegistry:
        devices: dict[str, LoadedDevice] = {}
        for root in roots if roots is not None else default_roots():
            root = Path(root)
            if not root.is_dir():
                continue
            for directory in sorted(p for p in root.iterdir() if p.is_dir()):
                if not (directory / MANIFEST_FILENAME).is_file():
                    continue
                manifest = load_manifest(directory)
                template_root = directory / TEMPLATE_DIRNAME
                if not template_root.is_dir():
                    raise ManifestError(
                        f"Device {manifest.id!r} has no {TEMPLATE_DIRNAME}/ directory",
                        details={"path": str(directory)},
                    )
                devices[manifest.id] = LoadedDevice(
                    manifest=manifest,
                    directory=directory,
                    environment=make_environment(template_root),
                )
        return cls(devices)

    def get(self, device_id: str) -> LoadedDevice:
        try:
            return self._devices[device_id]
        except KeyError:
            raise DeviceNotFoundError(
                f"Unknown device {device_id!r}. Known devices: "
                f"{', '.join(sorted(self._devices)) or '(none)'}",
                details={"device_id": device_id, "known": sorted(self._devices)},
            ) from None

    def list(self) -> list[LoadedDevice]:
        return [self._devices[k] for k in sorted(self._devices)]

    def __len__(self) -> int:
        return len(self._devices)
