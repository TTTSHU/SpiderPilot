"""AI-driven reverse analysis.

Replaces the heuristic locator with an LLM that analyses raw.html, JSON
responses, and expected field values to produce an Extraction Plan.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.reverse.html_compressor import collect_artifacts_smart
from spiderpilot.llm import chat_json
from spiderpilot.spec import CrawlSpec, load_spec

SYSTEM_PROMPT = """\
You are a web scraping expert AI. Your job is to analyze raw HTML and API responses
from a web page and locate where the target fields can be extracted.

You are given:
- A list of target fields with optional expected sample values.
- Raw HTML (may be truncated).
- Saved JSON API responses (if any).

For each field, determine:
1. The best data source: "json_response", "embedded_json", "html_selector", "html_xpath", or "raw_html_text".
2. The extraction path: JSONPath for JSON sources, CSS selector for html_selector, XPath for html_xpath.
3. A confidence score between 0 and 1.

Rules:
- Prefer JSON responses over HTML whenever possible.
- If a field value appears in a JSON response, use json_response with its JSONPath.
- If a field is only in HTML and has an id/data-testid/class, prefer html_selector.
- Use html_xpath only when CSS selector is not stable.
- Match expected sample values to locate the correct field.
- If you cannot find a field, set source to "unresolved" and confidence to 0.

Return a JSON object with:
{
  "source_type": "json_response" or "html" or "mixed",
  "source_confidence": <0-1>,
  "fields": {
    "field_name": {
      "source": "json_response",
      "path": "$.data.product.title",
      "confidence": 0.95,
      "note": "Found in product response JSON"
    },
    ...
  }
}
"""


def ai_reverse(spec_path: Path, workspace: Path = Path("workspace"), model: str = "deepseek-v4-flash") -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name

    messages = _build_reverse_prompt(spec, artifact_root)
    result = chat_json(messages, model=model, temperature=0.1, max_tokens=4096)

    plan = {
        "version": 1,
        "name": spec.name,
        "target_type": spec.target_type,
        "source": {
            "type": result.get("source_type", "unresolved"),
            "strategy": "ai_reverse",
            "confidence": result.get("source_confidence", 0),
            "sample_urls": [sample.url for sample in spec.samples],
        },
        "fields": _merge_fields(spec, result.get("fields", {})),
        "notes": ["AI-generated Extraction Plan. Review before running."],
    }
    plan_path = workspace / "plans" / f"{spec.name}.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (artifact_root / "ai_reverse_debug.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def _build_reverse_prompt(spec: CrawlSpec, artifact_root: Path) -> list[dict[str, str]]:
    fields_desc = []
    for name, field_spec in spec.fields.items():
        needed = "required" if field_spec.required else "optional"
        samples = []
        for sample in spec.samples:
            expected = sample.expected.get(name)
            if expected:
                if expected.equals:
                    samples.append(f'  sample {sample.id}: equals "{expected.equals}"')
                elif expected.contains:
                    samples.append(f'  sample {sample.id}: contains {expected.contains}')
        desc = f"- {name} ({needed}, {field_spec.type})"
        if samples:
            desc += "\n" + "\n".join(samples)
        fields_desc.append(desc)

    artifacts_text = _collect_artifacts(artifact_root, spec.samples)

    user = f"""Target fields:
{chr(10).join(fields_desc)}

Page artifacts:
- JSON responses are provided COMPLETE (no truncation).
- HTML is compressed text (tags stripped, only visible content).
{artifacts_text}

Analyze where each field can be extracted. Return JSON."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _collect_artifacts(artifact_root: Path, samples) -> str:
    parts = []
    for sample in samples:
        sample_dir = artifact_root / sample.id
        parts.append(f"\n=== Sample: {sample.id} ({sample.url}) ===")

        raw_html = _read_text(sample_dir / "raw.html")
        if raw_html:
            parts.append(f"--- raw.html (first 8000 chars) ---\n{raw_html[:8000]}")

        for response_dir in [sample_dir / "responses", sample_dir / "cloak" / "responses"]:
            if not response_dir.exists():
                continue
            for json_file in sorted(response_dir.glob("*.json")):
                text = _read_text(json_file)
                if text:
                    label = str(json_file.relative_to(sample_dir))
                    parts.append(f"--- JSON response: {label} (first 8000 chars) ---\n{text[:8000]}")
    return "\n".join(parts)


def _merge_fields(spec: CrawlSpec, ai_fields: dict[str, Any]) -> dict[str, Any]:
    merged = {}
    for name, field_spec in spec.fields.items():
        ai = ai_fields.get(name, {})
        merged[name] = {
            "source": ai.get("source", "unresolved"),
            "path": ai.get("path"),
            "confidence": ai.get("confidence", 0),
            "required": field_spec.required,
            "type": field_spec.type,
            "normalize": field_spec.normalize,
            "note": ai.get("note", ""),
            "status": ("resolved" if ai.get("source") else "unresolved"),
        }
    return merged


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
