"""Anti-bot strategy analysis from precheck/probe reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec


def build_antibot_strategy(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    antibot = _load_yaml(artifact_root / "antibot_report.yaml")
    probe = _load_yaml(artifact_root / "probe_report.yaml")
    cloak = _load_yaml(artifact_root / "cloak_probe_report.yaml")
    probe_diff = _load_yaml(artifact_root / "probe_diff.yaml")

    strategy = _decide_strategy(antibot, probe, cloak, probe_diff)
    report = {
        "version": 1,
        "task": spec.name,
        "strategy": strategy,
        "inputs": {
            "antibot_report": bool(antibot),
            "probe_report": bool(probe),
            "cloak_probe_report": bool(cloak),
            "probe_diff_report": bool(probe_diff),
        },
        "evidence": {
            "antibot_status": antibot.get("status"),
            "primary_vendor": antibot.get("primary_vendor"),
            "probe_samples_ok": probe.get("samples_ok"),
            "probe_samples_total": probe.get("samples_total"),
            "cloak_available": (cloak.get("cloakbrowser") or {}).get("available"),
            "flagged_samples": _flagged_samples(antibot),
            "probe_diff_strategy_hint": (probe_diff.get("summary") or {}).get("strategy_hint"),
            "probe_diff_signals": (probe_diff.get("summary") or {}).get("signals", {}),
            "fields_browser_only": (probe_diff.get("summary") or {}).get("fields_browser_only", 0),
        },
        "recommended_actions": _recommended_actions(strategy, antibot),
    }
    out_path = artifact_root / "antibot_strategy.yaml"
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _decide_strategy(antibot: dict[str, Any], probe: dict[str, Any], cloak: dict[str, Any], probe_diff: dict[str, Any] | None = None) -> str:
    probe_diff = probe_diff or {}
    diff_hint = (probe_diff.get("summary") or {}).get("strategy_hint")
    status = antibot.get("status")
    vendor = antibot.get("primary_vendor")
    samples_ok = int(probe.get("samples_ok") or 0)
    samples_total = int(probe.get("samples_total") or 0)
    cloak_available = bool((cloak.get("cloakbrowser") or {}).get("available"))

    if diff_hint == "cookie_or_browser_challenge":
        return "cookie_or_browser_challenge"
    if diff_hint == "browser_probe_required_for_reverse":
        return "browser_probe_required_for_reverse"
    if status == "clear" and samples_total and samples_ok == samples_total:
        return "direct_http"
    if vendor:
        return "inspect_cookie_or_signature_challenge"
    if samples_total and samples_ok == 0 and cloak_available:
        return "cloakbrowser_probe_required"
    if _looks_auth_required(antibot):
        return "auth_required"
    if _looks_manual_required(antibot):
        return "manual_required"
    if not probe:
        return "run_probe_first"
    return "needs_review"


def _recommended_actions(strategy: str, antibot: dict[str, Any]) -> list[str]:
    if strategy == "direct_http":
        return ["continue reverse", "prefer json_response or embedded_json sources"]
    if strategy == "browser_probe_required_for_reverse":
        return ["use CloakBrowser captured responses for reverse", "run spiderpilot reverse after cloak-probe --capture", "prefer cloak_json_response candidates"]
    if strategy == "cookie_or_browser_challenge":
        return ["compare HTTP blocked response with CloakBrowser success", "inspect cookies/challenge scripts", "derive cookie/signature flow when possible"]
    if strategy == "inspect_cookie_or_signature_challenge":
        vendor = antibot.get("primary_vendor") or "detected vendor"
        return [f"inspect {vendor} cookies/scripts", "compare HTTP vs CloakBrowser artifacts", "avoid browser as final runtime when possible"]
    if strategy == "cloakbrowser_probe_required":
        return ["run cloak-probe with network capture", "compare rendered/html/network against HTTP probe"]
    if strategy == "auth_required":
        return ["ask user for authorized cookie/state file", "rerun probe with auth state"]
    if strategy == "manual_required":
        return ["manual intervention required", "record challenge evidence"]
    if strategy == "run_probe_first":
        return ["run spiderpilot antibot", "run spiderpilot probe"]
    return ["inspect reports", "rerun with more samples"]


def _flagged_samples(antibot: dict[str, Any]) -> list[str]:
    return [r.get("sample_id") for r in antibot.get("results", []) if r.get("looks_like_challenge")]


def _looks_auth_required(antibot: dict[str, Any]) -> bool:
    text = str(antibot).lower()
    return any(k in text for k in ["login", "sign in", "unauthorized", "401"])


def _looks_manual_required(antibot: dict[str, Any]) -> bool:
    text = str(antibot).lower()
    return any(k in text for k in ["captcha", "hcaptcha", "turnstile", "slider"])


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
