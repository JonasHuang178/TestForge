"""Structured, non-fatal problem reporting.

Test plans are written by hand, so the input is reliably messy. Recoverable
problems are collected here and returned alongside the result rather than
raised, which lets a caller see every issue in one pass.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Diagnostic(BaseModel):
    """One problem found while parsing or generating.

    ``code`` is the stable identifier that clients and tests assert on;
    ``message`` is for humans and may be reworded at any time.
    """

    model_config = ConfigDict(frozen=True)

    severity: Severity
    code: str
    message: str
    line: int | None = Field(default=None, description="1-based source line")
    case_index: int | None = None
    step_index: int | None = None


class DiagnosticCollector:
    """Accumulates diagnostics during a single parse or generate call."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        *,
        line: int | None = None,
        case_index: int | None = None,
        step_index: int | None = None,
    ) -> None:
        self._items.append(
            Diagnostic(
                severity=severity,
                code=code,
                message=message,
                line=line,
                case_index=case_index,
                step_index=step_index,
            )
        )

    def error(self, code: str, message: str, **kw: int | None) -> None:
        self.add(Severity.ERROR, code, message, **kw)

    def warning(self, code: str, message: str, **kw: int | None) -> None:
        self.add(Severity.WARNING, code, message, **kw)

    def info(self, code: str, message: str, **kw: int | None) -> None:
        self.add(Severity.INFO, code, message, **kw)

    def extend(self, items: list[Diagnostic]) -> None:
        self._items.extend(items)

    @property
    def items(self) -> list[Diagnostic]:
        return list(self._items)

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self._items)
