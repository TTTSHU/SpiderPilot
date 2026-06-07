"""CloakBrowser + curl_cffi probe.

1. Launch CloakBrowser to capture real browser headers and cookies.
2. Replay API requests with curl_cffi (TLS fingerprint impersonation).
3. Save clean JSON responses for reverse analysis.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import curl_cffi.requests
import yaml


def cloak_curl_probe(
    url: str,
    artifact_dir: Path,
    wait_seconds: float = 8.0,
    match_url_patterns: tuple[str, ...] = (),
    impersonate: str = "chrome120",
) -> dict[str, Any]:
    """Full probe: CloakBrowser first, curl_cffi replay for API requests."""
    from cloakbrowser import launch

    artifact_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = artifact_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Step 1: CloakBrowser capture headers + cookies
    # ============================================================
    browser = launch(headless=True, stealth_args=True)
    api_requests: list[dict[str, Any]] = []
    browser_cookies: list[dict[str, str]] = []
    try:
        context = browser.new_context()
        page = context.new_page()

        def on_request(request):
            req = {
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "resource_type": request.resource_type,
                "post_data": request.post_data if request.method == "POST" else None,
            }
            matched = not match_url_patterns or any(p in request.url for p in match_url_patterns)
            if matched and request.resource_type in ("xhr", "fetch", "document"):
                api_requests.append(req)

        page.on("request", on_request)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(wait_seconds)

        rendered = page.content()
        (artifact_dir / "rendered.html").write_text(rendered, encoding="utf-8")
        browser_cookies = context.cookies()
        (artifact_dir / "cookies.json").write_text(json.dumps(browser_cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        browser.close()

    # ============================================================
    # Step 2: Replay with curl_cffi (TLS impersonation)
    # ============================================================
    session = curl_cffi.requests.Session()
    # Set browser cookies on the session
    for c in browser_cookies:
        if c.get("name") and c.get("value"):
            session.cookies.set(c["name"], c["value"], domain=urlparse(url).netloc)

    curl_responses: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for req in api_requests[:10]:
        req_url = req["url"]
        if req_url in seen_urls:
            continue
        seen_urls.add(req_url)

        # Build headers from browser capture
        headers = {}
        skip_headers = {"host", "content-length", "connection", "accept-encoding",
                        "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest",
                        "sec-fetch-user", "upgrade-insecure-requests", "pragma",
                        "cache-control", "cookie"}
        for k, v in (req.get("headers") or {}).items():
            if k.lower() in skip_headers or k.startswith(":"):
                continue
            headers[k] = v

        method = req["method"]
        post_data = req.get("post_data")

        try:
            if method == "POST":
                resp = session.post(req_url, headers=headers, data=post_data, impersonate=impersonate, timeout=30)
            else:
                resp = session.get(req_url, headers=headers, impersonate=impersonate, timeout=30)

            resp_body = resp.text
            resp_path = responses_dir / f"curl_{len(curl_responses)}.json"
            try:
                parsed = json.loads(resp_body)
                resp_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
            except json.JSONDecodeError:
                resp_path.write_text(resp_body, encoding="utf-8")

            curl_responses.append({
                "url": req_url,
                "method": method,
                "status_code": resp.status_code,
                "is_json": resp_body.strip().startswith("{"),
                "request_headers": {k: v for k, v in headers.items()},
                "response_file": str(resp_path),
                "response_size": len(resp_body),
            })
        except Exception as e:
            curl_responses.append({"url": req_url, "method": method, "status": f"error: {e}"})

    # ============================================================
    # Step 3: Report
    # ============================================================
    report = {
        "url": url,
        "api_requests_total": len(api_requests),
        "curl_replayed": len(curl_responses),
        "curl_succeeded": sum(1 for r in curl_responses if r.get("is_json")),
        "rendered_html_size": len(rendered),
        "curl_responses": curl_responses,
    }
    (artifact_dir / "cloak_curl_probe.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return report
