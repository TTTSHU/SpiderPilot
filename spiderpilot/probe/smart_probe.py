"""Smart probe: CloakBrowser first, curl_cffi replay.

Flow:
1. CloakBrowser opens page, captures real browser headers, cookies, API responses.
2. Extract the most important API requests (XHR/fetch/GraphQL).
3. Replay those requests with curl_cffi (TLS impersonation) for clean, reproducible artifacts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import curl_cffi.requests
import yaml

from spiderpilot.spec import SampleSpec, load_spec



def _write_progress(artifact_dir: Path, step: str, detail: str = "") -> None:
    """Write progress to file so Web UI can poll it."""
    (artifact_dir / "probe_progress.txt").write_text(
        f"{step}\n{detail}", encoding="utf-8"
    )

def smart_probe(
    spec_path: Path,
    workspace: Path,
    wait_seconds: float = 8.0,
    match_patterns: tuple[str, ...] = (),
    impersonate: str = "chrome131",
) -> dict[str, Any]:
    """Run smart probe for all samples."""
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    results = []

    for sample in spec.samples:
        sample_dir = artifact_root / sample.id
        sample_dir.mkdir(parents=True, exist_ok=True)
        result = _probe_sample(sample, sample_dir, wait_seconds, match_patterns, impersonate)
        results.append(result)

    report = {"version": 1, "task": spec.name, "samples": results}
    (artifact_root / "smart_probe.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return report


def _probe_sample(
    sample: SampleSpec,
    sample_dir: Path,
    wait_seconds: float,
    match_patterns: tuple[str, ...],
    impersonate: str,
) -> dict[str, Any]:
    """Probe a single URL: CloakBrowser first, then curl_cffi replay."""
    from cloakbrowser import launch

    responses_dir = sample_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    cloak_dir = sample_dir / "cloak"
    cloak_dir.mkdir(parents=True, exist_ok=True)
    cloak_responses_dir = cloak_dir / "responses"
    cloak_responses_dir.mkdir(parents=True, exist_ok=True)

    print(f"Probing {sample.id}: {sample.url}", flush=True)

    # ============================================================
    # Step 1: CloakBrowser capture
    # ============================================================
    print("  CloakBrowser: launching...", flush=True)
    _write_progress(sample_dir, "CloakBrowser: opening page...")
    browser = launch(headless=True, stealth_args=True)
    api_requests: list[dict[str, Any]] = []
    browser_cookies: list[dict[str, str]] = []

    try:
        context = browser.new_context()
        page = context.new_page()

        def on_request(request):
            matches = not match_patterns or any(p in request.url for p in match_patterns)
            if matches and request.resource_type in ("xhr", "fetch"):
                api_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "resource_type": request.resource_type,
                    "post_data": request.post_data,
                })

        def on_response(response):
            ct = (response.headers.get("content-type") or "").lower()
            if "json" in ct:
                try:
                    body = response.body()[:500_000]
                    data = json.loads(body.decode("utf-8", errors="replace"))
                    file_index = len(list(cloak_responses_dir.glob("*.json")))
                    resp_path = cloak_responses_dir / f"response_{file_index}.json"
                    resp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)
        page.goto(sample.url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(wait_seconds)

        rendered = page.content()
        (cloak_dir / "rendered.html").write_text(rendered, encoding="utf-8")
        browser_cookies = context.cookies()
        (cloak_dir / "cookies.json").write_text(json.dumps(browser_cookies, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"  CloakBrowser: html={len(rendered)}b api_requests={len(api_requests)} api_responses={len(list(cloak_responses_dir.glob('*.json')))} cookies={len(browser_cookies)}", flush=True)
        _write_progress(sample_dir, f"CloakBrowser: captured {len(api_requests)} API requests")
    finally:
        browser.close()

    # ============================================================
    # Step 2: Replay with curl_cffi
    _write_progress(sample_dir, "curl_cffi: replaying API requests...")
    # ============================================================
    curl_success = 0
    curl_responses: list[dict[str, Any]] = []

    if api_requests:
        print(f"  curl_cffi: replaying {len(api_requests)} requests...", flush=True)
        session = curl_cffi.requests.Session()
        domain = urlparse(sample.url).netloc
        for c in browser_cookies:
            if c.get("name") and c.get("value"):
                session.cookies.set(c["name"], c["value"], domain=domain)

        seen_urls: set[str] = set()
        for req in api_requests[:10]:
            req_url = req["url"]
            if req_url in seen_urls:
                continue
            seen_urls.add(req_url)

            headers = {}
            skip = {"host", "content-length", "connection", "accept-encoding",
                    "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest",
                    "sec-fetch-user", "cookie"}
            for k, v in (req.get("headers") or {}).items():
                if k.lower() in skip or k.startswith(":"):
                    continue
                headers[k] = v

            method = req["method"]
            post_data = req.get("post_data")

            try:
                if method == "POST":
                    resp = session.post(req_url, headers=headers, data=post_data,
                                        impersonate=impersonate, timeout=30)
                else:
                    resp = session.get(req_url, headers=headers,
                                       impersonate=impersonate, timeout=30)

                body = resp.text
                is_json = body.strip().startswith("{")
                # Check if blocked: HTML response means anti-bot
                body_lower = body.lower()[:500] if body else ""
                is_html = body_lower.startswith("<!doctype") or body_lower.startswith("<html")
                is_challenge = any(w in body_lower for w in ('challenge-platform', 'captcha', 'cf_chl'))
                blocked = ((is_html and not is_json) or resp.status_code in (403, 503)) and not is_challenge

                if not blocked:
                    # Save to main responses dir
                    resp_path = responses_dir / f"curl_{len(curl_responses)}.json"
                    try:
                        if is_json:
                            parsed = json.loads(body)
                            resp_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                        else:
                            resp_path.write_text(body, encoding="utf-8")
                    except Exception:
                        resp_path.write_text(body, encoding="utf-8")

                    curl_success += 1
                    curl_responses.append({
                        "url": req_url, "method": method,
                        "status_code": resp.status_code,
                        "is_json": is_json, "file": str(resp_path),
                    })
                    print(f"    OK [{resp.status_code}] {req_url[:60]}", flush=True)
                else:
                    print(f"    BLOCKED [{resp.status_code}] {req_url[:60]} (curl_cffi also blocked)", flush=True)
            except Exception as e:
                print(f"    ERR {req_url[:60]}: {e}", flush=True)
    else:
        print("  curl_cffi: no API requests to replay", flush=True)

    # ============================================================
    # Step 3: Determine result
    # ============================================================
    # Only consider curl_cffi successful if most replayed requests succeeded
    curl_ok = curl_success > 0 and (len(api_requests) == 0 or curl_success >= len(api_requests) * 0.5)
    if curl_ok:
        probe_method = "curl_cffi"
        status_tag = "ok"
        _write_progress(sample_dir, "Done: curl_cffi successful")
    else:
        # curl_cffi blocked: copy CloakBrowser responses to main dir
        import shutil
        for cf in sorted(cloak_responses_dir.glob("*.json")):
            dst = responses_dir / cf.name
            if not dst.exists():
                shutil.copy2(cf, dst)
                curl_success += 1
        probe_method = "cloakbrowser"
        status_tag = "blocked_curl_replay_blocked" if api_requests else "no_api_requests"
        _write_progress(sample_dir, "Done: using CloakBrowser data")
        print(f"  curl_cffi: BLOCKED -> using CloakBrowser responses ({curl_success} files)", flush=True)
        _write_progress(sample_dir, f"curl_cffi blocked, using CloakBrowser data ({curl_success} responses)")

    return {
        "sample_id": sample.id,
        "url": sample.url,
        "probe_method": probe_method,
        "status": status_tag,
        "curl_success": curl_success,
        "api_requests": len(api_requests),
        "curl_responses": len(curl_responses),
    }
