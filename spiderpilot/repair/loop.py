"""Repair loop MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.generator.codegen import generate_spider
from spiderpilot.planner.extraction_plan import build_extraction_plan
from spiderpilot.repair.auto_repair import build_repair_report
from spiderpilot.reverse.locator import run_reverse
from spiderpilot.runner.local_runner import run_plan
from spiderpilot.validator.result_validator import validate_results


def run_repair_loop(spec_path: Path, workspace: Path = Path("workspace"), max_attempts: int = 3) -> dict[str, Any]:
    """Retry reverse→plan→generate→run→validate when validation fails.

    MVP repair does not invent selectors yet; it reruns the deterministic pipeline
    after artifacts may have changed and records each attempt.
    """
    attempts = []
    task = None
    final_validation = None
    for attempt in range(1, max_attempts + 1):
        reverse_report = run_reverse(spec_path, workspace=workspace)
        task = reverse_report["task"]
        plan = build_extraction_plan(spec_path, workspace=workspace)
        plan_path = workspace / "plans" / f"{task}.yaml"
        generate_report = generate_spider(plan_path, workspace=workspace, kind="python")
        run_report = run_plan(spec_path, plan_path, workspace=workspace)
        result_path = workspace / "results" / f"{task}.json"
        validation = validate_results(spec_path, result_path, workspace=workspace)
        final_validation = validation
        attempts.append(
            {
                "attempt": attempt,
                "candidates_total": reverse_report.get("candidates_total"),
                "plan_confidence": (plan.get("source") or {}).get("confidence"),
                "generated": generate_report.get("path"),
                "items_total": run_report.get("items_total"),
                "ok": validation.get("ok"),
                "field_hit_rate": validation.get("field_hit_rate"),
                "errors_total": len(validation.get("errors") or []),
            }
        )
        if validation.get("ok"):
            break

    if task is None:
        task = Path(spec_path).stem
    validation_path = workspace / "results" / f"{task}_validation.yaml"
    repair_report = build_repair_report(validation_path, workspace=workspace) if validation_path.exists() else {}
    report = {
        "version": 1,
        "task": task,
        "ok": bool(final_validation and final_validation.get("ok")),
        "attempts_total": len(attempts),
        "attempts": attempts,
        "repair_report": repair_report,
    }
    out_path = workspace / "results" / f"{task}_repair_loop.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report
