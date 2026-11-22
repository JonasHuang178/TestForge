"""The intermediate representation and the boundary objects around it.

These are internal models. They are deliberately NOT used as API response
models: ``testforge.api.schemas`` defines separate DTOs and
``testforge.api.mappers`` converts between them, so the IR can grow fields
without breaking the published contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from testforge.core.diagnostics import Diagnostic


class TestStep(BaseModel):
    """One step of a test case, as read from the markdown."""

    model_config = ConfigDict(frozen=True)

    # Named Test*, so pytest would otherwise try to collect it as a suite.
    __test__ = False

    index: int = Field(description="1-based position within the case")
    declared_index: int | None = Field(
        default=None,
        description="The number written in the heading, if any. May disagree "
        "with `index` when the author misnumbered the plan.",
    )
    title: str
    description_md: str = Field(
        default="",
        description="Raw markdown of the step body, minus the Expected block. "
        "Kept raw so templates decide how to render it.",
    )
    expected: str | None = None
    source_line: int = Field(description="1-based line of the step heading")


class TestCase(BaseModel):
    """A single test case: the unit of generation."""

    model_config = ConfigDict(frozen=True)

    # Named Test*, so pytest would otherwise try to collect it as a suite.
    __test__ = False

    index: int = Field(description="1-based position within the document")
    title: str
    metadata: dict[str, str] = Field(default_factory=dict)
    description_md: str = ""
    steps: tuple[TestStep, ...] = ()
    source_line: int

    @property
    def case_id(self) -> str | None:
        """The ID from the metadata block, under any common spelling."""
        for key in ("id", "case_id", "test_case_id"):
            if key in self.metadata:
                return self.metadata[key]
        return None


class ParseResult(BaseModel):
    """What the parser returns: cases plus everything questionable about them."""

    model_config = ConfigDict(frozen=True)

    cases: tuple[TestCase, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


class CodeFragment(BaseModel):
    """Rendered code destined for one anchor in one output file."""

    model_config = ConfigDict(frozen=True)

    anchor: str
    content: str


class ExistingFile(BaseModel):
    """A file the client already has, sent up so we can regenerate in place.

    This is how idempotent regeneration works without server-side state: the
    client owns the file, we only rewrite the anchored regions.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    content: str


class GeneratedArtifact(BaseModel):
    """One output file produced by a generation."""

    model_config = ConfigDict(frozen=True)

    path: str
    content: str
    mode: Literal["created", "updated"]
    anchors_filled: tuple[str, ...] = ()


class GenerationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    cases: int
    steps: int
    functions: tuple[str, ...] = ()


class GenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_id: str
    device_id: str
    artifacts: tuple[GeneratedArtifact, ...] = ()
    summary: GenerationSummary
    diagnostics: tuple[Diagnostic, ...] = ()
