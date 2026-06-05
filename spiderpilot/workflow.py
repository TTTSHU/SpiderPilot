"""End-to-end SpiderPilot workflow orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.antibot.precheck import run_antibot_precheck
from spiderpilot.generator.codegen import generate_spider
from spiderpilot.planner.extraction_plan import build_extraction_plan
from spiderpilot.probe.http_probe import run_http_probe
from spiderpilot.repair.auto_repair import build_repair_report
from spiderpilot.reverse.locator import run_reverse
from spiderpilot.runner.local_runner import run_plan
from spiderpilot.spec import build_task_summary, load_spec, prepare_task_workspace, write_task_summary
from spiderpilot.validator.result_validator import validate_results


def create_task(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    task_workspace = prepare_task_workspace(spec, source_path=spec_path, workspace=workspace)
    summary = build_task_summary(spec, task_workspace)
    write_task_summary(summary, task_workspace.summary_path)
    return {"spec": spec, "workspace": task_workspace, "summary": summary}


def run_all(spec_path: Path, workspace: Path = Path("workspace"), timeout: int = 20, skip_network: bool = False) -> dict[str, Any]:
    """Run the full MVP workflow.

    If skip_network is True, existing raw.html artifacts are reused and antibot/probe
    are skipped. This is useful for tests and offline fixtures.
    """
    created = create_task(spec_path, workspace=workspace)
    spec = created["spec"]
    copied_spec_path = created["workspace"].spec_path

    report: dict[str, Any] = {
        "version": 1,
        "task": spec.name,
        "steps": {},
    }

    if not skip_network:
        report["steps"]["antibot"] = run_antibot_precheck(copied_spec_path, workspace=workspace, timeout=timeout)
        report["steps"]["probe"] = run_http_probe(copied_spec_path, workspace=workspace, timeout=timeout)
    else:
        report["steps"]["antibot"] = {"skipped": True}
        report["steps"]["probe"] = {"skipped": True}

    report["steps"]["reverse"] = run_reverse(copied_spec_path, workspace=workspace)
    plan = build_extraction_plan(copied_spec_path, workspace=workspace)
    report["steps"]["plan"] = plan
    plan_path = workspace / "plans" / f"{spec.name}.yaml"
    report["steps"]["generate"] = generate_spider(plan_path, workspace=workspace)
    report["steps"]["run"] = run_plan(copied_spec_path, plan_path, workspace=workspace)
    result_path = workspace / "results" / f"{spec.name}.json"
    validation = validate_results(copied_spec_path, result_path, workspace=workspace)
    report["steps"]["validate"] = validation
    validation_path = workspace / "results" / f"{spec.name}_validation.yaml"
    report["steps"]["repair"] = build_repair_report(validation_path, workspace=workspace)

    report["ok"] = bool(validation.get("ok"))
    report_path = workspace / "results" / f"{spec.name}_workflow.yaml"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(yaml.safe_dump(_compact_report(report), allow_unicode=True, sort_keys=False), encoding="utf-8")
    report["workflow_report_path"] = str(report_path)
    return report


def _compact_report(report: dict[str, Any]) -> dict[str, Any]:
    """Keep workflow report readable by dropping bulky nested artifacts."""
    compact = {"version": report["version"], "task": report["task"], "ok": report.get("ok"), "steps": {}}
    for name, step in (report.get("steps") or {}).items():
        if isinstance(step, dict):
            compact["steps"][name] = {
                key: value
                for key, value in step.items()
                if key not in {"results", "fields", "items"}
            }
        else:
            compact["steps"][name] = step
    return compact
