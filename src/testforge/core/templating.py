"""Jinja2 environment and the filters device templates may rely on."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from testforge.core.errors import TemplateRenderError
from testforge.core.naming import (
    sanitize_identifier,
    to_camel,
    to_pascal,
    to_snake,
    to_upper_snake,
)


def cpp_comment(text: str | None, prefix: str = "// ") -> str:
    """Render arbitrary text as a run of C++ line comments.

    Markdown bodies are multi-line by nature; emitting them as ``/* */`` would
    break on any ``*/`` in the source, so line comments are used throughout.
    """
    if not text:
        return ""
    lines = str(text).splitlines() or [""]
    return "\n".join(f"{prefix}{line}".rstrip() for line in lines)


def cpp_string(text: str | None) -> str:
    """Escape text for use inside a double-quoted C++ string literal."""
    if text is None:
        return ""
    out = (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\r", "")
        .replace("\n", "\\n")
    )
    return out


def first_line(text: str | None) -> str:
    """The first non-empty line, useful for one-line summaries."""
    if not text:
        return ""
    for line in str(text).splitlines():
        if line.strip():
            return line.strip()
    return ""


def indent_block(text: str, width: int = 4) -> str:
    pad = " " * width
    return "\n".join(f"{pad}{line}".rstrip() for line in str(text).splitlines())


FILTERS = {
    "cpp_comment": cpp_comment,
    "cpp_string": cpp_string,
    "first_line": first_line,
    "indent_block": indent_block,
    # Identifier casing, so a template never has to do its own string surgery.
    "pascal": to_pascal,
    "snake": to_snake,
    "camel": to_camel,
    "upper_snake": to_upper_snake,
    "cpp_ident": sanitize_identifier,
}


def make_environment(template_root: Path) -> Environment:
    """Build the environment used for one device's templates.

    ``StrictUndefined`` is deliberate: a typo in a template placeholder should
    fail loudly instead of silently rendering an empty string into generated
    C++ that then fails to compile for an unrelated-looking reason.
    """
    env = Environment(
        loader=FileSystemLoader(str(template_root)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters.update(FILTERS)
    return env


def render(env: Environment, template_name: str, context: dict[str, object]) -> str:
    try:
        return env.get_template(template_name).render(**context)
    except TemplateError as exc:
        raise TemplateRenderError(
            f"Template {template_name!r} failed to render: {exc}",
            details={"template": template_name, "reason": str(exc)},
        ) from exc
