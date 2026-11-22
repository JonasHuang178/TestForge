"""Loading a device written in Python.

A device folder holding ``device.py`` is imported and checked when the registry
loads, so a broken device stops startup instead of failing someone's first
request — the same contract the declarative devices have.

Importing a device runs its module, exactly as a test suite runs conftest.py.
Device folders are project code, not untrusted input.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from testforge.core.assembler import DEFAULT_ANCHOR_STYLE, AnchorStyle
from testforge.core.errors import DeviceDefinitionError, TemplateRenderError
from testforge.core.options import ParseOptions
from testforge.device_api import CaseInfo, OutputFile, StepInfo
from testforge.core.models import TestCase

DEVICE_MODULE = "device.py"

#: Substituted when a template is first used. Chosen so it cannot collide with
#: C or C++ syntax, unlike braces.
_VARIABLE_RE = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")

_REQUIRED = ("ID", "NAME", "step_function_name")


@dataclass(frozen=True)
class ResolvedOutput:
    """One output file, with everything needed to write or update it."""

    path: str
    anchors: dict[str, str]
    skeleton: str
    """The template with its variables filled in. Used only when the file does
    not already exist."""


class PythonDevice:
    """A device whose rules live in a Python module."""

    def __init__(self, module: ModuleType, directory: Path) -> None:
        self._module = module
        self._directory = directory
        self.id: str = module.ID
        self.name: str = module.NAME
        self.description: str = getattr(module, "DESCRIPTION", "")
        self.version: int = int(getattr(module, "VERSION", 1))
        section_level = getattr(module, "SECTION_HEADING_LEVEL", None)
        self.parse_options = ParseOptions(
            case_heading_level=int(getattr(module, "CASE_HEADING_LEVEL", 1)),
            step_heading_level=int(getattr(module, "STEP_HEADING_LEVEL", 2)),
            case_section=getattr(module, "CASE_SECTION", None),
            section_heading_level=int(section_level) if section_level else None,
            step_style=getattr(module, "STEP_STYLE", "heading"),
            case_table=bool(getattr(module, "CASE_TABLE", False)),
        )
        # A device emitting C89, where // is not a comment, can declare a
        # block-comment marker instead.
        self.anchor_style = AnchorStyle(
            begin=getattr(module, "ANCHOR_BEGIN", DEFAULT_ANCHOR_STYLE.begin),
            end=getattr(module, "ANCHOR_END", DEFAULT_ANCHOR_STYLE.end),
        )

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def example_plan(self) -> str | None:
        """A sample plan shipped with the device, if it declares one.

        Lets the page offer an example that matches the selected device rather
        than one fixed sample that only parses under one device's conventions.
        """
        name = getattr(self._module, "EXAMPLE_PLAN", None)
        if not name:
            return None
        path = self._directory / name
        if not path.is_file():
            return None
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()

    @property
    def builds_whole_plan(self) -> bool:
        """True when the module writes every case into the same file(s).

        Such a device defines ``build_all(cases)`` and is called once with the
        whole plan; the per-case ``build(case)`` cannot express it, because a
        later case would overwrite the anchored region an earlier one filled.
        """
        return hasattr(self._module, "build_all")

    # -- generation --------------------------------------------------------

    def case_info(self, case: TestCase) -> CaseInfo:
        """Turn the IR into the device-facing view, naming each step on the way."""
        steps: list[StepInfo] = []
        for step in case.steps:
            bare = StepInfo(
                index=step.index,
                title=step.title,
                declared_index=step.declared_index,
                description_md=step.description_md,
                expected=step.expected,
                source_line=step.source_line,
                function_name="",
            )
            try:
                name = self._module.step_function_name(bare)
            except Exception as exc:
                raise TemplateRenderError(
                    f"Device {self.id!r}: step_function_name() failed on step "
                    f"{step.index} ({step.title!r}): {exc}",
                    details={"device": self.id, "step": step.index},
                ) from exc
            if not isinstance(name, str) or not name:
                raise TemplateRenderError(
                    f"Device {self.id!r}: step_function_name() must return a "
                    f"non-empty string; got {name!r} for step {step.index}.",
                    details={"device": self.id, "step": step.index},
                )
            steps.append(
                StepInfo(
                    index=bare.index,
                    title=bare.title,
                    declared_index=bare.declared_index,
                    description_md=bare.description_md,
                    expected=bare.expected,
                    source_line=bare.source_line,
                    function_name=name,
                )
            )

        return CaseInfo(
            index=case.index,
            title=case.title,
            case_id=case.case_id,
            metadata=dict(case.metadata),
            description_md=case.description_md,
            steps=tuple(steps),
            source_line=case.source_line,
            device_id=self.id,
        )

    def build(self, info: CaseInfo) -> list[ResolvedOutput]:
        """One case -> its files. For a device that defines ``build``."""
        return self._invoke(
            self._module.build,
            (info,),
            "build",
            f"case {info.index} ({info.title!r})",
        )

    def build_plan(self, infos: list[CaseInfo]) -> list[ResolvedOutput]:
        """Every case -> the files holding them all. For ``build_all``."""
        return self._invoke(
            self._module.build_all, (tuple(infos),), "build_all", "the plan"
        )

    def _invoke(self, func, args, name: str, what: str) -> list[ResolvedOutput]:
        try:
            produced = func(*args)
        except Exception as exc:
            raise TemplateRenderError(
                f"Device {self.id!r}: {name}() failed for {what}: {exc}",
                details={"device": self.id},
            ) from exc

        if not isinstance(produced, (list, tuple)) or not produced:
            raise TemplateRenderError(
                f"Device {self.id!r}: {name}() must return a non-empty list of "
                f"OutputFile; got {type(produced).__name__}.",
                details={"device": self.id},
            )

        resolved: list[ResolvedOutput] = []
        for item in produced:
            if not isinstance(item, OutputFile):
                raise TemplateRenderError(
                    f"Device {self.id!r}: {name}() returned "
                    f"{type(item).__name__}, expected OutputFile "
                    f"(use device_api.output()).",
                    details={"device": self.id},
                )
            resolved.append(
                ResolvedOutput(
                    path=item.path,
                    anchors=dict(item.anchors),
                    skeleton=self._render_template(item),
                )
            )
        return resolved

    def _render_template(self, item: OutputFile) -> str:
        if item.content is not None:
            # The module built the skeleton itself; variables still apply so
            # it can mix the two.
            return self._substitute(item, item.content)

        path = self._directory / item.template
        if not path.is_file():
            raise TemplateRenderError(
                f"Device {self.id!r}: template {item.template!r} does not exist "
                f"in {self._directory}.",
                details={"device": self.id, "template": item.template},
            )
        # newline="" so a CRLF template is not silently normalised before the
        # assembler gets a chance to honour it.
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        return self._substitute(item, text)

    def _substitute(self, item: OutputFile, text: str) -> str:
        missing: list[str] = []

        def substitute(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in item.variables:
                missing.append(key)
                return match.group(0)
            return item.variables[key]

        rendered = _VARIABLE_RE.sub(substitute, text)
        if missing:
            where = item.template or "the content build() supplied"
            raise TemplateRenderError(
                f"Device {self.id!r}: {where} uses "
                f"@@{'@@, @@'.join(sorted(set(missing)))}@@ but build() "
                f"supplied no value for it.",
                details={"device": self.id, "template": item.template, "missing": sorted(set(missing))},
            )
        return rendered


def load_python_device(directory: Path) -> PythonDevice:
    """Import ``<directory>/device.py`` and check its contract."""
    path = directory / DEVICE_MODULE
    module_name = f"testforge_device_{directory.name}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise DeviceDefinitionError(
            f"Cannot load {path} as a Python module.", details={"path": str(path)}
        )
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so the module can import itself by name and
    # so tracebacks from inside it resolve.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise DeviceDefinitionError(
            f"{path} raised {type(exc).__name__} while being imported: {exc}",
            details={"path": str(path)},
        ) from exc

    missing = [attr for attr in _REQUIRED if not hasattr(module, attr)]
    if missing:
        raise DeviceDefinitionError(
            f"{path} does not define {', '.join(missing)}. A device module must "
            f"define ID, NAME, step_function_name(step) and build(case).",
            details={"path": str(path), "missing": missing},
        )
    entry_points = [a for a in ("build", "build_all") if hasattr(module, a)]
    if len(entry_points) != 1:
        raise DeviceDefinitionError(
            f"{path} must define exactly one of build(case) or "
            f"build_all(cases); it defines "
            f"{', '.join(entry_points) if entry_points else 'neither'}. Use "
            f"build(case) when each case gets its own file, build_all(cases) "
            f"when they all go into the same one.",
            details={"path": str(path), "defines": entry_points},
        )
    for attr in ("step_function_name", *entry_points):
        if not callable(getattr(module, attr)):
            raise DeviceDefinitionError(
                f"{path}: {attr} must be a function.",
                details={"path": str(path)},
            )
    if module.ID != directory.name:
        raise DeviceDefinitionError(
            f"{path}: ID is {module.ID!r} but the folder is named "
            f"{directory.name!r}; keep them identical so devices stay findable.",
            details={"path": str(path)},
        )

    return PythonDevice(module, directory)
