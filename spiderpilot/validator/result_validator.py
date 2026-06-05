"""Result validation MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import ExpectedValue, load_spec


def validate_results(spec_path: Path, result_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    results = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else []
    by_sample = {item.get("_sample_id"): item for item in results}
    errors = []
    checks_total = 0
    checks_passed = 0

    for sample in spec.samples:
        item = by_sample.get(sample.id) or {}
        for field_name, field_spec in spec.fields.items():
            value = item.get(field_name)
            if field_spec.required:
                checks_total += 1
                if value not in (None, "", []):
                    checks_passed += 1
                else:
                    errors.append({"sample_id": sample.id, "field": field_name, "reason": "required_empty"})
        for field_name, expected in sample.expected.items():
            checks_total += 1
            value = item.get(field_name)
            if _matches_expected(value, expected):
                checks_passed += 1
            else:
                errors.append({"sample_id": sample.id, "field": field_name, "reason": "expected_mismatch", "value": value})

    report = {
        "version": 1,
        "task": spec.name,
        "ok": not errors,
        "checks_total": checks_total,
        "checks_passed": checks_passed,
        "field_hit_rate": round(checks_passed / checks_total, 4) if checks_total else 0,
        "errors": errors,
    }
    report_path = workspace / "results" / f"{spec.name}_validation.yaml"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _matches_expected(value: Any, expected: ExpectedValue) -> bool:
    if expected.equals is not None:
        return str(value) == str(expected.equals)
    if expected.contains:
        text = "\n".join(map(str, value)) if isinstance(value, list) else str(value)
        return all(str(part) in text for part in expected.contains)
    if expected.contains_any:
        text = "\n".join(map(str, value)) if isinstance(value, list) else str(value)
        return any(str(part) in text for part in expected.contains_any)
    return False
