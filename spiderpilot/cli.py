"""SpiderPilot command line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from spiderpilot.platform.initializer import init_platform
from spiderpilot.spec import build_task_summary, load_spec, prepare_task_workspace, write_task_summary
from spiderpilot.antibot.precheck import run_antibot_precheck
from spiderpilot.probe.http_probe import run_http_probe
from spiderpilot.reverse.locator import run_reverse
from spiderpilot.planner.extraction_plan import build_extraction_plan
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


@app.command("antibot")
def antibot(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    timeout: int = typer.Option(15, "--timeout", help="HTTP timeout seconds."),
) -> None:
    """Run no-cookie HTTP anti-bot precheck for all Spec samples."""
    report = run_antibot_precheck(file, workspace=workspace, timeout=timeout)
    report_path = workspace / "artifacts" / report["task"] / "antibot_report.yaml"
    typer.echo(f"AntiBot status: {report['status']}")
    typer.echo(f"Samples flagged: {report['samples_flagged']}/{report['samples_total']}")
    if report.get("primary_vendor"):
        typer.echo(f"Primary vendor: {report['primary_vendor']}")
    typer.echo(f"Report: {report_path}")


@app.command("probe")
def probe(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    timeout: int = typer.Option(20, "--timeout", help="HTTP timeout seconds."),
) -> None:
    """Collect HTTP page artifacts for all Spec samples."""
    report = run_http_probe(file, workspace=workspace, timeout=timeout)
    report_path = workspace / "artifacts" / report["task"] / "probe_report.yaml"
    typer.echo(f"Probe task: {report['task']}")
    typer.echo(f"Samples OK: {report['samples_ok']}/{report['samples_total']}")
    typer.echo(f"Report: {report_path}")


@app.command("reverse")
def reverse(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Reverse field locations from collected artifacts.

    MVP behavior: search expected sample values inside raw.html artifacts and
    write candidates.yaml.
    """
    report = run_reverse(file, workspace=workspace)
    candidates_path = workspace / "artifacts" / report["task"] / "candidates.yaml"
    typer.echo(f"Reverse task: {report['task']}")
    typer.echo(f"Candidates: {report['candidates_total']}")
    typer.echo(f"Report: {candidates_path}")


@app.command("plan")
def plan(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Build an Extraction Plan from reverse candidates."""
    extraction_plan = build_extraction_plan(file, workspace=workspace)
    plan_path = workspace / "plans" / f"{extraction_plan['name']}.yaml"
    typer.echo(f"Plan task: {extraction_plan['name']}")
    typer.echo(f"Source: {extraction_plan['source']['type']}")
    typer.echo(f"Confidence: {extraction_plan['source']['confidence']}")
    typer.echo(f"Plan: {plan_path}")


@app.command("version")
def version() -> None:
    """Print SpiderPilot version."""
    typer.echo("spiderpilot 0.1.0")
