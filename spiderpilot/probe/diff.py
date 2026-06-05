"""HTTP vs CloakBrowser probe diff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import ExpectedValue, load_spec


def build_probe_diff(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    sample_reports = []
    for sample in spec.samples:
        sample_dir = artifact_root / sample.id
        raw_html = _read_text(sample_dir / "raw.html")
        rendered_html = _read_text(sample_dir / "cloak" / "rendered.html")
        http_json_files = sorted((sample_dir / "responses").glob("*.json")) if (sample_dir / "responses").exists() else []
        cloak_json_files = sorted((sample_dir / "cloak" / "responses").glob("*.json")) if (sample_dir / "cloak" / "responses").exists() else []
        sample_reports.append(
            {
                "sample_id": sample.id,
                "url": sample.url,
                "raw_html_size": len(raw_html),
                "rendered_html_size": len(rendered_html),
                "http_json_responses": len(http_json_files),
                "cloak_json_responses": len(cloak_json_files),
                "expected_presence": _expected_presence(sample.expected, raw_html, rendered_html, http_json_files, cloak_json_files),
                "signals": _signals(raw_html, rendered_html, http_json_files, cloak_json_files),
            }
        )
    report = {
        "version": 1,
        "task": spec.name,
        "samples_total": len(sample_reports),
        "samples": sample_reports,
        "summary": _summary(sample_reports),
    }
    out_path = artifact_root / "probe_diff.yaml"
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _expected_presence(expected: dict[str, ExpectedValue], raw_html: str, rendered_html: str, http_json_files: list[Path], cloak_json_files: list[Path]) -> dict[str, Any]:
    http_json_text = "\n".join(_read_text(p) for p in http_json_files)
    cloak_json_text = "\n".join(_read_text(p) for p in cloak_json_files)
    result = {}
    for field, matcher in expected.items():
        values = []
        if matcher.equals is not None:
            values.append(str(matcher.equals))
        values.extend(str(v) for v in (matcher.contains or []))
        values.extend(str(v) for v in (matcher.contains_any or []))
        result[field] = {
            "raw_html": any(v in raw_html for v in values),
            "rendered_html": any(v in rendered_html for v in values),
            "http_json": any(v in http_json_text for v in values),
            "cloak_json": any(v in cloak_json_text for v in values),
        }
    return result


def _signals(raw_html: str, rendered_html: str, http_json_files: list[Path], cloak_json_files: list[Path]) -> list[str]:
    signals = []
    if rendered_html and len(rendered_html) > len(raw_html) * 1.5:
        signals.append("browser_render_adds_content")
    if cloak_json_files and not http_json_files:
        signals.append("browser_discovered_json_api")
    if raw_html and not rendered_html:
        signals.append("cloak_render_missing")
    if _looks_blocked(raw_html) and rendered_html and not _looks_blocked(rendered_html):
        signals.append("http_blocked_browser_ok")
    return signals


def _summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    signals: dict[str, int] = {}
    fields_browser_only = 0
    for sample in samples:
        for signal in sample.get("signals", []):
            signals[signal] = signals.get(signal, 0) + 1
        for presence in sample.get("expected_presence", {}).values():
            if not presence.get("raw_html") and not presence.get("http_json") and (presence.get("rendered_html") or presence.get("cloak_json")):
                fields_browser_only += 1
    strategy_hint = "direct_http"
    if signals.get("browser_discovered_json_api") or fields_browser_only:
        strategy_hint = "browser_probe_required_for_reverse"
    if signals.get("http_blocked_browser_ok"):
        strategy_hint = "cookie_or_browser_challenge"
    return {"signals": signals, "fields_browser_only": fields_browser_only, "strategy_hint": strategy_hint}


def _looks_blocked(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in ["captcha", "access denied", "blocked", "forbidden", "challenge"])


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
