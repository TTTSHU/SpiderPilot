"""Signature request diff analyzer MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec


def analyze_signature_diff(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    candidates_path = artifact_root / "signature_candidates.yaml"
    candidates_report = yaml.safe_load(candidates_path.read_text(encoding="utf-8")) if candidates_path.exists() else {}
    candidates = candidates_report.get("candidates") or []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        groups.setdefault((candidate.get("location"), str(candidate.get("key", "")).lower()), []).append(candidate)

    analyses = []
    for (location, key), items in groups.items():
        values = [str(item.get("value_sample", "")) for item in items]
        analyses.append(
            {
                "location": location,
                "key": key,
                "samples_total": len(items),
                "unique_values": len(set(values)),
                "classification": _classify_values(key, values),
                "value_shape": _value_shape(values),
                "request_paths": sorted({_path_from_url(item.get("request_url", "")) for item in items}),
            }
        )

    report = {"version": 1, "task": spec.name, "groups_total": len(analyses), "groups": analyses}
    out_path = artifact_root / "signature_diff.yaml"
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _classify_values(key: str, values: list[str]) -> str:
    key_l = key.lower()
    unique = set(values)
    if key_l in {"timestamp", "ts", "t", "wts"} or all(_looks_timestamp(v) for v in values if v):
        return "timestamp"
    if len(unique) == 1:
        return "stable_token"
    if all(_looks_hash(v) for v in values if v):
        return "hash_or_signature"
    if key_l in {"nonce"}:
        return "nonce_or_random"
    if len(unique) == len(values):
        return "dynamic_value"
    return "mixed"


def _value_shape(values: list[str]) -> dict[str, Any]:
    lengths = [len(v) for v in values]
    return {
        "min_len": min(lengths) if lengths else 0,
        "max_len": max(lengths) if lengths else 0,
        "all_numeric": all(v.isdigit() for v in values if v),
        "all_hex": all(all(ch in "0123456789abcdefABCDEF" for ch in v) for v in values if v),
    }


def _looks_timestamp(value: str) -> bool:
    return value.isdigit() and len(value) in {10, 13}


def _looks_hash(value: str) -> bool:
    return len(value) in {32, 40, 64} and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _path_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).path
    except Exception:
        return ""
