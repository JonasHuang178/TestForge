"""Turning a generation result into something downloadable.

Shared by the HTTP API and the web layer so the two cannot drift: a zip
produced by one is byte-identical to the other's.
"""

from __future__ import annotations

import io
import re
import zipfile

from testforge.core.models import GenerationResult

#: A fixed timestamp keeps the archive byte-identical across runs, which is the
#: same determinism the golden-file tests rely on.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    """Reduce a name to characters safe in a Content-Disposition header."""
    cleaned = _UNSAFE_FILENAME.sub("_", name).strip("_")
    return cleaned or "generated"


def artifacts_to_zip(result: GenerationResult) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for artifact in result.artifacts:
            info = zipfile.ZipInfo(artifact.path, date_time=ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            archive.writestr(info, artifact.content)
    return buffer.getvalue()


def zip_filename(result: GenerationResult) -> str:
    return safe_filename(f"{result.device_id}_generated") + ".zip"
