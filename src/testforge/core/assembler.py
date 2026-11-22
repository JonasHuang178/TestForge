"""Anchor-based code injection.

Generated code lives between a paired begin/end marker. Rewriting only the
span between the two lines is what makes regeneration idempotent and keeps
hand-written code outside the anchors untouched, so a generated file can be
committed and regenerated in place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from testforge.core.errors import (
    AnchorDuplicateError,
    AnchorMissingError,
    AnchorUnbalancedError,
)

_INDENT_RE = re.compile(r"^[ \t]*")


@dataclass(frozen=True)
class AnchorStyle:
    """How a device spells its begin and end markers.

    Both must contain ``{name}``. A device that generates C89, where ``//`` is
    not a comment, can declare a block-comment form instead.
    """

    begin: str = "// === TESTFORGE:{name}:BEGIN ==="
    end: str = "// === TESTFORGE:{name}:END ==="

    def __post_init__(self) -> None:
        for field_name, value in (("begin", self.begin), ("end", self.end)):
            if "{name}" not in value:
                raise ValueError(f"anchor {field_name} marker must contain {{name}}")

    def begin_marker(self, name: str) -> str:
        return self.begin.format(name=name)

    def end_marker(self, name: str) -> str:
        return self.end.format(name=name)


DEFAULT_ANCHOR_STYLE = AnchorStyle()


def detect_newline(content: str) -> str:
    """The line ending the file already uses.

    Generated files get committed, so rewriting a CRLF file with LF endings
    would show every line as changed in the next diff. The dominant ending
    wins, which keeps a file with a few stray endings consistent instead of
    propagating the mixture.
    """
    crlf = content.count("\r\n")
    lf = content.count("\n") - crlf
    return "\r\n" if crlf > lf else "\n"


@dataclass(frozen=True)
class AnchorRegion:
    name: str
    begin_line: int  # 0-based index of the BEGIN marker line
    end_line: int  # 0-based index of the END marker line
    indent: str


def find_anchor_regions(
    content: str, style: AnchorStyle, names: list[str]
) -> dict[str, AnchorRegion]:
    """Locate each requested anchor pair in ``content``.

    Markers are matched on the stripped line, so indenting an anchor inside a
    namespace or class body is fine. Anchors absent from the file are simply
    missing from the result; it is up to the caller to decide whether that is
    an error.
    """
    begins = {style.begin_marker(n): n for n in names}
    ends = {style.end_marker(n): n for n in names}

    lines = content.splitlines()
    open_at: dict[str, int] = {}
    regions: dict[str, AnchorRegion] = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in begins:
            name = begins[stripped]
            if name in regions or name in open_at:
                raise AnchorDuplicateError(
                    f"Anchor {name!r} opens more than once (line {i + 1}); "
                    f"each anchor may appear only once per file.",
                    details={"anchor": name, "line": i + 1},
                )
            open_at[name] = i
        elif stripped in ends:
            name = ends[stripped]
            if name not in open_at:
                raise AnchorUnbalancedError(
                    f"Anchor {name!r} is closed at line {i + 1} without a "
                    f"matching BEGIN marker.",
                    details={"anchor": name, "line": i + 1},
                )
            begin_line = open_at.pop(name)
            regions[name] = AnchorRegion(
                name=name,
                begin_line=begin_line,
                end_line=i,
                indent=_INDENT_RE.match(lines[begin_line]).group(0),
            )

    if open_at:
        name, line = sorted(open_at.items(), key=lambda kv: kv[1])[0]
        raise AnchorUnbalancedError(
            f"Anchor {name!r} opens at line {line + 1} but is never closed.",
            details={"anchor": name, "line": line + 1},
        )
    return regions


def inject(
    content: str,
    fragments: dict[str, str],
    style: AnchorStyle = DEFAULT_ANCHOR_STYLE,
) -> tuple[str, tuple[str, ...]]:
    """Replace the body of each anchor in ``content`` with its fragment.

    Returns the rewritten content and the anchors that were filled, in the
    file's own order. Raises :class:`AnchorMissingError` if a fragment has
    nowhere to go, which is the common symptom of a template that lost its
    markers.
    """
    names = list(fragments)
    regions = find_anchor_regions(content, style, names)

    missing = [n for n in names if n not in regions]
    if missing:
        raise AnchorMissingError(
            f"The file has no marker pair for anchor(s): {', '.join(missing)}. "
            f"Expected lines spelled {style.begin_marker(missing[0])!r} and "
            f"{style.end_marker(missing[0])!r}.",
            details={
                "anchors": missing,
                "expected_begin": [style.begin_marker(n) for n in missing],
                "expected_end": [style.end_marker(n) for n in missing],
            },
        )

    newline = detect_newline(content)
    lines = content.splitlines()
    # Bottom-up so earlier replacements do not shift later line indices.
    for name in sorted(names, key=lambda n: regions[n].begin_line, reverse=True):
        region = regions[name]
        body = _indented_body(fragments[name], region.indent)
        lines[region.begin_line + 1 : region.end_line] = body

    assembled = newline.join(lines)
    if content.endswith(("\n", "\r")) and not assembled.endswith(newline):
        assembled += newline
    filled = tuple(sorted(names, key=lambda n: regions[n].begin_line))
    return assembled, filled


def _indented_body(fragment: str, indent: str) -> list[str]:
    """Re-indent a rendered fragment to sit under its BEGIN marker."""
    stripped = fragment.strip("\n")
    if not stripped.strip():
        return []
    return [f"{indent}{line}".rstrip() if line.strip() else "" for line in stripped.splitlines()]
