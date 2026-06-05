"""Candidate scoring helpers."""

from __future__ import annotations

SOURCE_PRIORITY = {
    "json_response": 1.0,
    "embedded_json": 0.92,
    "window_initial_state": 0.9,
    "window_preloaded_state": 0.88,
    "html_selector": 0.78,
    "html_xpath": 0.74,
    "raw_html": 0.65,
}


def score_candidate(candidate: dict) -> float:
    base = float(candidate.get("confidence") or 0)
    source_weight = SOURCE_PRIORITY.get(candidate.get("source"), 0.5)
    return round(base * 0.7 + source_weight * 0.3, 4)
