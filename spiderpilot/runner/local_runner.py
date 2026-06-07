"""Local runner MVP.

Runs generated extraction plans against existing raw.html artifacts without
requiring Scrapy yet. This keeps the MVP executable in minimal environments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.reverse.json_locator import extract_embedded_json, get_json_path, load_json_file
from spiderpilot.runner.html_extract import extract_by_css_selector, extract_by_xpath
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
            item[field_name] = _extract_mvp_value(text, field_plan, sample_id=sample.id, sample_dir=raw_path.parent)
        results.append(item)

    result_path = workspace / "results" / f"{spec.name}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"task": spec.name, "result_path": str(result_path), "items_total": len(results), "items": results}


def _extract_mvp_value(text: str, field_plan: dict[str, Any], sample_id: str | None = None, sample_dir: Path | None = None) -> Any:
    evidence = field_plan.get("evidence") or {}
    if sample_id:
        sample_evidence = (evidence.get("samples") or {}).get(sample_id) or {}
        value = _extract_from_evidence(text, sample_evidence, sample_dir=sample_dir)
        if value is not None:
            return value
    return _extract_from_evidence(text, evidence if evidence else field_plan, sample_dir=sample_dir)


def _extract_from_evidence(text: str, evidence: dict[str, Any], sample_dir: Path | None = None) -> Any:
    path = evidence.get("path") if isinstance(evidence, dict) else None
    if isinstance(path, str) and path.startswith("json_doc:"):
        value = _extract_json_doc_path(text, path)
        if value is not None:
            return value
    if isinstance(path, str) and path.startswith("json_response:") and sample_dir is not None:
        value = _extract_json_response_path(sample_dir, path)
        if value is not None:
            return value
    if isinstance(path, str) and path.startswith("$") and sample_dir is not None:
        value = _extract_bare_json_path_from_responses(sample_dir, path)
        if value is not None:
            return value
    source = evidence.get("source")
    if source == "html_selector" or (isinstance(path, str) and _looks_like_css_selector(path)):
        value = extract_by_css_selector(text, path)
        if value is not None:
            return value
    if source == "html_xpath" or (isinstance(path, str) and path.startswith("//")):
        value = extract_by_xpath(text, path)
        if value is not None:
            return value
    matched = evidence.get("matched_value")
    if matched is not None and str(matched) in text:
        return matched
    return None


def _looks_like_css_selector(path: str | None) -> bool:
    if not isinstance(path, str):
        return False
    return path.startswith("#") or "[" in path or "." in path or path.isalpha()



def _extract_bare_json_path_from_responses(sample_dir, json_path):
    """Try bare JSONPath against all response JSON files."""
    for responses_dir in [sample_dir / "responses", sample_dir / "cloak" / "responses"]:
        if not responses_dir.exists():
            continue
        for json_file in sorted(responses_dir.glob("*.json")):
            data = load_json_file(json_file)
            if data is None:
                continue
            value = get_json_path(data, json_path)
            if value is not None:
                return value
    return None

def _extract_json_response_path(sample_dir: Path, path: str) -> Any:
    # path format: json_response:{filename}:$.a.b[0]
    try:
        _, filename, json_path = path.split(":", 2)
    except ValueError:
        return None
    if filename.startswith("cloak/"):
        response_path = sample_dir / "cloak" / "responses" / filename.split("/", 1)[1]
    else:
        response_path = sample_dir / "responses" / filename
    data = load_json_file(response_path)
    if data is None:
        return None
    return get_json_path(data, json_path)


def _extract_json_doc_path(text: str, path: str) -> Any:
    # path format: json_doc:{index}:$.a.b[0]
    try:
        _, index_text, json_path = path.split(":", 2)
        doc_index = int(index_text)
    except ValueError:
        return None
    docs = extract_embedded_json(text)
    if doc_index >= len(docs):
        return None
    return get_json_path(docs[doc_index].data, json_path)
