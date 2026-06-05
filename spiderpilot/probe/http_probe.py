"""HTTP probe for collecting baseline page artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

import yaml

from spiderpilot.antibot.precheck import DEFAULT_HEADERS
from spiderpilot.spec import load_spec


@dataclass
class HttpProbeResult:
    sample_id: str
    url: str
    final_url: str | None
    status_code: int | None
    ok: bool
    error: str | None = None
    response_size: int = 0
    artifact_dir: str | None = None
    files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "ok": self.ok,
            "error": self.error,
            "response_size": self.response_size,
            "artifact_dir": self.artifact_dir,
            "files": self.files,
        }


def run_http_probe(spec_path: Path, workspace: Path = Path("workspace"), timeout: int = 20) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    results = []
    for sample in spec.samples:
        sample_dir = artifact_root / sample.id
        sample_dir.mkdir(parents=True, exist_ok=True)
        results.append(probe_url(sample.id, sample.url, sample_dir, timeout=timeout))

    report = {
        "version": 1,
        "task": spec.name,
        "samples_total": len(results),
        "samples_ok": sum(1 for result in results if result.ok),
        "results": [result.to_dict() for result in results],
    }
    report_path = artifact_root / "probe_report.yaml"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def probe_url(sample_id: str, url: str, artifact_dir: Path, timeout: int = 20) -> HttpProbeResult:
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    request = Request(url, headers=DEFAULT_HEADERS)

    body_bytes = b""
    headers: dict[str, str] = {}
    status_code: int | None = None
    final_url: str | None = None
    error: str | None = None

    try:
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
            final_url = response.geturl()
            headers = dict(response.headers.items())
            body_bytes = response.read()
    except HTTPError as exc:
        status_code = exc.code
        final_url = exc.geturl()
        headers = dict(exc.headers.items()) if exc.headers else {}
        body_bytes = exc.read()
        error = f"HTTPError: {exc.code}"
    except URLError as exc:
        error = f"URLError: {exc.reason}"
    except Exception as exc:  # pragma: no cover - defensive network boundary
        error = f"{type(exc).__name__}: {exc}"

    raw_path = artifact_dir / "raw.html"
    headers_path = artifact_dir / "headers.json"
    cookies_path = artifact_dir / "cookies.json"
    meta_path = artifact_dir / "meta.yaml"

    raw_path.write_bytes(body_bytes)
    headers_path.write_text(json.dumps(headers, ensure_ascii=False, indent=2), encoding="utf-8")
    cookies_path.write_text(json.dumps(_cookies_to_list(cookie_jar), ensure_ascii=False, indent=2), encoding="utf-8")

    ok = bool(status_code and 200 <= status_code < 400 and body_bytes)
    meta = {
        "sample_id": sample_id,
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "ok": ok,
        "error": error,
        "response_size": len(body_bytes),
        "files": {
            "raw_html": str(raw_path),
            "headers": str(headers_path),
            "cookies": str(cookies_path),
        },
    }
    meta_path.write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return HttpProbeResult(
        sample_id=sample_id,
        url=url,
        final_url=final_url,
        status_code=status_code,
        ok=ok,
        error=error,
        response_size=len(body_bytes),
        artifact_dir=str(artifact_dir),
        files={
            "raw_html": str(raw_path),
            "headers": str(headers_path),
            "cookies": str(cookies_path),
            "meta": str(meta_path),
        },
    )


def _cookies_to_list(cookie_jar: CookieJar) -> list[dict[str, Any]]:
    return [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.secure,
            "expires": cookie.expires,
        }
        for cookie in cookie_jar
    ]
