"""HTTP anti-bot precheck.

The precheck intentionally starts with a clean, no-cookie HTTP request. It is a
baseline detector, not a bypasser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

import yaml

from spiderpilot.spec import CrawlSpec, load_spec


DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "SpiderPilot/0.1 AntiBotPrecheck",
}

VENDOR_RULES = {
    "datadome": ["datadome", "ddsession", "ddoriginalreferrer", "geo.captcha-delivery.com"],
    "cloudflare": ["cf_clearance", "__cf_bm", "cf_chl", "turnstile", "cloudflare"],
    "akamai": ["_abck", "bm_sz", "ak_bmsc", "akamai", "sensor_data"],
    "perimeterx": ["_px", "_px3", "_pxvid", "px-captcha", "perimeterx"],
    "kasada": ["x-kpsdk", "kpsdk", "ips.js", "kasada"],
    "imperva": ["incap_ses", "visid_incap", "_incapsula", "imperva"],
    "shape_f5": ["f5_cspm", "shape", "shapesecurity", "ts", "big-ip"],
    "ruishu": ["412", "fssbbil1ugzbn7n", "nfbc sins2oyws".replace(" ", ""), "sdenv"],
    "bytedance": ["webmssdk", "byted_acrawler", "x-bogus", "a_bogus"],
}

BLOCK_KEYWORDS = [
    "captcha",
    "challenge",
    "access denied",
    "blocked",
    "forbidden",
    "verify you are human",
    "robot",
    "bot detection",
]


@dataclass
class PrecheckResult:
    sample_id: str
    url: str
    final_url: str | None
    status_code: int | None
    ok: bool
    looks_like_challenge: bool
    vendor: str | None
    confidence: float
    set_cookie_names: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "ok": self.ok,
            "looks_like_challenge": self.looks_like_challenge,
            "vendor": self.vendor,
            "confidence": self.confidence,
            "set_cookie_names": self.set_cookie_names,
            "evidence": self.evidence,
        }


def run_antibot_precheck(spec_path: Path, workspace: Path = Path("workspace"), timeout: int = 15) -> dict[str, Any]:
    spec = load_spec(spec_path)
    results = [precheck_url(sample.id, sample.url, timeout=timeout) for sample in spec.samples]
    report = build_report(spec, results)
    report_path = workspace / "artifacts" / spec.name / "antibot_report.yaml"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def precheck_url(sample_id: str, url: str, timeout: int = 15) -> PrecheckResult:
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    request = Request(url, headers=DEFAULT_HEADERS)
    body = ""
    headers: dict[str, str] = {}
    status_code: int | None = None
    final_url: str | None = None
    error: str | None = None

    try:
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
            final_url = response.geturl()
            headers = dict(response.headers.items())
            body = response.read(300_000).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status_code = exc.code
        final_url = exc.geturl()
        headers = dict(exc.headers.items()) if exc.headers else {}
        body = exc.read(300_000).decode("utf-8", errors="replace")
        error = f"HTTPError: {exc.code}"
    except URLError as exc:
        error = f"URLError: {exc.reason}"
    except Exception as exc:  # pragma: no cover - defensive network boundary
        error = f"{type(exc).__name__}: {exc}"

    set_cookie_names = _cookie_names(cookie_jar, headers)
    combined = "\n".join([url, final_url or "", str(status_code or ""), _headers_text(headers), body[:100_000]]).lower()
    vendor, confidence, vendor_hits = detect_vendor(combined, set_cookie_names)
    block_hits = [keyword for keyword in BLOCK_KEYWORDS if keyword in combined]
    challenge_status = status_code in {403, 407, 409, 412, 429, 503}
    looks_like_challenge = bool(vendor or block_hits or challenge_status)
    ok = bool(status_code and 200 <= status_code < 300 and not looks_like_challenge)

    return PrecheckResult(
        sample_id=sample_id,
        url=url,
        final_url=final_url,
        status_code=status_code,
        ok=ok,
        looks_like_challenge=looks_like_challenge,
        vendor=vendor,
        confidence=confidence,
        set_cookie_names=set_cookie_names,
        evidence={
            "error": error,
            "vendor_hits": vendor_hits,
            "block_keywords": block_hits,
            "challenge_status": challenge_status,
            "response_size_sampled": len(body),
            "headers_sample": {k: headers[k] for k in list(headers)[:12]},
        },
    )


def detect_vendor(text: str, cookie_names: list[str]) -> tuple[str | None, float, list[str]]:
    haystack = text + "\n" + "\n".join(cookie_names).lower()
    scored: list[tuple[int, str, list[str]]] = []
    for vendor, keywords in VENDOR_RULES.items():
        hits = [keyword for keyword in keywords if keyword.lower() in haystack]
        if hits:
            scored.append((len(hits), vendor, hits))
    if not scored:
        return None, 0.0, []
    scored.sort(reverse=True)
    count, vendor, hits = scored[0]
    confidence = min(0.5 + count * 0.15, 0.95)
    return vendor, round(confidence, 2), hits


def build_report(spec: CrawlSpec, results: list[PrecheckResult]) -> dict[str, Any]:
    detected = [result for result in results if result.looks_like_challenge]
    vendors = [result.vendor for result in detected if result.vendor]
    primary_vendor = max(set(vendors), key=vendors.count) if vendors else None
    status = "detected" if detected else "clear"
    return {
        "version": 1,
        "task": spec.name,
        "status": status,
        "primary_vendor": primary_vendor,
        "samples_total": len(results),
        "samples_flagged": len(detected),
        "results": [result.to_dict() for result in results],
        "recommended_next_step": _recommend_next_step(status, primary_vendor),
    }


def _recommend_next_step(status: str, vendor: str | None) -> list[str]:
    if status == "clear":
        return ["probe", "reverse"]
    steps = ["inspect antibot_report evidence", "run CloakBrowser probe for comparison"]
    if vendor:
        steps.append(f"analyze {vendor} cookie/signature characteristics")
    return steps


def _headers_text(headers: dict[str, str]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in headers.items())


def _cookie_names(cookie_jar: CookieJar, headers: dict[str, str]) -> list[str]:
    names = {cookie.name for cookie in cookie_jar}
    for key, value in headers.items():
        if key.lower() == "set-cookie":
            first = value.split(";", 1)[0]
            if "=" in first:
                names.add(first.split("=", 1)[0].strip())
    return sorted(names)
