"""Typer CLI entry point for AgentTest.

S1: in-process invocation only — `python -m agenttest generate Foo.java`
runs the pipeline via `asyncio.run` and writes a placeholder JUnit class
to disk. The `--server URL` opt-in for HTTP/skill-parity (architecture
decision 1) lands in S3 alongside the FastAPI `/generate` route.
"""

import asyncio
import logging
from pathlib import Path

import typer

from agenttest import pipeline

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Security-aware unit test generator for Java AI agent code.",
)


@app.callback()
def _root() -> None:
    """AgentTest CLI root.

    A no-op callback exists so Typer keeps the `generate` subcommand
    layer (it would otherwise collapse a single-command app into the
    root, breaking `python -m agenttest generate ...`).
    """


@app.command()
def generate(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a Java source file containing AI-agent logic.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output path for the generated JUnit test class. "
        "Defaults to <input_dir>/<TargetClass>SecurityGenTest.java.",
    ),
) -> None:
    """Generate a JUnit 5 security test class for INPUT_PATH."""
    # Surface pipeline progress logs to the user. The pipeline emits
    # INFO-level lines like "[analyzer] found N risk site(s)"; in S3 these
    # become async events and this handler goes away.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    emission = asyncio.run(pipeline.run(input_path))

    output_path = out if out is not None else Path(emission.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(emission.java_source, encoding="utf-8")

    typer.echo("")
    typer.echo(f"Wrote {output_path}")
    typer.echo(f"Risk sites found: {len(emission.refused_sites) + len(emission.risks_covered)}")
    typer.echo(f"Tests emitted:    {len(emission.risks_covered)}")
    typer.echo(f"Sites refused:    {len(emission.refused_sites)}")
    for site, reason in emission.refused_sites:
        typer.echo(
            f"  - {site.method_name} "
            f"({site.file_path}:{site.line_start}-{site.line_end}) "
            f"[{site.site_kind}]: {reason}"
        )
    typer.echo("")
    typer.echo(
        "Reminder: generated tests are advisory. A human MUST review every "
        "test before it lands in src/test/java."
    )


if __name__ == "__main__":
    app()
