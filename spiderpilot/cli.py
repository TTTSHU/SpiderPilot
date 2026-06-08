"""SpiderPilot command line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from spiderpilot.platform.initializer import init_platform
from spiderpilot.spec import build_task_summary, load_spec, prepare_task_workspace, write_task_summary
from spiderpilot.antibot.precheck import run_antibot_precheck
from spiderpilot.antibot.strategy import build_antibot_strategy
from spiderpilot.probe.http_probe import run_http_probe
from spiderpilot.probe.diff import build_probe_diff
from spiderpilot.probe.cloak_probe import run_cloak_probe
from spiderpilot.reverse.locator import run_reverse
from spiderpilot.ai_reverse import ai_reverse
import uvicorn
from spiderpilot.web.app import app as web_app
from spiderpilot.ai_codegen import ai_generate
from spiderpilot.ai_repair import ai_repair_plan
from spiderpilot.planner.extraction_plan import build_extraction_plan
from spiderpilot.generator.codegen import generate_spider
from spiderpilot.discovery import run_discovery
from spiderpilot.signature.detector import detect_signatures
from spiderpilot.signature.request_diff import analyze_signature_diff
from spiderpilot.signature.runtime_hook import write_hook_script
from spiderpilot.signature.sample_collector import collect_signature_samples
from spiderpilot.signature.generator import generate_signer_skeleton
from spiderpilot.signature.verifier import verify_signer
from spiderpilot.runner.local_runner import run_plan
from spiderpilot.runner.http_runner import run_http_plan
from spiderpilot.validator.result_validator import validate_results
from spiderpilot.workflow import create_task, run_all
from spiderpilot.repair.auto_repair import build_repair_report
from spiderpilot.repair.loop import run_repair_loop
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
    run_all_steps: bool = typer.Option(False, "--run-all", help="Run the full 8-step MVP workflow after creating the task."),
    ai: bool = typer.Option(False, "--ai", help="Use LLM for reverse analysis instead of rules."),
    skip_network: bool = typer.Option(False, "--skip-network", help="Skip antibot/probe and reuse existing raw.html artifacts. Useful for offline fixtures."),
    timeout: int = typer.Option(20, "--timeout", help="HTTP timeout seconds for antibot/probe."),
    with_cloak: bool = typer.Option(False, "--with-cloak", help="Run CloakBrowser capture, probe diff, and antibot strategy inside --run-all."),
    cloak_wait: float = typer.Option(5.0, "--cloak-wait", help="Seconds to wait for CloakBrowser network capture."),
) -> None:
    """Create a SpiderPilot task workspace from a Spec file.

    Use --run-all to execute the full MVP workflow:
    create → antibot → probe → reverse → plan → generate → run → validate → repair.
    """
    if run_all_steps:
        report = run_all(file, workspace=workspace, timeout=timeout, skip_network=skip_network, with_cloak=with_cloak, ai=ai, cloak_wait=cloak_wait)
        typer.echo(f"Workflow task: {report['task']}")
        typer.echo(f"OK: {report['ok']}")
        typer.echo(f"Workflow report: {report['workflow_report_path']}")
        return

    created = create_task(file, workspace=workspace)
    spec = created["spec"]
    task_workspace = created["workspace"]
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


@app.command("antibot-strategy")
def antibot_strategy(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Build anti-bot strategy from collected precheck/probe reports."""
    report = build_antibot_strategy(file, workspace=workspace)
    report_path = workspace / "artifacts" / report["task"] / "antibot_strategy.yaml"
    typer.echo(f"AntiBot strategy: {report['strategy']}")
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



@app.command("reverse-ai")
def reverse_ai(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    model: str = typer.Option("deepseek-v4-flash", "--model", help="LLM model name."),
) -> None:
    """Use AI to analyze page artifacts and generate an Extraction Plan."""
    plan = ai_reverse(file, workspace=workspace, model=model)
    plan_path = workspace / "plans" / f"{plan['name']}.yaml"
    typer.echo(f"AI source: {plan['source']['type']}")
    typer.echo(f"AI confidence: {plan['source']['confidence']}")
    typer.echo(f"Plan: {plan_path}")
    for name, info in plan["fields"].items():
        typer.echo(f"  {name}: {info.get('source')} {info.get('path')} ({info.get('confidence', 0):.2f})")

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


