"""Markdown test plan -> IR.

Headings are located with markdown-it's token stream rather than line regexes,
so a ``#`` inside a fenced code block cannot be mistaken for a heading. Step
bodies are then sliced out of the original source by line number, which keeps
the author's markdown byte-for-byte instead of round-tripping it through an
AST renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from markdown_it import MarkdownIt

from testforge.core.diagnostics import DiagnosticCollector
from testforge.core.models import ParseResult, TestCase, TestStep
from testforge.core.options import ParseOptions

#: Two spellings, kept separate on purpose.
#:
#: With the word "Step" the number may be followed by nothing but a space
#: (`Step 1 Print the version`). Without it, an explicit separator is required
#: (`3. Title`), because a bare leading number otherwise swallows titles such
#: as "2024 annual check".
_STEP_TITLE_RE = re.compile(
    r"^\s*(?:(?:step|steps|步驟|步骤)\s*(\d+)\s*(?:[:.)\-–—：]\s*|\s+|$)"
    r"|(\d+)\s*[:.)\-–—：]\s*)(.*)$",
    re.IGNORECASE,
)

#: `- ID: TC-001`, `* **Author:** Jonas`, `- 裝置：foo`
_METADATA_RE = re.compile(
    r"^\s*[-*+]\s+\*{0,2}\s*([^:：*]{1,40}?)\s*\*{0,2}\s*[:：]\s*(.+?)\s*$"
)

#: The label that opens an expectation paragraph.
_EXPECTED_LABEL = r"expected(?:\s+results?)?|預期結果|預期|期望結果"

#: Matches `**Expected:** ...`, `**Expected**: ...`, `Expected result: ...`,
#: `預期結果：...`. The three bold spellings are listed separately on purpose:
#: a single optional `\*{0,2}` after the colon would swallow the opening `**`
#: of an expectation whose own text starts bold.
_EXPECTED_RE = re.compile(
    r"^\s*(?:"
    rf"\*\*\s*(?:{_EXPECTED_LABEL})\s*[:：]\s*\*\*"
    rf"|\*\*\s*(?:{_EXPECTED_LABEL})\s*\*\*\s*[:：]"
    rf"|(?:{_EXPECTED_LABEL})\s*[:：]"
    r")\s*(.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Heading:
    level: int
    text: str
    line: int  # 0-based index of the heading line
    body_start: int  # 0-based index of the first line after the heading


class MarkdownTestPlanParser:
    """Parses the canonical markdown test plan format.

    The format is deliberately thin:

    * ``# Test Case: <title>`` starts a case. Several per document is fine.
    * An optional bullet list directly under it is metadata (``Key: Value``).
    * ``## Step N: <title>`` starts a step. ``Step``/``N`` are both optional;
      without a number, steps are indexed by position.
    * A paragraph beginning ``Expected:`` becomes the step's expectation;
      everything else in the step is its description.
    """

    def __init__(self) -> None:
        # commonmark preset: no unexpected plugin syntax, predictable tokens.
        self._md = MarkdownIt("commonmark")

    def parse(
        self,
        source: str,
        options: ParseOptions | None = None,
        diagnostics: DiagnosticCollector | None = None,
    ) -> ParseResult:
        opts = options or ParseOptions()
        diag = diagnostics if diagnostics is not None else DiagnosticCollector()
        lines = source.splitlines()
        headings = self._headings(source, lines)

        scan_from, scan_to = 0, len(lines)
        if opts.case_section is not None:
            bounds = self._section_bounds(headings, opts, len(lines))
            if bounds is None:
                level = opts.section_heading_level or max(1, opts.case_heading_level - 1)
                diag.error(
                    "document.section_not_found",
                    f"No level-{level} heading titled {opts.case_section!r} was "
                    f"found, so there is nowhere to look for test cases.",
                )
                return ParseResult(cases=(), diagnostics=tuple(diag.items))
            scan_from, scan_to = bounds

        case_headings = [
            h
            for h in headings
            if scan_from <= h.line < scan_to
            and h.level == opts.case_heading_level
            and self._is_case_heading(h.text, opts)
        ]

        if not case_headings:
            diag.error(
                "document.no_test_case",
                f"No test case heading found. Expected a level-"
                f"{opts.case_heading_level} heading"
                + (
                    f" starting with one of: {', '.join(opts.case_prefixes)}."
                    if opts.require_case_prefix
                    else "."
                ),
            )
            return ParseResult(cases=(), diagnostics=tuple(diag.items))

        first_case_line = case_headings[0].line
        # Pointless when a section is configured: content before the section is
        # exactly what `case_section` exists to allow.
        if opts.case_section is None and any(
            h.line < first_case_line and h.level >= opts.case_heading_level
            for h in headings
        ):
            diag.warning(
                "document.content_before_case",
                "Headings appear before the first test case heading; they are "
                "ignored.",
                line=1,
            )

        cases: list[TestCase] = []
        seen_titles: dict[str, int] = {}
        for ordinal, heading in enumerate(case_headings, start=1):
            end = min(
                self._next_boundary(headings, heading, opts.case_heading_level, len(lines)),
                scan_to,
            )
            case = self._build_case(ordinal, heading, end, lines, headings, opts, diag)
            if not case.steps:
                diag.warning(
                    "case.no_steps",
                    f"Test case {case.title!r} has no level-"
                    f"{opts.step_heading_level} step headings; it is skipped.",
                    line=heading.line + 1,
                    case_index=ordinal,
                )
                continue
            if case.title in seen_titles:
                diag.warning(
                    "case.duplicate_title",
                    f"Test case title {case.title!r} already used by case "
                    f"{seen_titles[case.title]}; output filenames may collide.",
                    line=heading.line + 1,
                    case_index=ordinal,
                )
            else:
                seen_titles[case.title] = ordinal
            cases.append(case)

        if not cases:
            diag.error(
                "document.no_usable_case",
                "Every test case in the document was skipped; nothing can be "
                "generated.",
            )

        return ParseResult(cases=tuple(cases), diagnostics=tuple(diag.items))

    # -- internals ---------------------------------------------------------

    def _headings(self, source: str, lines: list[str]) -> list[_Heading]:
        tokens = self._md.parse(source)
        headings: list[_Heading] = []
        for i, token in enumerate(tokens):
            if token.type != "heading_open" or token.map is None:
                continue
            level = int(token.tag[1:])
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text = (inline.content if inline is not None and inline.type == "inline" else "").strip()
            start = token.map[0]
            # Setext headings ("Title\n=====") span two lines; the body starts
            # after the underline, which token.map already accounts for.
            body_start = token.map[1] if token.map[1] > start else start + 1
            headings.append(_Heading(level=level, text=text, line=start, body_start=body_start))
        return headings

    @staticmethod
    def _section_bounds(
        headings: list[_Heading], opts: ParseOptions, eof: int
    ) -> tuple[int, int] | None:
        """Line range (0-based, end exclusive) of the section holding the cases."""
        level = opts.section_heading_level or max(1, opts.case_heading_level - 1)
        wanted = opts.case_section.strip().casefold()
        for i, heading in enumerate(headings):
            if heading.level != level or heading.text.strip().casefold() != wanted:
                continue
            end = eof
            for later in headings[i + 1 :]:
                if later.level <= level:
                    end = later.line
                    break
            return heading.body_start, end
        return None

    @staticmethod
    def _is_case_heading(text: str, opts: ParseOptions) -> bool:
        if not opts.require_case_prefix:
            return True
        lowered = text.lower()
        return any(lowered.startswith(p.lower()) for p in opts.case_prefixes)

    @staticmethod
    def _strip_case_prefix(text: str, opts: ParseOptions) -> str:
        for prefix in opts.case_prefixes:
            if text.lower().startswith(prefix.lower()):
                return text[len(prefix) :].lstrip(" :：-–—").strip() or text.strip()
        return text.strip()

    @staticmethod
    def _next_boundary(
        headings: list[_Heading], current: _Heading, max_level: int, eof: int
    ) -> int:
        """First line (0-based, exclusive) at which ``current``'s region ends."""
        for h in headings:
            if h.line > current.line and h.level <= max_level:
                return h.line
        return eof

    def _build_case(
        self,
        ordinal: int,
        heading: _Heading,
        end: int,
        lines: list[str],
        headings: list[_Heading],
        opts: ParseOptions,
        diag: DiagnosticCollector,
    ) -> TestCase:
        step_headings = [
            h
            for h in headings
            if heading.line < h.line < end and h.level == opts.step_heading_level
        ]
        preamble_end = step_headings[0].line if step_headings else end
        metadata, description = self._split_preamble(
            lines[heading.body_start : preamble_end], heading.body_start, ordinal, diag
        )

        steps: list[TestStep] = []
        for position, step_heading in enumerate(step_headings, start=1):
            step_end = self._next_boundary(
                [h for h in headings if h.line < end],
                step_heading,
                opts.step_heading_level,
                end,
            )
            steps.append(
                self._build_step(
                    position, step_heading, step_end, lines, ordinal, diag
                )
            )

        return TestCase(
            index=ordinal,
            title=self._strip_case_prefix(heading.text, opts),
            metadata=metadata,
            description_md=description,
            steps=tuple(steps),
            source_line=heading.line + 1,
        )

    def _split_preamble(
        self,
        body: list[str],
        offset: int,
        case_index: int,
        diag: DiagnosticCollector,
    ) -> tuple[dict[str, str], str]:
        """Pull the leading `Key: Value` bullet list out of the case preamble."""
        metadata: dict[str, str] = {}
        rest: list[str] = []
        in_metadata_block = True
        for i, line in enumerate(body):
            stripped = line.strip()
            if not stripped:
                rest.append(line)
                continue
            is_bullet = bool(re.match(r"^\s*[-*+]\s+", line))
            if in_metadata_block and is_bullet:
                match = _METADATA_RE.match(line)
                if match:
                    key = re.sub(r"\s+", "_", match.group(1).strip().lower())
                    metadata[key] = match.group(2).strip()
                else:
                    diag.info(
                        "metadata.unparsed_line",
                        f"Bullet in the case preamble is not a `Key: Value` "
                        f"entry and is kept as description: {stripped!r}",
                        line=offset + i + 1,
                        case_index=case_index,
                    )
                    rest.append(line)
                continue
            if is_bullet and not metadata:
                # A bullet list further down is ordinary prose.
                in_metadata_block = False
            elif not is_bullet:
                in_metadata_block = False
            rest.append(line)
        return metadata, "\n".join(rest).strip()

    def _build_step(
        self,
        position: int,
        heading: _Heading,
        end: int,
        lines: list[str],
        case_index: int,
        diag: DiagnosticCollector,
    ) -> TestStep:
        declared_index: int | None = None
        title = heading.text
        match = _STEP_TITLE_RE.match(heading.text)
        if match:
            declared_index = int(match.group(1) or match.group(2))
            title = match.group(3).strip() or heading.text.strip()

        if declared_index is not None and declared_index != position:
            diag.warning(
                "step.index_mismatch",
                f"Step is numbered {declared_index} in the plan but is at "
                f"position {position}; the generated name uses {position}.",
                line=heading.line + 1,
                case_index=case_index,
                step_index=position,
            )

        body = "\n".join(lines[heading.body_start : end]).strip()
        description, expected = self._split_expected(body)

        if not description:
            diag.warning(
                "step.empty_description",
                f"Step {position} ({title!r}) has no description body; the "
                f"generated function will only carry a TODO.",
                line=heading.line + 1,
                case_index=case_index,
                step_index=position,
            )
        if expected is None:
            diag.info(
                "step.no_expected",
                f"Step {position} ({title!r}) declares no `Expected:` block; "
                f"no assertion scaffold will be emitted.",
                line=heading.line + 1,
                case_index=case_index,
                step_index=position,
            )

        return TestStep(
            index=position,
            declared_index=declared_index,
            title=title,
            description_md=description,
            expected=expected,
            source_line=heading.line + 1,
        )

    @staticmethod
    def _split_expected(body: str) -> tuple[str, str | None]:
        """Separate the Expected paragraph from the rest of the step body."""
        lines = body.splitlines()
        for i, line in enumerate(lines):
            match = _EXPECTED_RE.match(line)
            if not match:
                continue
            collected = [match.group(1).strip()]
            j = i + 1
            while j < len(lines) and lines[j].strip():
                collected.append(lines[j].strip())
                j += 1
            remainder = lines[:i] + lines[j:]
            expected = " ".join(part for part in collected if part).strip()
            return "\n".join(remainder).strip(), (expected or None)
        return body.strip(), None
