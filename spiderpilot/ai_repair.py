"""AI-driven repair — uses LLM to fix failing Extraction Plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.llm import chat_json

SYSTEM_REPAIR = """\
You are a web scraping repair expert. Given an Extraction Plan and validation
failures, determine which field paths are wrong and propose corrections.

Rules:
- If a field is empty and the source is json_response, check if the JSONPath
  might be wrong (wrong nesting, wrong key name, array vs object).
- If the source is html_selector, suggest alternative CSS/XPath selectors.
- Look at the error context for clues (actual page content, sample values).
- Propose the most likely correct path.

Return JSON:
{
  "repairs": {
    "field_name": {
      "action": "update_path",
      "source": "json_response",
      "path": "$.data.product.title",
      "reason": "Original path $.data.title was empty, likely nested under product"
    }
  },
  "notes": "...."
}
"""


def ai_repair_plan(plan_path: Path, validation_path: Path, workspace: Path = Path("workspace"), model: str = "deepseek-v4-flash") -> dict[str, Any]:
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    validation = yaml.safe_load(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}

    if validation.get("ok") or not validation.get("errors"):
        return {"repaired": False, "reason": "no errors to repair"}

    messages = [
        {"role": "system", "content": SYSTEM_REPAIR},
        {"role": "user", "content": f"Current Extraction Plan:\n{yaml.safe_dump(plan, allow_unicode=True, sort_keys=False)}\n\nValidation errors:\n{yaml.safe_dump(validation, allow_unicode=True, sort_keys=False)}\n\nPropose corrections. Return JSON."},
    ]
    repair = chat_json(messages, model=model, temperature=0.1, max_tokens=2048)
    repairs = repair.get("repairs", {})
    for field_name, fix in repairs.items():
        if field_name in plan.get("fields", {}):
            plan["fields"][field_name]["source"] = fix.get("source", plan["fields"][field_name].get("source"))
            plan["fields"][field_name]["path"] = fix.get("path", plan["fields"][field_name].get("path"))
            plan["fields"][field_name]["note"] = fix.get("reason", "")

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    repair_path = workspace / "results" / f"{plan['name']}_ai_repair.yaml"
    repair_path.write_text(yaml.safe_dump(repair, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"repaired": True, "fields_fixed": len(repairs), "report": str(repair_path)}
