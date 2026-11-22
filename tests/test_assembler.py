from __future__ import annotations

import pytest

from testforge.core.assembler import detect_newline, find_anchor_regions, inject
from testforge.core.errors import (
    AnchorDuplicateError,
    AnchorMissingError,
    AnchorUnbalancedError,
)
from testforge.devices.manifest import AnchorStyle

STYLE = AnchorStyle()

FILE = """\
#include "x.h"

// hand-written, must survive
static int g_budget = 3;

void Run() {
  // === TESTFORGE:CALLS:BEGIN ===
  // === TESTFORGE:CALLS:END ===
}

// === TESTFORGE:DEFS:BEGIN ===
// === TESTFORGE:DEFS:END ===
"""


def test_finds_both_regions_with_their_indentation() -> None:
    regions = find_anchor_regions(FILE, STYLE, ["CALLS", "DEFS"])
    assert regions["CALLS"].indent == "  "
    assert regions["DEFS"].indent == ""


def test_injects_and_reindents_to_match_the_marker() -> None:
    out, filled = inject(FILE, {"CALLS": "a();\nb();", "DEFS": "void a() {}"}, STYLE)
    assert filled == ("CALLS", "DEFS")
    assert "  a();\n  b();" in out  # indented to the marker
    assert "\nvoid a() {}" in out  # top-level marker, no indent
    assert "static int g_budget = 3;" in out  # untouched


def test_regeneration_is_idempotent() -> None:
    fragments = {"CALLS": "a();", "DEFS": "void a() {}"}
    once, _ = inject(FILE, fragments, STYLE)
    twice, _ = inject(once, fragments, STYLE)
    assert once == twice


def test_replacing_a_filled_region_does_not_accumulate() -> None:
    filled, _ = inject(FILE, {"CALLS": "old();", "DEFS": ""}, STYLE)
    replaced, _ = inject(filled, {"CALLS": "new();", "DEFS": ""}, STYLE)
    assert "old();" not in replaced
    assert "new();" in replaced


def test_empty_fragment_clears_the_region() -> None:
    filled, _ = inject(FILE, {"CALLS": "a();", "DEFS": ""}, STYLE)
    cleared, _ = inject(filled, {"CALLS": "", "DEFS": ""}, STYLE)
    # The markers are indented inside Run(), so compare on stripped lines.
    lines = [line.strip() for line in cleared.splitlines()]
    begin = lines.index("// === TESTFORGE:CALLS:BEGIN ===")
    assert lines[begin + 1] == "// === TESTFORGE:CALLS:END ==="


def test_missing_anchor_raises_with_the_expected_spelling() -> None:
    with pytest.raises(AnchorMissingError) as excinfo:
        inject("// nothing here\n", {"CALLS": "a();"}, STYLE)
    assert excinfo.value.details["anchors"] == ["CALLS"]
    assert "TESTFORGE:CALLS:BEGIN" in excinfo.value.details["expected_begin"][0]


def test_unclosed_anchor_raises() -> None:
    with pytest.raises(AnchorUnbalancedError):
        inject("// === TESTFORGE:CALLS:BEGIN ===\n", {"CALLS": "a();"}, STYLE)


def test_close_before_open_raises() -> None:
    with pytest.raises(AnchorUnbalancedError):
        inject("// === TESTFORGE:CALLS:END ===\n", {"CALLS": "a();"}, STYLE)


def test_duplicate_anchor_raises() -> None:
    content = (
        "// === TESTFORGE:CALLS:BEGIN ===\n// === TESTFORGE:CALLS:END ===\n"
        "// === TESTFORGE:CALLS:BEGIN ===\n// === TESTFORGE:CALLS:END ===\n"
    )
    with pytest.raises(AnchorDuplicateError):
        inject(content, {"CALLS": "a();"}, STYLE)


# -- line endings -----------------------------------------------------------
#
# Generated files get committed. Rewriting a CRLF file with LF endings would
# report every line as changed in the next diff, which defeats the point of
# regenerating in place. These matter most on Windows, where CRLF is the norm.


def test_detect_newline() -> None:
    assert detect_newline("a\r\nb\r\n") == "\r\n"
    assert detect_newline("a\nb\n") == "\n"
    assert detect_newline("") == "\n"
    # A few stray endings must not flip the whole file.
    assert detect_newline("a\r\nb\r\nc\n") == "\r\n"
    assert detect_newline("a\nb\nc\r\n") == "\n"


def test_crlf_file_keeps_crlf() -> None:
    crlf = FILE.replace("\n", "\r\n")
    out, _ = inject(crlf, {"CALLS": "a();", "DEFS": "void a() {}"}, STYLE)
    assert "\r\n" in out
    # No mixture: every LF is part of a CRLF pair.
    assert out.count("\n") == out.count("\r\n")


def test_lf_file_keeps_lf() -> None:
    out, _ = inject(FILE, {"CALLS": "a();", "DEFS": "void a() {}"}, STYLE)
    assert "\r" not in out


def test_crlf_regeneration_is_idempotent() -> None:
    crlf = FILE.replace("\n", "\r\n")
    fragments = {"CALLS": "a();", "DEFS": "void a() {}"}
    once, _ = inject(crlf, fragments, STYLE)
    twice, _ = inject(once, fragments, STYLE)
    assert once == twice
