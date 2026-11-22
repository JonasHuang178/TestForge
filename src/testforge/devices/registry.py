"""Discovery and lookup of devices.

The registry is built once at startup and every device is imported and checked
there, so a running service holds only devices that load.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from testforge.core.errors import DeviceNotFoundError
from testforge.devices.python_device import DEVICE_MODULE, PythonDevice, load_python_device

#: Where a project keeps its devices, relative to the working directory.
LOCAL_DIRNAME = "devices"

#: Extra roots, separated by the platform's path separator
#: (``:`` on Unix, ``;`` on Windows).
DEVICE_PATH_ENV = "TESTFORGE_DEVICE_PATH"


def default_roots(cwd: Path | None = None) -> list[Path]:
    """Where to look for devices when the caller does not say.

    ``./devices`` first, then anything on ``TESTFORGE_DEVICE_PATH``. A later
    root wins on an id clash, so a shared device directory can override a
    project's own.
    """
    roots = [(cwd or Path.cwd()) / LOCAL_DIRNAME]
    for entry in os.environ.get(DEVICE_PATH_ENV, "").split(os.pathsep):
        if entry.strip():
            roots.append(Path(entry.strip()))
    return roots


class DeviceRegistry:
    def __init__(self, devices: dict[str, PythonDevice]) -> None:
        self._devices = devices

    @classmethod
    def from_roots(cls, roots: Iterable[Path] | None = None) -> DeviceRegistry:
        devices: dict[str, PythonDevice] = {}
        for root in roots if roots is not None else default_roots():
            root = Path(root)
            if not root.is_dir():
                continue
            for directory in sorted(p for p in root.iterdir() if p.is_dir()):
                # A folder without device.py is not a device and is skipped in
                # silence: a devices directory may hold shared headers too.
                if not (directory / DEVICE_MODULE).is_file():
                    continue
                device = load_python_device(directory)
                devices[device.id] = device
        return cls(devices)

    def get(self, device_id: str) -> PythonDevice:
        try:
            return self._devices[device_id]
        except KeyError:
            raise DeviceNotFoundError(
                f"Unknown device {device_id!r}. Known devices: "
                f"{', '.join(sorted(self._devices)) or '(none)'}",
                details={"device_id": device_id, "known": sorted(self._devices)},
            ) from None

    def list(self) -> list[PythonDevice]:
        return [self._devices[k] for k in sorted(self._devices)]

    def __len__(self) -> int:
        return len(self._devices)
