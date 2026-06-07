"""CloakBrowser (Playwright) probe for SpiderPilot.

Uses cloakbrowser.launch() which returns a Playwright Browser with stealth
features (patchright/chromium). This is the same approach used in the
datadome-cookie project and handles JS challenges better than raw CDP.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spiderpilot.spec import load_spec


def capture_with_cloakbrowser(
    url: str,
    artifact_dir: Path,
    wait_seconds: float = 15.0,
    headless: bool = True,
    stealth: bool = True,
) -> dict[str, Any]:
    """Launch CloakBrowser, navigate, and save rendered page + network artifacts."""
    from cloakbrowser import launch

    artifact_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = artifact_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    browser = launch(headless=headless, stealth_args=stealth)
    try:
        context = browser.new_context()
        page = context.new_page()

        # Collect network responses (XHR/Fetch)
        network_responses: list[dict[str, Any]] = []
        def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "").lower()
                if "json" in ct:
                    body = resp.body()[:500_000]
                    try:
                        data = json.loads(body.decode("utf-8", errors="replace"))
                    except Exception:
                        data = body.decode("utf-8", errors="replace")
                    network_responses.append({
                        "url": resp.url,
                        "status": resp.status,
                        "content_type": ct,
                        "body": data,
                    })
            except Exception:
                pass
        page.on("response", on_response)

        # Navigate
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Wait extra time for JS challenges / dynamic content
        time.sleep(wait_seconds)

        # Get rendered HTML
        rendered_html = page.content()
        (artifact_dir / "rendered.html").write_text(rendered_html, encoding="utf-8")

        # Get cookies
        cookies = context.cookies()
        (artifact_dir / "cookies.json").write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")

        # Get storage
        storage = {
            "localStorage": page.evaluate("() => JSON.parse(JSON.stringify(window.localStorage))"),
            "sessionStorage": page.evaluate("() => JSON.parse(JSON.stringify(window.sessionStorage))"),
        }
        (artifact_dir / "storage.json").write_text(json.dumps(storage, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save JSON network responses
        for i, entry in enumerate(network_responses):
            resp_path = responses_dir / f"response_{i}.json"
            resp_path.write_text(json.dumps(entry["body"], ensure_ascii=False, indent=2), encoding="utf-8")

        # Save simplified network list
        network_list = [
            {"url": entry["url"], "status": entry["status"], "content_type": entry["content_type"]}
            for entry in network_responses
        ]
        (artifact_dir / "network.json").write_text(json.dumps(network_list, ensure_ascii=False, indent=2), encoding="utf-8")

        report = {
            "url": url,
            "network_total": len(network_list),
            "json_responses_total": len(network_responses),
            "cookies_total": len(cookies),
            "rendered_html_size": len(rendered_html),
            "artifact_dir": str(artifact_dir),
        }
        (artifact_dir / "cloak_capture.yaml").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report
    finally:
        browser.close()
