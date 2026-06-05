"""SpiderPilot command line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from spiderpilot.platform.initializer import init_platform
from spiderpilot.spec import build_task_summary, load_spec, prepare_task_workspace, write_task_summary
from spiderpilot.templates.loader import list_templates, load_template

app = typer.Typer(help="SpiderPilot: AI-powered field-driven reverse crawling framework.")
platform_app = typer.Typer(help="Platform workspace commands.")
template_app = typer.Typer(help="Domain template commands.")
app.add_typer(platform_app, name="platform")
app.add_typer(template_app, name="template")


@template_app.command("list")
def template_list() -> None:
    """List available domain templates."""
    for name in list_templates():
        typer.echo(name)


@template_app.command("show")
def template_show(name: str) -> None:
    """Show a domain template as YAML."""
    import yaml

    data = load_template(name)
    typer.echo(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


@platform_app.command("init")
def platform_init(
    name: str = typer.Argument(..., help="Platform name, e.g. allegro or bbc."),
    domain: str | None = typer.Option(None, "--domain", "-d", help="Platform domain."),
    template: str = typer.Option("generic", "--template", "-t", help="Domain template name."),
    workspace: Path = typer.Option(Path("workspace/platforms"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Initialize a platform workspace from a domain template."""
    platform_dir = init_platform(name=name, domain=domain, template=template, workspace=workspace)
    typer.echo(f"Created platform workspace: {platform_dir}")
    typer.echo(f"- {platform_dir / 'platform.yaml'}")
    typer.echo(f"- {platform_dir / 'spider_plan.yaml'}")


@app.command("create")
def create(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Create a SpiderPilot task workspace from a Spec file.

    MVP behavior: validate the Spec, copy it into workspace/specs, create
    artifacts/plans/generated_spiders/results paths, and print a task summary.
    """
    spec = load_spec(file)
    task_workspace = prepare_task_workspace(spec, source_path=file, workspace=workspace)
    summary = build_task_summary(spec, task_workspace)
    write_task_summary(summary, task_workspace.summary_path)

    typer.echo(f"Task created: {spec.name}")
    typer.echo(f"Samples: {len(spec.samples)}")
    typer.echo(f"Fields: {', '.join(spec.fields.keys())}")
    typer.echo(f"Spec: {task_workspace.spec_path}")
    typer.echo(f"Artifacts: {task_workspace.artifacts_dir}")
    typer.echo(f"Summary: {task_workspace.summary_path}")
    typer.echo("Next: spiderpilot antibot -f " + str(task_workspace.spec_path))


@app.command("version")
def version() -> None:
    """Print SpiderPilot version."""
    typer.echo("spiderpilot 0.1.0")
