from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from testforge.core.errors import DeviceNotFoundError, ManifestError
from testforge.devices.manifest import load_manifest
from testforge.devices.registry import BUILTIN_ROOT, DeviceRegistry

EXAMPLE = BUILTIN_ROOT / "example_device"


def test_builtin_example_device_loads() -> None:
    manifest = load_manifest(EXAMPLE)
    assert manifest.id == "example_device"
    assert manifest.anchor_names == ["STEP_DECLS", "STEP_CALLS", "STEP_DEFS"]


def test_registry_lookup_and_listing(registry: DeviceRegistry) -> None:
    assert [d.id for d in registry.list()] == ["example_device"]
    assert registry.get("example_device").manifest.name == "Example Device"


def test_unknown_device_names_the_known_ones(registry: DeviceRegistry) -> None:
    with pytest.raises(DeviceNotFoundError) as excinfo:
        registry.get("ghost")
    assert excinfo.value.details["known"] == ["example_device"]


def _write_device(root: Path, name: str, manifest: dict, *, templates=("t.j2",)) -> Path:
    directory = root / name
    (directory / "templates").mkdir(parents=True)
    for t in templates:
        (directory / "templates" / t).write_text("x\n")
    (directory / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    return directory


BASE = {
    "id": "d1",
    "name": "D1",
    "outputs": [{"path": "o_{case_snake}.cpp", "template": "t.j2"}],
}


def test_manifest_requires_matching_directory_name(tmp_path: Path) -> None:
    directory = _write_device(tmp_path, "wrong_name", BASE)
    with pytest.raises(ManifestError, match="does not match its directory name"):
        load_manifest(directory)


def test_manifest_rejects_missing_template(tmp_path: Path) -> None:
    broken = {**BASE, "outputs": [{"path": "o.cpp", "template": "absent.j2"}]}
    directory = _write_device(tmp_path, "d1", broken)
    with pytest.raises(ManifestError, match="do not exist"):
        load_manifest(directory)


def test_manifest_rejects_unknown_naming_placeholder(tmp_path: Path) -> None:
    broken = {**BASE, "naming": {"step_function": "S_{nope}"}}
    directory = _write_device(tmp_path, "d1", broken)
    with pytest.raises(ManifestError, match="nope"):
        load_manifest(directory)


def test_manifest_rejects_step_placeholder_in_output_path(tmp_path: Path) -> None:
    # pascal_title has no meaning at file level: there is no step in scope.
    broken = {**BASE, "outputs": [{"path": "o_{pascal_title}.cpp", "template": "t.j2"}]}
    directory = _write_device(tmp_path, "d1", broken)
    with pytest.raises(ManifestError, match="pascal_title"):
        load_manifest(directory)


def test_manifest_rejects_anchor_marker_without_name(tmp_path: Path) -> None:
    broken = {**BASE, "anchor": {"begin": "// BEGIN", "end": "// END"}}
    directory = _write_device(tmp_path, "d1", broken)
    with pytest.raises(ManifestError, match="schema"):
        load_manifest(directory)


def test_manifest_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    directory = _write_device(tmp_path, "d1", {**BASE, "typo": 1})
    with pytest.raises(ManifestError, match="schema"):
        load_manifest(directory)
