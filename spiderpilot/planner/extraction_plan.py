"""Extraction Plan builder MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec


def build_extraction_plan(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    candidates_path = artifact_root / "candidates.yaml"
    if not candidates_path.exists():
        raise FileNotFoundError(f"candidates not found: {candidates_path}. Run `spiderpilot reverse` first.")

    candidates = yaml.safe_load(candidates_path.read_text(encoding="utf-8")) or {}
    fields = {}
    for field_name, field_spec in spec.fields.items():
        field_candidates = (candidates.get("fields") or {}).get(field_name, {})
        best = _select_best_candidate(field_candidates.get("candidates") or [])
        if best:
            fields[field_name] = {
                "source": best.get("source", "raw_html"),
                "path": best.get("path"),
                "match_type": best.get("match_type"),
                "confidence": best.get("confidence", 0),
                "required": field_spec.required,
                "type": field_spec.type,
                "normalize": field_spec.normalize,
                "evidence": {
                    "samples_matched": field_candidates.get("samples_matched", 0),
                    "samples_total": field_candidates.get("samples_total", len(spec.samples)),
                    "hit_rate": field_candidates.get("hit_rate", 0),
                    "sample_id": best.get("sample_id"),
                    "matched_value": best.get("matched_value"),
                    "context": best.get("context"),
                    "samples": _sample_evidence(field_candidates.get("candidates") or []),
                },
            }
        else:
            fields[field_name] = {
                "source": None,
                "path": None,
                "confidence": 0,
                "required": field_spec.required,
                "type": field_spec.type,
                "normalize": field_spec.normalize,
                "evidence": {
                    "samples_matched": 0,
                    "samples_total": len(spec.samples),
                    "hit_rate": 0,
                },
                "status": "unresolved",
            }

    plan = {
        "version": 1,
        "name": spec.name,
        "target_type": spec.target_type,
        "source": {
            "type": "raw_html",
            "strategy": "text_offset_mvp",
            "confidence": _overall_confidence(fields),
        },
        "fields": fields,
        "notes": [
            "MVP plan generated from raw_html text offsets.",
            "Future versions should replace text offsets with CSS/XPath/JSONPath/API paths.",
        ],
    }

    plan_path = workspace / "plans" / f"{spec.name}.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return plan


def _sample_evidence(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    by_sample: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        sample_id = candidate.get("sample_id")
        if not sample_id:
            continue
        by_sample.setdefault(sample_id, []).append(candidate)
    for sample_id, sample_candidates in by_sample.items():
        best = _select_best_candidate(sample_candidates)
        if best:
            evidence[sample_id] = {
                "path": best.get("path"),
                "matched_value": best.get("matched_value"),
                "match_type": best.get("match_type"),
                "confidence": best.get("confidence", 0),
                "context": best.get("context"),
            }
    return evidence


def _select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda candidate: (candidate.get("confidence", 0), -len(str(candidate.get("path", "")))),
        reverse=True,
    )[0]


def _overall_confidence(fields: dict[str, Any]) -> float:
    confidences = [float(field.get("confidence") or 0) for field in fields.values()]
    if not confidences:
        return 0
    return round(sum(confidences) / len(confidences), 4)
