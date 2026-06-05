"""Field value backtracking for reverse analysis MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import CrawlSpec, ExpectedValue, load_spec
from spiderpilot.reverse.json_locator import extract_embedded_json, find_json_paths


@dataclass
class FieldCandidate:
    field: str
    source: str
    path: str
    sample_id: str
    match_type: str
    matched_value: Any
    context: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "source": self.source,
            "path": self.path,
            "sample_id": self.sample_id,
            "match_type": self.match_type,
            "matched_value": self.matched_value,
            "context": self.context,
            "confidence": self.confidence,
        }


def run_reverse(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    all_candidates: list[FieldCandidate] = []

    for sample in spec.samples:
        raw_path = artifact_root / sample.id / "raw.html"
        if not raw_path.exists():
            continue
        text = raw_path.read_text(encoding="utf-8", errors="replace")
        for field_name, expected in sample.expected.items():
            all_candidates.extend(locate_expected_in_text(field_name, expected, sample.id, text))
            all_candidates.extend(locate_expected_in_embedded_json(field_name, expected, sample.id, text))

    grouped = group_candidates(spec, all_candidates)
    report = {
        "version": 1,
        "task": spec.name,
        "source": "raw_html",
        "samples_total": len(spec.samples),
        "fields_total": len(spec.fields),
        "candidates_total": len(all_candidates),
        "fields": grouped,
    }
    out_path = artifact_root / "candidates.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def locate_expected_in_text(field_name: str, expected: ExpectedValue, sample_id: str, text: str) -> list[FieldCandidate]:
    candidates: list[FieldCandidate] = []
    if expected.equals is not None:
        candidates.extend(_find_value(field_name, sample_id, text, str(expected.equals), "equals", 0.75))
    for value in expected.contains or []:
        candidates.extend(_find_value(field_name, sample_id, text, str(value), "contains", 0.65))
    for value in expected.contains_any or []:
        candidates.extend(_find_value(field_name, sample_id, text, str(value), "contains_any", 0.55))
    return candidates


def locate_expected_in_embedded_json(field_name: str, expected: ExpectedValue, sample_id: str, html: str) -> list[FieldCandidate]:
    candidates: list[FieldCandidate] = []
    docs = extract_embedded_json(html)
    expected_values: list[tuple[str, str, float]] = []
    if expected.equals is not None:
        expected_values.append((str(expected.equals), "equals", 0.9))
    for value in expected.contains or []:
        expected_values.append((str(value), "contains", 0.8))
    for value in expected.contains_any or []:
        expected_values.append((str(value), "contains_any", 0.7))

    for doc_index, doc in enumerate(docs):
        for value, match_type, confidence in expected_values:
            for hit in find_json_paths(doc.data, value):
                candidates.append(
                    FieldCandidate(
                        field=field_name,
                        source=doc.source,
                        path=f"json_doc:{doc_index}:{hit['path']}",
                        sample_id=sample_id,
                        match_type=match_type,
                        matched_value=hit["value"],
                        context=f"{doc.source} {hit['path']}",
                        confidence=confidence,
                    )
                )
    return candidates


def group_candidates(spec: CrawlSpec, candidates: list[FieldCandidate]) -> dict[str, Any]:
    grouped: dict[str, Any] = {}
    for field_name in spec.fields:
        field_candidates = [candidate for candidate in candidates if candidate.field == field_name]
        samples_matched = sorted({candidate.sample_id for candidate in field_candidates})
        grouped[field_name] = {
            "samples_matched": len(samples_matched),
            "samples_total": len(spec.samples),
            "hit_rate": round(len(samples_matched) / len(spec.samples), 4) if spec.samples else 0,
            "best_confidence": max((candidate.confidence for candidate in field_candidates), default=0),
            "candidates": [candidate.to_dict() for candidate in field_candidates[:20]],
        }
    return grouped


def _find_value(
    field_name: str,
    sample_id: str,
    text: str,
    value: str,
    match_type: str,
    confidence: float,
) -> list[FieldCandidate]:
    if not value:
        return []
    candidates: list[FieldCandidate] = []
    start = 0
    max_hits = 10
    while len(candidates) < max_hits:
        index = text.find(value, start)
        if index < 0:
            break
        context_start = max(index - 120, 0)
        context_end = min(index + len(value) + 120, len(text))
        context = text[context_start:context_end].replace("\n", " ").strip()
        candidates.append(
            FieldCandidate(
                field=field_name,
                source="raw_html",
                path=f"text_offset:{index}",
                sample_id=sample_id,
                match_type=match_type,
                matched_value=value,
                context=context,
                confidence=confidence,
            )
        )
        start = index + len(value)
    return candidates
