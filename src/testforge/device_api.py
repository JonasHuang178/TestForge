"""The surface a device's ``device.py`` imports.

A device is a folder holding one Python module plus the C/C++ files it fills
in. The module owns the rules that differ between devices — how a step becomes
a function name, which files come out, what code goes in each of them — while
the framework keeps the guarantees that must hold for every device:

* the plan is parsed the same way for all devices;
* only the regions between anchor markers are rewritten, so hand-written code
  survives regeneration;
* a file keeps the line endings it already had;
* the same input always produces byte-identical output.

A module must define ``ID``, ``NAME``, ``step_function_name`` and ``build``.
Everything else has a default. See ``devices/demo_board/device.py`` for a
worked example.
"""

from __future__ import annotations

import re
import string
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath

__all__ = [
    "StepInfo",
    "CaseInfo",
    "OutputFile",
    "output",
    "read_text",
    "pascal",
    "snake",
    "upper_snake",
    "camel",
    "cstr",
    "comment",
    "guard",
    "identifier",
]


# --------------------------------------------------------------- data passed in


@dataclass(frozen=True)
class StepInfo:
    """One step of the plan, as a device sees it."""

    index: int
    """1-based position in the case. Authoritative: a mis-numbered plan does
    not change it."""

    title: str
    declared_index: int | None
    description_md: str
    """The step's body, as the author wrote it. Raw markdown, never rendered."""

    expected: str | None
    source_line: int
    """1-based line of the step's heading in the plan."""

    function_name: str
    """Filled in by the framework from this device's ``step_function_name``."""

    @property
    def has_expected(self) -> bool:
        return self.expected is not None


@dataclass(frozen=True)
class CaseInfo:
    """One test case."""

    index: int
    title: str
    case_id: str | None
    """The ID from the plan's metadata block, if it has one."""

    metadata: dict[str, str]
    description_md: str
    steps: tuple[StepInfo, ...]
    source_line: int
    device_id: str


# -------------------------------------------------------------- data returned


@dataclass(frozen=True)
class OutputFile:
    """One file this device produces for one case."""

    path: str
    """Output filename, e.g. ``test_power_on.cpp``."""

    template: str = ""
    """A file in the device folder, used when the output does not exist yet.

    Leave empty and set ``content`` instead when the device needs to build the
    skeleton itself — for instance to insert anchor markers into a template
    that does not carry any.
    """

    content: str | None = None
    """The skeleton verbatim, overriding ``template`` when set."""

    anchors: dict[str, str] = field(default_factory=dict)
    """anchor name -> the code to place between its BEGIN and END markers."""

    variables: dict[str, str] = field(default_factory=dict)
    """``@@NAME@@`` placeholders substituted when the template is first used.

    Only applied on creation. Regenerating an existing file touches the
    anchored regions and nothing else.
    """


def output(
    path: str,
    template: str = "",
    anchors: dict[str, str] | None = None,
    *,
    content: str | None = None,
    **variables: str,
) -> OutputFile:
    """Describe one output file.

    Either name a ``template`` in the device folder, or pass ``content``
    already prepared by the module. Passing neither is an error.
    """
    if not template and content is None:
        raise ValueError(f"output({path!r}) needs either a template or content")
    return OutputFile(
        path=path,
        template=template,
        content=content,
        anchors=dict(anchors or {}),
        variables={k: str(v) for k, v in variables.items()},
    )


def read_text(path) -> str:
    """Read a file from the device folder without touching its line endings.

    Text mode would normalise CRLF to LF before the assembler could honour it.
    """
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


# ------------------------------------------------------------------- helpers

_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z]+")

#: C and C++ reserved words, plus a few names that collide with common macros.
RESERVED = frozenset(
    """
    alignas alignof and and_eq asm auto bitand bitor bool break case catch
    char char8_t char16_t char32_t class compl concept const consteval
    constexpr constinit const_cast continue co_await co_return co_yield
    decltype default delete do double dynamic_cast else enum explicit export
    extern false float for friend goto if inline int long mutable namespace
    new noexcept not not_eq nullptr operator or or_eq private protected public
    register reinterpret_cast requires restrict return short signed sizeof
    static static_assert static_cast struct switch template this thread_local
    throw true try typedef typeid typename union unsigned using virtual void
    volatile wchar_t while xor xor_eq NULL TRUE FALSE
    """.split()
)


def _tokens(text: str) -> list[str]:
    """ASCII alphanumeric tokens. Accents fold; CJK and symbols drop out."""
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    ascii_only = "".join(c if c in string.printable else " " for c in folded)
    return [t for t in _TOKEN_SPLIT.split(ascii_only) if t]


def pascal(text: str) -> str:
    """``power on the device`` -> ``PowerOnTheDevice``. Acronyms stay whole."""
    return "".join(
        t if t.isupper() and len(t) > 1 else t[:1].upper() + t[1:] for t in _tokens(text)
    )


def snake(text: str) -> str:
    """``Power On`` -> ``power_on``."""
    return "_".join(t.lower() for t in _tokens(text))


def upper_snake(text: str) -> str:
    return snake(text).upper()


def camel(text: str) -> str:
    p = pascal(text)
    return p[:1].lower() + p[1:] if p else ""


def identifier(name: str) -> str:
    """Make ``name`` a legal, non-reserved C/C++ identifier."""
    cleaned = re.sub(r"[^0-9A-Za-z_]", "", name) or "Unnamed"
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    if cleaned in RESERVED:
        cleaned += "_"
    return cleaned


def cstr(text: str | None) -> str:
    """Escape text for use inside a double-quoted C string literal."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def comment(text: str | None, prefix: str = "// ") -> str:
    """Render arbitrary text as line comments.

    Line comments rather than ``/* */`` because a markdown body may itself
    contain ``*/`` and would close the block early.
    """
    if not text:
        return ""
    return "\n".join(f"{prefix}{line}".rstrip() for line in str(text).splitlines())


def guard(filename: str) -> str:
    """``test_power_on.h`` -> ``TEST_POWER_ON_H``, for an include guard."""
    name = PurePosixPath(filename).name
    return upper_snake(name.replace(".", " ")) or "TESTFORGE_GENERATED_H"
