"""Turning human step titles into C++ identifiers.

The default pattern is index-prefixed (``TestStep_01_InitializeDevice``)
because it keeps names stable when a title is reworded, preserves the order of
the plan in the generated file, and is unique without dedup suffixes.
"""

from __future__ import annotations

import re
import string
import unicodedata

from testforge.core.diagnostics import DiagnosticCollector
from testforge.core.errors import NamingPatternError
from testforge.core.models import TestCase, TestStep

#: Reserved words (C++20) plus a few names that collide with common macros.
CPP_RESERVED = frozenset(
    """
    alignas alignof and and_eq asm atomic_cancel atomic_commit atomic_noexcept
    auto bitand bitor bool break case catch char char8_t char16_t char32_t
    class compl concept const consteval constexpr constinit const_cast
    continue co_await co_return co_yield decltype default delete do double
    dynamic_cast else enum explicit export extern false float for friend goto
    if inline int long mutable namespace new noexcept not not_eq nullptr
    operator or or_eq private protected public register reinterpret_cast
    requires return short signed sizeof static static_assert static_cast
    struct switch template this thread_local throw true try typedef typeid
    typename union unsigned using virtual void volatile wchar_t while xor
    xor_eq NULL TRUE FALSE
    """.split()
)

DEFAULT_STEP_PATTERN = "TestStep_{index:02d}_{pascal_title}"

_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z]+")
_FIELD_RE = re.compile(r"\{([a-z_]+)(?:![rsa])?(?::[^}]*)?\}")

#: Placeholders a manifest may use in a naming pattern.
KNOWN_FIELDS = frozenset(
    {
        "index",
        "declared_index",
        "pascal_title",
        "snake_title",
        "camel_title",
        "upper_title",
        "case_index",
        "case_pascal",
        "case_snake",
        "case_id",
        "device_id",
    }
)


def _ascii_tokens(text: str) -> list[str]:
    """Split text into ASCII alphanumeric tokens.

    Accented Latin characters are folded (``Prüfung`` -> ``Prufung``).
    Characters with no ASCII equivalent, CJK in particular, simply drop out;
    the caller is expected to notice an empty result and report it.
    """
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    ascii_only = "".join(c if c in string.printable else " " for c in folded)
    return [t for t in _TOKEN_SPLIT.split(ascii_only) if t]


def to_pascal(text: str) -> str:
    parts = []
    for token in _ascii_tokens(text):
        # Keep acronyms intact: "ADC read" -> "ADCRead", not "AdcRead".
        parts.append(token if token.isupper() and len(token) > 1 else token[:1].upper() + token[1:])
    return "".join(parts)


def to_snake(text: str) -> str:
    return "_".join(t.lower() for t in _ascii_tokens(text))


def to_camel(text: str) -> str:
    pascal = to_pascal(text)
    return pascal[:1].lower() + pascal[1:] if pascal else ""


def to_upper_snake(text: str) -> str:
    return to_snake(text).upper()


def sanitize_identifier(name: str) -> str:
    """Make ``name`` a legal, non-reserved C++ identifier."""
    cleaned = re.sub(r"[^0-9A-Za-z_]", "", name)
    if not cleaned:
        cleaned = "Unnamed"
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    if cleaned in CPP_RESERVED:
        cleaned += "_"
    return cleaned


def validate_pattern(pattern: str) -> None:
    """Reject a naming pattern that references unknown placeholders.

    Called when a manifest is loaded, so a typo fails at startup rather than
    at the first generation request.
    """
    unknown = {m.group(1) for m in _FIELD_RE.finditer(pattern)} - KNOWN_FIELDS
    if unknown:
        raise NamingPatternError(
            f"Naming pattern references unknown placeholder(s): "
            f"{', '.join(sorted(unknown))}",
            details={"pattern": pattern, "known_fields": sorted(KNOWN_FIELDS)},
        )


#: The subset of placeholders usable in an output *path* pattern, where no
#: step is in scope yet.
PATH_FIELDS = frozenset({"case_index", "case_pascal", "case_snake", "case_id", "device_id"})


def validate_path_pattern(pattern: str) -> None:
    """Reject an output path pattern that references step-level placeholders."""
    used = {m.group(1) for m in _FIELD_RE.finditer(pattern)}
    unknown = used - PATH_FIELDS
    if unknown:
        raise NamingPatternError(
            f"Output path pattern references placeholder(s) not available at "
            f"file level: {', '.join(sorted(unknown))}",
            details={"pattern": pattern, "known_fields": sorted(PATH_FIELDS)},
        )


def case_fields(case: TestCase, device_id: str) -> dict[str, object]:
    """Placeholder values that depend only on the case, not on a step."""
    return {
        "case_index": case.index,
        "case_pascal": to_pascal(case.title) or f"Case{case.index}",
        "case_snake": to_snake(case.title) or f"case{case.index}",
        "case_id": case.case_id or f"case_{case.index}",
        "device_id": device_id,
    }


class StepNamer:
    """Names every step of one case, keeping the results unique.

    One instance per case: duplicate titles within a case get a numeric
    suffix, while the same title in a different case is free to repeat.
    """

    def __init__(
        self,
        pattern: str,
        case: TestCase,
        device_id: str,
        diagnostics: DiagnosticCollector | None = None,
    ) -> None:
        validate_pattern(pattern)
        self._pattern = pattern
        self._case = case
        self._case_fields = case_fields(case, device_id)
        self._diagnostics = diagnostics
        self._used: dict[str, int] = {}

    def name_for(self, step: TestStep) -> str:
        pascal = to_pascal(step.title)
        if not pascal and self._diagnostics is not None:
            # Almost always a CJK or symbol-only title. Generating
            # Step<n> keeps the file compiling; the diagnostic tells the
            # author why the name looks unhelpful.
            self._diagnostics.warning(
                "naming.title_not_representable",
                f"Step {step.index} title {step.title!r} contains no characters "
                f"usable in a C++ identifier; falling back to a positional name.",
                line=step.source_line,
                case_index=self._case.index,
                step_index=step.index,
            )
        fallback = f"Step{step.index}"
        fields = {
            **self._case_fields,
            "index": step.index,
            "declared_index": step.declared_index if step.declared_index is not None else step.index,
            "pascal_title": pascal or fallback,
            "snake_title": to_snake(step.title) or fallback.lower(),
            "camel_title": to_camel(step.title) or fallback[:1].lower() + fallback[1:],
            "upper_title": to_upper_snake(step.title) or fallback.upper(),
        }
        try:
            raw = self._pattern.format(**fields)
        except (KeyError, ValueError, IndexError) as exc:
            raise NamingPatternError(
                f"Naming pattern {self._pattern!r} could not be applied: {exc}",
                details={"pattern": self._pattern},
            ) from exc

        name = sanitize_identifier(raw)
        seen = self._used.get(name, 0) + 1
        self._used[name] = seen
        if seen > 1:
            if self._diagnostics is not None:
                self._diagnostics.warning(
                    "naming.duplicate",
                    f"Step {step.index} produced the identifier {name!r}, which is "
                    f"already in use; suffixing it with _{seen}.",
                    line=step.source_line,
                    case_index=self._case.index,
                    step_index=step.index,
                )
            name = f"{name}_{seen}"
        return name
