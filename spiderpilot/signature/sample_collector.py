"""Signature sample collector MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import yaml

from spiderpilot.spec import load_spec


def collect_signature_samples(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    diff = _load_yaml(artifact_root / "signature_diff.yaml")
    classifications = {(g.get("location"), str(g.get("key", "")).lower()): g.get("classification") for g in diff.get("groups", [])}
    samples = []
    for sample in spec.samples:
        sample_dir = artifact_root / sample.id
        samples.extend(_samples_from_trace(sample.id, sample_dir, classifications))
        samples.extend(_samples_from_network(sample.id, sample_dir, classifications))
    # de-duplicate by sample/key/value/url
    deduped = []
    seen = set()
    for item in samples:
        key = (item.get("sample_id"), item.get("location"), item.get("key"), item.get("value"), item.get("url"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    report = {"version": 1, "task": spec.name, "samples_total": len(deduped), "samples": deduped}
    out_dir = workspace / "signatures" / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "samples.json").write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "samples.yaml").write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _samples_from_trace(sample_id: str, sample_dir: Path, classifications: dict[tuple[str, str], str | None]) -> list[dict[str, Any]]:
    out = []
    for trace_path in [sample_dir / "signature_trace.json", sample_dir / "cloak" / "signature_trace.json"]:
        if not trace_path.exists():
            continue
        try:
            events = json.loads(trace_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for event in events:
            payload = event.get("payload") or {}
            key = str(payload.get("key", ""))
            value = str(payload.get("value", ""))
            url = payload.get("url")
            location = "query" if event.get("type") in {"network_query_signature", "url_param_set"} else "header"
            out.append({
                "sample_id": sample_id,
                "source": "trace",
                "event_type": event.get("type"),
                "location": location,
                "key": key,
                "value": value,
                "url": url,
                "classification": classifications.get((location, key.lower())),
                "stack": event.get("stack"),
            })
    return out


def _samples_from_network(sample_id: str, sample_dir: Path, classifications: dict[tuple[str, str], str | None]) -> list[dict[str, Any]]:
    out = []
    for network_path in [sample_dir / "network.json", sample_dir / "cloak" / "network.json"]:
        if not network_path.exists():
            continue
        try:
            entries = json.loads(network_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for entry in entries:
            url = entry.get("url") or ""
            parsed = urlparse(url)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                if ("sign" in key.lower()) or ("token" in key.lower()) or ("nonce" in key.lower()) or ("timestamp" in key.lower()) or ("ts" == key.lower()):
                    out.append({
                        "sample_id": sample_id,
                        "source": "network",
                        "event_type": "query_param",
                        "location": "query",
                        "key": key,
                        "value": value,
                        "url": url,
                        "path": parsed.path,
                        "classification": classifications.get(("query", key.lower())),
                    })
            for key, value in (entry.get("request_headers") or {}).items():
                if ("sign" in key.lower()) or ("token" in key.lower()) or key.lower().startswith("x-"):
                    out.append({
                        "sample_id": sample_id,
                        "source": "network",
                        "event_type": "request_header",
                        "location": "request_header",
                        "key": key,
                        "value": str(value),
                        "url": url,
                        "path": parsed.path,
                        "classification": classifications.get(("request_header", key.lower())),
                    })
    return out


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
