"""The device manifest schema.

A manifest is the whole contract for one device: how to read its test plans,
how to name the functions it generates, what its anchor markers look like, and
which files come out. Everything is validated at load time so a typo fails
when the service starts rather than on a user's first request.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from testforge.core.errors import ManifestError, NamingPatternError
from testforge.core.naming import (
    DEFAULT_STEP_PATTERN,
    validate_path_pattern,
    validate_pattern,
)
from testforge.core.options import ParseOptions

MANIFEST_FILENAME = "manifest.yaml"
TEMPLATE_DIRNAME = "templates"


class AnchorStyle(BaseModel):
    """How a begin/end marker pair is spelled in this device's templates.

    Paired markers (rather than a single insertion point) are what make
    regeneration idempotent: everything between the two lines is replaced, so
    running the generator twice produces the same file.
    """

    model_config = ConfigDict(extra="forbid")

    begin: str = "// === TESTFORGE:{name}:BEGIN ==="
    end: str = "// === TESTFORGE:{name}:END ==="

    @field_validator("begin", "end")
    @classmethod
    def _must_contain_name(cls, v: str) -> str:
        if "{name}" not in v:
            raise ValueError("anchor marker must contain the {name} placeholder")
        return v

    def begin_marker(self, name: str) -> str:
        return self.begin.format(name=name)

    def end_marker(self, name: str) -> str:
        return self.end.format(name=name)


class OutputSpec(BaseModel):
    """One file this device produces."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Filename pattern, e.g. test_{case_snake}.cpp")
    template: str = Field(description="Skeleton template, relative to templates/")
    fragments: dict[str, str] = Field(
        default_factory=dict,
        description="anchor name -> fragment template rendered into it",
    )


class NamingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_function: str = DEFAULT_STEP_PATTERN


class DeviceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    name: str
    description: str = ""
    version: int = 1
    parse: ParseOptions = Field(default_factory=ParseOptions)
    naming: NamingSpec = Field(default_factory=NamingSpec)
    anchor: AnchorStyle = Field(default_factory=AnchorStyle)
    outputs: list[OutputSpec] = Field(min_length=1)

    @property
    def anchor_names(self) -> list[str]:
        seen: list[str] = []
        for output in self.outputs:
            for name in output.fragments:
                if name not in seen:
                    seen.append(name)
        return seen


def load_manifest(directory: Path) -> DeviceManifest:
    """Read and fully validate the manifest in ``directory``."""
    path = directory / MANIFEST_FILENAME
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"Cannot read {path}: {exc}", details={"path": str(path)}) from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path} is not valid YAML: {exc}", details={"path": str(path)}) from exc

    if not isinstance(raw, dict):
        raise ManifestError(
            f"{path} must contain a YAML mapping at the top level",
            details={"path": str(path)},
        )

    try:
        manifest = DeviceManifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestError(
            f"{path} does not match the manifest schema: {exc.error_count()} problem(s)",
            details={"path": str(path), "errors": exc.errors(include_url=False)},
        ) from exc

    if manifest.id != directory.name:
        raise ManifestError(
            f"Manifest id {manifest.id!r} does not match its directory name "
            f"{directory.name!r}; keep them identical so devices are easy to find.",
            details={"path": str(path)},
        )

    template_root = directory / TEMPLATE_DIRNAME
    try:
        validate_pattern(manifest.naming.step_function)
        for output in manifest.outputs:
            validate_path_pattern(output.path)
    except NamingPatternError as exc:
        raise ManifestError(f"{path}: {exc.message}", details={**exc.details, "path": str(path)}) from exc

    missing: list[str] = []
    for output in manifest.outputs:
        for rel in [output.template, *output.fragments.values()]:
            if not (template_root / rel).is_file():
                missing.append(rel)
    if missing:
        raise ManifestError(
            f"{path} references template file(s) that do not exist under "
            f"{template_root}: {', '.join(sorted(set(missing)))}",
            details={"path": str(path), "missing": sorted(set(missing))},
        )

    return manifest
