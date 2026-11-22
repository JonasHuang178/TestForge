"""The orchestrator both the API and the CLI call.

Everything the web layer does goes through here. ``api/`` and ``web/`` depend
on this module and never on each other, and neither of them re-enters the
application over HTTP.
"""

from __future__ import annotations

import uuid

from testforge.core.assembler import inject
from testforge.core.diagnostics import DiagnosticCollector
from testforge.core.errors import UnprocessableDocumentError
from testforge.core.fragments import build_context, output_view, step_views
from testforge.core.models import (
    ExistingFile,
    GeneratedArtifact,
    GenerationResult,
    GenerationSummary,
    ParseResult,
    TestCase,
)
from testforge.core.naming import StepNamer, case_fields
from testforge.core.options import GenerateOptions, ParseOptions
from testforge.core.parser import MarkdownTestPlanParser
from testforge.core.templating import render
from testforge.devices.manifest import AnchorStyle, DeviceManifest
from testforge.devices.registry import DeviceRegistry, LoadedDevice

_PARSE_KEYS = frozenset(ParseOptions.model_fields)

#: Python devices do not declare their marker spelling; one spelling for all of
#: them keeps a template copied between devices working unchanged.
PYTHON_DEVICE_ANCHOR = AnchorStyle()


class GenerationService:
    def __init__(
        self,
        registry: DeviceRegistry,
        parser: MarkdownTestPlanParser | None = None,
    ) -> None:
        self._registry = registry
        self._parser = parser or MarkdownTestPlanParser()

    @property
    def registry(self) -> DeviceRegistry:
        return self._registry

    # -- parse -------------------------------------------------------------

    def parse(
        self,
        source: str,
        options: ParseOptions | None = None,
        device_id: str | None = None,
    ) -> ParseResult:
        """Read a plan without generating anything.

        ``device_id`` is optional and only used to pick up that device's
        heading conventions, so the preview matches what generation will see.
        """
        effective = options or ParseOptions()
        if device_id is not None:
            effective = self._merge_parse_options(
                self._registry.get(device_id).parse_options, options
            )
        return self._parser.parse(source, effective)

    # -- generate ----------------------------------------------------------

    def generate(
        self,
        source: str,
        device_id: str,
        options: GenerateOptions | None = None,
        existing_files: list[ExistingFile] | None = None,
    ) -> GenerationResult:
        device = self._registry.get(device_id)
        effective = self._merge_generate_options(device, options)

        diag = DiagnosticCollector()
        parsed = self._parser.parse(source, effective, diag)

        if diag.has_errors or not parsed.cases:
            raise UnprocessableDocumentError(
                "The test plan could not be turned into any test case.",
                diagnostics=diag.items,
            )

        cases = list(parsed.cases)
        if effective.case_selector is not None:
            if effective.case_selector > len(cases):
                diag.error(
                    "case_selector.out_of_range",
                    f"Requested case {effective.case_selector} but the document "
                    f"contains {len(cases)}.",
                )
                raise UnprocessableDocumentError(
                    f"Case {effective.case_selector} does not exist in this document.",
                    diagnostics=diag.items,
                )
            cases = [cases[effective.case_selector - 1]]

        existing = {f.path: f.content for f in (existing_files or [])}
        artifacts: list[GeneratedArtifact] = []
        functions: list[str] = []
        seen_paths: dict[str, int] = {}

        for case in cases:
            case_artifacts, case_functions = self._generate_case(
                device, case, effective, existing, diag, seen_paths
            )
            artifacts.extend(case_artifacts)
            functions.extend(case_functions)

        return GenerationResult(
            generation_id=f"gen_{uuid.uuid4().hex[:24]}",
            device_id=device.id,
            artifacts=tuple(artifacts),
            summary=GenerationSummary(
                cases=len(cases),
                steps=sum(len(c.steps) for c in cases),
                functions=tuple(functions),
            ),
            diagnostics=tuple(diag.items),
        )

    # -- internals ---------------------------------------------------------

    def _generate_case(
        self,
        device: LoadedDevice,
        case: TestCase,
        options: GenerateOptions,
        existing: dict[str, str],
        diag: DiagnosticCollector,
        seen_paths: dict[str, int],
    ) -> tuple[list[GeneratedArtifact], list[str]]:
        if device.python is not None:
            return self._generate_case_python(device, case, existing, diag, seen_paths)
        manifest = device.manifest
        pattern = options.naming_pattern or manifest.naming.step_function
        namer = StepNamer(pattern, case, device.id, diag)
        steps = step_views(case, namer)
        fields = case_fields(case, device.id)

        resolved = [
            output_view(spec.path.format(**fields)) for spec in manifest.outputs
        ]

        artifacts: list[GeneratedArtifact] = []
        for spec, view in zip(manifest.outputs, resolved):
            path = view["path"]
            if path in seen_paths:
                diag.warning(
                    "output.path_collision",
                    f"Case {case.index} writes {path!r}, which case "
                    f"{seen_paths[path]} already produced; the later one wins.",
                    line=case.source_line,
                    case_index=case.index,
                )
            seen_paths[path] = case.index

            context = build_context(
                device_id=device.id,
                device_name=manifest.name,
                case=case,
                steps=steps,
                current_output=view,
                all_outputs=resolved,
            )

            base = existing.get(path)
            mode = "updated" if base is not None else "created"
            if base is None:
                base = render(device.environment, spec.template, context)

            fragments = {
                anchor: render(device.environment, template, context)
                for anchor, template in spec.fragments.items()
            }
            content, filled = inject(base, fragments, manifest.anchor)

            artifacts.append(
                GeneratedArtifact(
                    path=path, content=content, mode=mode, anchors_filled=filled
                )
            )

        return artifacts, [str(s["function_name"]) for s in steps]

    def _generate_case_python(
        self,
        device: LoadedDevice,
        case: TestCase,
        existing: dict[str, str],
        diag: DiagnosticCollector,
        seen_paths: dict[str, int],
    ) -> tuple[list[GeneratedArtifact], list[str]]:
        """Generate one case with a device whose rules are written in Python.

        The device decides the filenames, the function names and the code; the
        framework still owns anchor injection, so idempotent regeneration and
        line-ending preservation hold whatever the device does.
        """
        python = device.python
        info = python.case_info(case)
        outputs = python.build(info)

        artifacts: list[GeneratedArtifact] = []
        for spec in outputs:
            path = spec.path
            if path in seen_paths:
                diag.warning(
                    "output.path_collision",
                    f"Case {case.index} writes {path!r}, which case "
                    f"{seen_paths[path]} already produced; the later one wins.",
                    line=case.source_line,
                    case_index=case.index,
                )
            seen_paths[path] = case.index

            base = existing.get(path)
            mode = "updated" if base is not None else "created"
            if base is None:
                base = spec.skeleton

            content, filled = inject(base, spec.anchors, PYTHON_DEVICE_ANCHOR)
            artifacts.append(
                GeneratedArtifact(
                    path=path, content=content, mode=mode, anchors_filled=filled
                )
            )

        return artifacts, [s.function_name for s in info.steps]

    @staticmethod
    def _merge_parse_options(
        parse_defaults: ParseOptions, options: ParseOptions | None
    ) -> ParseOptions:
        merged = parse_defaults.model_dump()
        if options is not None:
            provided = options.model_dump(exclude_unset=True)
            merged.update({k: v for k, v in provided.items() if k in _PARSE_KEYS})
        return ParseOptions(**merged)

    @classmethod
    def _merge_generate_options(
        cls, device: LoadedDevice, options: GenerateOptions | None
    ) -> GenerateOptions:
        """Device manifest supplies the defaults; the request overrides them.

        Only fields the caller actually sent are treated as overrides, so an
        unset field falls back to the manifest rather than to the schema
        default.
        """
        base = cls._merge_parse_options(device.parse_options, options).model_dump()
        provided = {} if options is None else options.model_dump(exclude_unset=True)
        default_pattern = (
            device.manifest.naming.step_function if device.manifest else None
        )
        return GenerateOptions(
            **base,
            naming_pattern=provided.get("naming_pattern") or default_pattern,
            case_selector=provided.get("case_selector"),
        )
