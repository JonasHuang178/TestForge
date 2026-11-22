"""Command line interface.

A second consumer of ``GenerationService``, which is the point: anything the
CLI can do without HTTP proves the core really is free of web concerns.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from testforge.core.errors import TestForgeError, UnprocessableDocumentError
from testforge.core.options import GenerateOptions, ParseOptions
from testforge.devices.registry import DeviceRegistry
from testforge.service import GenerationService

_SEVERITY_COLOR = {"error": "red", "warning": "yellow", "info": "cyan"}


def _service() -> GenerationService:
    return GenerationService(DeviceRegistry.from_roots())


def _echo_diagnostics(diagnostics) -> None:
    for d in diagnostics:
        where = f"line {d.line}" if d.line else "-"
        click.secho(
            f"  [{d.severity.value:<7}] {d.code:<32} {where:>9}  {d.message}",
            fg=_SEVERITY_COLOR.get(d.severity.value),
            err=True,
        )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="testforge")
def main() -> None:
    """Generate C++ test code from markdown test plans."""


@main.command("devices")
def list_devices() -> None:
    """List the devices TestForge can generate for."""
    for device in _service().registry.list():
        m = device.manifest
        click.echo(f"{m.id}  (v{m.version})  {m.name}")
        click.echo(f"    naming:  {m.naming.step_function}")
        click.echo(f"    outputs: {', '.join(o.path for o in m.outputs)}")
        click.echo(f"    path:    {device.directory}")


@main.command("parse")
@click.argument("plan", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--device", "device_id", default=None, help="Adopt this device's heading conventions.")
@click.option("--step-level", type=click.IntRange(1, 6), default=None, help="Step heading level.")
@click.option("--json", "as_json", is_flag=True, help="Emit the IR as JSON.")
def parse_plan(plan: Path, device_id: str | None, step_level: int | None, as_json: bool) -> None:
    """Show what TestForge reads from PLAN without generating anything."""
    options = ParseOptions(step_heading_level=step_level) if step_level else None
    result = _service().parse(plan.read_text(encoding="utf-8"), options, device_id=device_id)

    if as_json:
        click.echo(result.model_dump_json(indent=2))
    else:
        for case in result.cases:
            click.secho(f"Case {case.index}: {case.title}", bold=True)
            if case.metadata:
                click.echo(f"  metadata: {case.metadata}")
            for step in case.steps:
                mark = "+" if step.expected else " "
                click.echo(f"  {mark} {step.index:>2}. {step.title}  (line {step.source_line})")
        click.echo(f"\n{len(result.cases)} case(s), "
                   f"{sum(len(c.steps) for c in result.cases)} step(s)")

    if result.diagnostics:
        click.secho(f"\n{len(result.diagnostics)} diagnostic(s):", bold=True, err=True)
        _echo_diagnostics(result.diagnostics)


@main.command("generate")
@click.argument("plan", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--device", "device_id", required=True, help="Device id; see `testforge devices`.")
@click.option(
    "-o",
    "--out",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Write artifacts here. Existing files are regenerated in place, so "
    "anything outside the anchors is kept.",
)
@click.option("--case", "case_selector", type=click.IntRange(min=1), default=None, help="Only this case.")
@click.option("--naming", default=None, help="Override the step function pattern.")
def generate(
    plan: Path,
    device_id: str,
    out: Path | None,
    case_selector: int | None,
    naming: str | None,
) -> None:
    """Generate code from PLAN. Without -o, the artifacts go to stdout."""
    service = _service()
    options = GenerateOptions(case_selector=case_selector, naming_pattern=naming)

    existing = []
    if out is not None and out.is_dir():
        # Feed back whatever is already there; this is what makes a rerun
        # preserve hand-written code outside the anchors.
        from testforge.core.models import ExistingFile

        for path in sorted(out.iterdir()):
            if path.is_file():
                existing.append(
                    ExistingFile(path=path.name, content=path.read_text(encoding="utf-8"))
                )

    result = service.generate(plan.read_text(encoding="utf-8"), device_id, options, existing)

    if out is None:
        for artifact in result.artifacts:
            click.echo(f"{'=' * 70}\n== {artifact.path}  ({artifact.mode})\n{'=' * 70}")
            click.echo(artifact.content)
    else:
        out.mkdir(parents=True, exist_ok=True)
        for artifact in result.artifacts:
            (out / artifact.path).write_text(artifact.content, encoding="utf-8")
            click.echo(f"{artifact.mode:>7}  {out / artifact.path}")

    click.secho(
        f"\n{result.summary.cases} case(s), {result.summary.steps} step(s), "
        f"{len(result.artifacts)} file(s)",
        bold=True,
        err=True,
    )
    if result.diagnostics:
        _echo_diagnostics(result.diagnostics)


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, help="Reload on source changes (development).")
def serve(host: str, port: int, reload: bool) -> None:
    """Run the web interface and the REST API."""
    import uvicorn

    click.secho(f"TestForge  ->  http://{host}:{port}", bold=True)
    click.echo(f"  web 介面   http://{host}:{port}/")
    click.echo(f"  API 文件   http://{host}:{port}/docs")
    uvicorn.run("testforge.api.app:app", host=host, port=port, reload=reload)


def _run() -> int:
    try:
        main.main(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Abort:
        return 130
    except UnprocessableDocumentError as exc:
        click.secho(f"error: {exc.message}", fg="red", err=True)
        _echo_diagnostics(exc.diagnostics)
        return 2
    except TestForgeError as exc:
        click.secho(f"error [{exc.code}]: {exc.message}", fg="red", err=True)
        if exc.details:
            click.echo(json.dumps(exc.details, indent=2, default=str), err=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
