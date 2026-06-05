"""Auto repair MVP.

The first MVP does not mutate plans yet. It converts validation failures into a
structured repair report so later iterations can feed LLM/codegen repair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def build_repair_report(validation_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    validation = yaml.safe_load(validation_path.read_text(encoding="utf-8")) or {}
    task = validation.get("task", validation_path.stem.replace("_validation", ""))
    errors = validation.get("errors") or []
    report = {
        "version": 1,
        "task": task,
        "status": "needs_repair" if errors else "no_repair_needed",
        "errors_total": len(errors),
        "suggested_actions": [_suggest_action(error) for error in errors],
    }
    out_path = workspace / "results" / f"{task}_repair.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _suggest_action(error: dict[str, Any]) -> dict[str, Any]:
    reason = error.get("reason")
    action = "rerun reverse with richer artifacts"
    if reason == "required_empty":
        action = "locate alternative source for required field"
    elif reason == "expected_mismatch":
        action = "compare expected value against raw_html/api responses and update plan"
    return {"error": error, "action": action}
