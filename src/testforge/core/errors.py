"""Domain exceptions.

The core layer raises only these. Mapping them to HTTP status codes happens
exclusively in ``testforge.api.errors`` so that core stays usable from the CLI
and from unit tests without FastAPI installed.
"""

from __future__ import annotations

from typing import Any


class TestForgeError(Exception):
    """Base class for every error TestForge raises deliberately."""

    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class DeviceNotFoundError(TestForgeError):
    code = "device_not_found"


class ManifestError(TestForgeError):
    """A device manifest is malformed or references missing templates."""

    code = "manifest_invalid"


class TemplateRenderError(TestForgeError):
    code = "template.render_failed"


class NamingPatternError(TestForgeError):
    code = "naming.pattern_invalid"


class OutputFormatError(TestForgeError):
    """The requested response representation cannot carry this result."""

    code = "format.unsupported"


class AnchorError(TestForgeError):
    code = "anchor.error"


class AnchorMissingError(AnchorError):
    code = "anchor.missing"


class AnchorUnbalancedError(AnchorError):
    code = "anchor.unbalanced"


class AnchorDuplicateError(AnchorError):
    code = "anchor.duplicate"


class UnprocessableDocumentError(TestForgeError):
    """The markdown could not be turned into anything useful.

    Carries the diagnostics collected so far so the caller can report every
    problem at once instead of one per round trip.
    """

    code = "document.unprocessable"

    def __init__(
        self,
        message: str,
        *,
        diagnostics: list[Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.diagnostics = diagnostics or []