@app.command("probe-diff")
def probe_diff(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Compare HTTP Probe artifacts with CloakBrowser artifacts."""
    report = build_probe_diff(file, workspace=workspace)
    report_path = workspace / "artifacts" / report["task"] / "probe_diff.yaml"
    typer.echo(f"Probe diff strategy hint: {report['summary']['strategy_hint']}")
    typer.echo(f"Report: {report_path}")


@app.command("cloak-probe")
def cloak_probe(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    capture: bool = typer.Option(False, "--capture", help="Launch CloakBrowser and capture rendered/network artifacts."),
    wait_seconds: float = typer.Option(5.0, "--wait", help="Seconds to wait for network events."),
    signature_hook: bool = typer.Option(False, "--signature-hook", help="Inject SpiderPilot signature runtime hooks."),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode."),
) -> None:
    """Prepare or run CloakBrowser probe artifacts."""
    report = run_cloak_probe(file, workspace=workspace, capture=capture, wait_seconds=wait_seconds, signature_hook=signature_hook, headless=headless)
    report_path = workspace / "artifacts" / report["task"] / "cloak_probe_report.yaml"
    typer.echo(f"CloakBrowser available: {report['cloakbrowser']['available']}")
    typer.echo(f"Report: {report_path}")


@app.command("generate-ai")
def generate_ai(
    plan_file: Path = typer.Option(..., "--plan", "-p", help="Extraction Plan YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    model: str = typer.Option("deepseek-v4-flash", "--model", help="LLM model name."),
) -> None:
    """Use AI to generate Scrapy spider code from an Extraction Plan."""
    result = ai_generate(plan_file, workspace=workspace, model=model)
    typer.echo(f"AI codegen: {result['path']}")


@app.command("generate")
def generate(
    plan_file: Path = typer.Option(..., "--plan", "-p", help="Extraction Plan YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    kind: str = typer.Option("python", "--kind", help="Generator kind: python or scrapy."),
) -> None:
    """Generate extractor code from an Extraction Plan."""
    result = generate_spider(plan_file, workspace=workspace, kind=kind)
    typer.echo(f"Generated: {result['path']}")


@app.command("run")
def run(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    plan_file: Path = typer.Option(..., "--plan", "-p", help="Extraction Plan YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    mode: str = typer.Option("artifacts", "--mode", help="Runner mode: artifacts or http."),
    timeout: int = typer.Option(20, "--timeout", help="HTTP timeout seconds for --mode http."),
) -> None:
    """Run an Extraction Plan against artifacts or live HTTP."""
    if mode == "http":
        result = run_http_plan(file, plan_file, workspace=workspace, timeout=timeout)
    else:
        result = run_plan(file, plan_file, workspace=workspace)
    typer.echo(f"Run task: {result['task']}")
    typer.echo(f"Items: {result['items_total']}")
    typer.echo(f"Result: {result['result_path']}")


@app.command("validate")
def validate(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    result_file: Path = typer.Option(..., "--result", "-r", help="Result JSON file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Validate result JSON against Spec expected values."""
    report = validate_results(file, result_file, workspace=workspace)
    typer.echo(f"Validation task: {report['task']}")
    typer.echo(f"OK: {report['ok']}")
    typer.echo(f"Hit rate: {report['field_hit_rate']}")


@app.command("signature-detect")
def signature_detect(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Detect suspicious signature/token parameters from network artifacts."""
    report = detect_signatures(file, workspace=workspace)
    report_path = workspace / "artifacts" / report["task"] / "signature_candidates.yaml"
    typer.echo(f"Signature candidates: {report['candidates_total']}")
    typer.echo(f"Groups: {len(report['groups'])}")
    typer.echo(f"Report: {report_path}")


@app.command("signature-verify")
def signature_verify(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Verify generated signer against collected signature samples."""
    report = verify_signer(file, workspace=workspace)
    typer.echo(f"Signature verify OK: {report['ok']}")
    typer.echo(f"Samples: {report['samples_passed']}/{report['samples_total']}")


@app.command("signature-generate")
def signature_generate(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Generate signer stub and signature manifest from collected samples."""
    report = generate_signer_skeleton(file, workspace=workspace)
    typer.echo(f"Signer stub: {report['signer_path']}")
    typer.echo(f"Groups: {len(report['groups'])}")


@app.command("signature-collect")
def signature_collect(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Collect signature input/output samples from trace and network artifacts."""
    report = collect_signature_samples(file, workspace=workspace)
    samples_path = workspace / "signatures" / report["task"] / "samples.json"
    typer.echo(f"Signature samples: {report['samples_total']}")
    typer.echo(f"Samples: {samples_path}")


@app.command("signature-hook")
def signature_hook(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Write runtime hook JavaScript for signature tracing."""
    report = write_hook_script(file, workspace=workspace)
    typer.echo(f"Hook script: {report['script_path']}")


@app.command("signature-diff")
def signature_diff(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Analyze dynamic/static behavior of detected signature candidates."""
    report = analyze_signature_diff(file, workspace=workspace)
    report_path = workspace / "artifacts" / report["task"] / "signature_diff.yaml"
    typer.echo(f"Signature diff groups: {report['groups_total']}")
    typer.echo(f"Report: {report_path}")


@app.command("discover")
def discover(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    target_task: str = typer.Option("detail", "--target-task", help="Task name for discovered URLs."),
    entity_type: str = typer.Option("item", "--entity-type", help="Entity type for discovered URLs."),
    include: list[str] = typer.Option([], "--include", help="Only include links containing this text/pattern. Can be repeated."),
) -> None:
    """Discover links from raw.html artifacts and emit TaskMessages."""
    report = run_discovery(file, workspace=workspace, target_task=target_task, entity_type=entity_type, include=include)
    typer.echo(f"Discovery task: {report['task']}")
    typer.echo(f"Messages: {report['messages_total']}")


@app.command("repair-ai")
def repair_ai(
    plan_file: Path = typer.Option(..., "--plan", "-p", help="Extraction Plan YAML file."),
    validation_file: Path = typer.Option(..., "--validation", "-v", help="Validation YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    model: str = typer.Option("deepseek-v4-flash", "--model", help="LLM model name."),
) -> None:
    """Use AI to repair a failing Extraction Plan based on validation errors."""
    report = ai_repair_plan(plan_file, validation_file, workspace=workspace, model=model)
    typer.echo(f"AI repair: {report['repaired']}")
    if report['repaired']:
        typer.echo(f"Fields fixed: {report['fields_fixed']}")


@app.command("repair-loop")
def repair_loop(
    file: Path = typer.Option(..., "--file", "-f", help="Spec YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
    max_attempts: int = typer.Option(3, "--max-attempts", help="Maximum repair attempts."),
) -> None:
    """Run deterministic repair loop: reverse→plan→generate→run→validate."""
    report = run_repair_loop(file, workspace=workspace, max_attempts=max_attempts)
    typer.echo(f"Repair loop task: {report['task']}")
    typer.echo(f"OK: {report['ok']}")
    typer.echo(f"Attempts: {report['attempts_total']}")


@app.command("repair")
def repair(
    validation_file: Path = typer.Option(..., "--validation", "-v", help="Validation YAML file."),
    workspace: Path = typer.Option(Path("workspace"), "--workspace", "-w", help="Workspace root."),
) -> None:
    """Build a repair report from validation failures."""
    report = build_repair_report(validation_file, workspace=workspace)
    typer.echo(f"Repair task: {report['task']}")
    typer.echo(f"Status: {report['status']}")
    typer.echo(f"Errors: {report['errors_total']}")


@app.command("version")
def version() -> None:
    """Print SpiderPilot version."""
    typer.echo("spiderpilot 0.1.0")


@app.command("web")
def web(host: str = "127.0.0.1", port: int = 8000):
    """Launch SpiderPilot web UI."""
    uvicorn.run(web_app, host=host, port=port, log_level="info")
