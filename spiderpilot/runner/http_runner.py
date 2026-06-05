"""HTTP runner MVP.

Fetches Spec sample URLs directly, applies a JSON-response Extraction Plan, and
writes result JSON. This is separate from the artifacts runner so users can
validate a plan against live HTTP without Scrapy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

from spiderpilot.antibot.precheck import DEFAULT_HEADERS
from spiderpilot.reverse.json_locator import get_json_path
from spiderpilot.spec import load_spec


def run_http_plan(spec_path: Path, plan_path: Path, workspace: Path = Path("workspace"), timeout: int = 20) -> dict[str, Any]:
    spec = load_spec(spec_path)
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    results = []
    errors = []
    for sample in spec.samples:
        item = {"_sample_id": sample.id, "_url": sample.url}
        try:
            data = _fetch_json(sample.url, timeout=timeout)
            for field_name, field_plan in (plan.get("fields") or {}).items():
                item[field_name] = _extract_live_json_value(data, field_plan)
        except Exception as exc:
            errors.append({"sample_id": sample.id, "url": sample.url, "error": f"{type(exc).__name__}: {exc}"})
            for field_name in spec.fields:
                item[field_name] = None
        results.append(item)

    result_path = workspace / "results" / f"{spec.name}_http.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"task": spec.name, "result_path": str(result_path), "items_total": len(results), "errors": errors}
    report_path = workspace / "results" / f"{spec.name}_http_run.yaml"
    report_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _fetch_json(url: str, timeout: int = 20) -> Any:
    req = Request(url, headers={**DEFAULT_HEADERS, "Accept": "application/json,text/plain,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    return json.loads(body.decode("utf-8", errors="replace"))


def _extract_live_json_value(data: Any, field_plan: dict[str, Any]) -> Any:
    evidence = field_plan.get("evidence") or {}
    path = evidence.get("path") or field_plan.get("path")
    if isinstance(path, str) and path.startswith("json_response:"):
        path = path.split(":", 2)[2]
    if isinstance(path, str) and path.startswith("$"):
        return get_json_path(data, path)
    return evidence.get("matched_value")
