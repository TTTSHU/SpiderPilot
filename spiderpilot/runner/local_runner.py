"""Local runner MVP.

Runs generated extraction plans against existing raw.html artifacts without
requiring Scrapy yet. This keeps the MVP executable in minimal environments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec


def run_plan(spec_path: Path, plan_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    results = []
    artifact_root = workspace / "artifacts" / spec.name

    for sample in spec.samples:
        raw_path = artifact_root / sample.id / "raw.html"
        text = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path.exists() else ""
        item = {"_sample_id": sample.id, "_url": sample.url}
        for field_name, field_plan in (plan.get("fields") or {}).items():
            item[field_name] = _extract_mvp_value(text, field_plan, sample_id=sample.id)
        results.append(item)

    result_path = workspace / "results" / f"{spec.name}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"task": spec.name, "result_path": str(result_path), "items_total": len(results), "items": results}


def _extract_mvp_value(text: str, field_plan: dict[str, Any], sample_id: str | None = None) -> Any:
    evidence = field_plan.get("evidence") or {}
    if sample_id:
        sample_evidence = (evidence.get("samples") or {}).get(sample_id) or {}
        matched = sample_evidence.get("matched_value")
        if matched is not None and str(matched) in text:
            return matched
    matched = evidence.get("matched_value")
    if matched is not None and str(matched) in text:
        return matched
    return None
