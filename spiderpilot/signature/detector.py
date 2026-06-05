"""Signature parameter detector MVP.

Scans CloakBrowser/HTTP network artifacts for suspicious query/header keys such
as sign, token, timestamp, x-bogus, a_bogus, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import json
import yaml

from spiderpilot.spec import load_spec

SIGNATURE_KEYWORDS = [
    "sign",
    "signature",
    "sig",
    "token",
    "auth",
    "nonce",
    "timestamp",
    "ts",
    "w_rid",
    "wts",
    "x-bogus",
    "a_bogus",
    "x-sign",
    "x-signature",
    "x-api-sign",
    "x-token",
    "x-timestamp",
    "anti_content",
    "x-kpsdk",
]

DYNAMIC_HINT_KEYS = {"timestamp", "ts", "t", "nonce", "wts"}


@dataclass
class SignatureCandidate:
    sample_id: str
    request_url: str
    location: str
    key: str
    value_sample: str
    confidence: float
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "request_url": self.request_url,
            "location": self.location,
            "key": self.key,
            "value_sample": self.value_sample,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


def detect_signatures(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    candidates: list[SignatureCandidate] = []
    for sample in spec.samples:
        candidates.extend(_scan_sample_network(sample.id, artifact_root / sample.id))
    grouped = _group_candidates(candidates)
    report = {
        "version": 1,
        "task": spec.name,
        "candidates_total": len(candidates),
        "groups": grouped,
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    out_path = artifact_root / "signature_candidates.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _scan_sample_network(sample_id: str, sample_dir: Path) -> list[SignatureCandidate]:
    candidates: list[SignatureCandidate] = []
    network_files = [sample_dir / "network.json", sample_dir / "cloak" / "network.json"]
    for network_file in network_files:
        if not network_file.exists():
            continue
        try:
            entries = json.loads(network_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url") or ""
            candidates.extend(_scan_url(sample_id, url))
            candidates.extend(_scan_headers(sample_id, url, entry.get("request_headers") or {}, "request_header"))
            candidates.extend(_scan_headers(sample_id, url, entry.get("response_headers") or {}, "response_header"))
    return candidates


def _scan_url(sample_id: str, url: str) -> list[SignatureCandidate]:
    parsed = urlparse(url)
    candidates = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        confidence, reasons = _score_key_value(key, value, location="query")
        if confidence > 0:
            candidates.append(
                SignatureCandidate(
                    sample_id=sample_id,
                    request_url=url,
                    location="query",
                    key=key,
                    value_sample=value[:160],
                    confidence=confidence,
                    evidence={"reasons": reasons, "path": parsed.path},
                )
            )
    return candidates


def _scan_headers(sample_id: str, url: str, headers: dict[str, Any], location: str) -> list[SignatureCandidate]:
    candidates = []
    for key, value in headers.items():
        value_text = str(value)
        confidence, reasons = _score_key_value(key, value_text, location=location)
        if confidence > 0:
            candidates.append(
                SignatureCandidate(
                    sample_id=sample_id,
                    request_url=url,
                    location=location,
                    key=key,
                    value_sample=value_text[:160],
                    confidence=confidence,
                    evidence={"reasons": reasons},
                )
            )
    return candidates


def _score_key_value(key: str, value: str, location: str) -> tuple[float, list[str]]:
    key_l = key.lower()
    value_l = value.lower()
    reasons = []
    score = 0.0
    if any(keyword in key_l for keyword in SIGNATURE_KEYWORDS):
        score += 0.55
        reasons.append("signature_keyword_key")
    if key_l in DYNAMIC_HINT_KEYS:
        score += 0.2
        reasons.append("dynamic_hint_key")
    if location.endswith("header") and key_l.startswith("x-"):
        score += 0.1
        reasons.append("custom_x_header")
    if _looks_hash_like(value):
        score += 0.2
        reasons.append("hash_like_value")
    if len(value) >= 24 and any(ch.isdigit() for ch in value) and any(ch.isalpha() for ch in value):
        score += 0.1
        reasons.append("long_mixed_value")
    if not reasons:
        return 0.0, []
    return round(min(score, 0.98), 4), reasons


def _looks_hash_like(value: str) -> bool:
    if len(value) in {32, 40, 64} and all(ch in "0123456789abcdefABCDEF" for ch in value):
        return True
    if len(value) > 20 and all(ch.isalnum() or ch in "-_=." for ch in value):
        return True
    return False


def _group_candidates(candidates: list[SignatureCandidate]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (candidate.location, candidate.key.lower())
        group = groups.setdefault(
            key,
            {
                "location": candidate.location,
                "key": candidate.key,
                "samples": set(),
                "requests": set(),
                "best_confidence": 0.0,
                "value_samples": [],
            },
        )
        group["samples"].add(candidate.sample_id)
        group["requests"].add(candidate.request_url)
        group["best_confidence"] = max(group["best_confidence"], candidate.confidence)
        if len(group["value_samples"]) < 5:
            group["value_samples"].append(candidate.value_sample)
    result = []
    for group in groups.values():
        result.append(
            {
                "location": group["location"],
                "key": group["key"],
                "samples_matched": len(group["samples"]),
                "requests_matched": len(group["requests"]),
                "best_confidence": group["best_confidence"],
                "value_samples": group["value_samples"],
            }
        )
    return sorted(result, key=lambda g: (g["best_confidence"], g["samples_matched"]), reverse=True)
