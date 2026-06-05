"""CloakBrowser CDP launcher and network capture MVP.

This module launches the CloakBrowser Chromium binary with a temporary profile
and Chrome DevTools Protocol enabled. CDP websocket transport uses the optional
`websocket-client` package when available.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from urllib.parse import parse_qsl, urlparse

from spiderpilot.signature.runtime_hook import HOOK_SCRIPT


@dataclass
class NetworkEntry:
    request_id: str
    url: str | None = None
    method: str | None = None
    status: int | None = None
    mime_type: str | None = None
    request_headers: dict[str, Any] = field(default_factory=dict)
    response_headers: dict[str, Any] = field(default_factory=dict)
    response_body_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class CDPClient:
    def __init__(self, ws_url: str):
        try:
            import websocket  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("websocket-client package is required for CloakBrowser CDP capture") from exc
        self.websocket = websocket
        self.ws = websocket.create_connection(ws_url, timeout=10)
        self._next_id = 1

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == msg_id:
                return msg

    def recv_event(self, timeout: float = 1.0) -> dict[str, Any] | None:
        old_timeout = self.ws.gettimeout()
        self.ws.settimeout(timeout)
        try:
            return json.loads(self.ws.recv())
        except Exception:
            return None
        finally:
            self.ws.settimeout(old_timeout)

    def close(self) -> None:
        self.ws.close()


def cloak_binary_path() -> str | None:
    exe = shutil.which("cloakbrowser")
    if not exe:
        return None
    proc = subprocess.run([exe, "info"], capture_output=True, text=True, timeout=20)
    for line in proc.stdout.splitlines():
        if line.strip().startswith("Binary:"):
            return line.split("Binary:", 1)[1].strip()
    return None


def capture_with_cloakbrowser(url: str, artifact_dir: Path, wait_seconds: float = 5.0, port: int = 9223, signature_hook: bool = False) -> dict[str, Any]:
    binary = cloak_binary_path()
    if not binary:
        raise RuntimeError("CloakBrowser binary not found. Run `cloakbrowser install` first.")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = artifact_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    user_data_dir = tempfile.mkdtemp(prefix="spiderpilot-cloak-")
    proc = subprocess.Popen(
        [
            binary,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            "--headless=new",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client: CDPClient | None = None
    try:
        ws_url = _wait_for_cdp_ws(port)
        client = CDPClient(ws_url)
        client.call("Page.enable")
        client.call("Network.enable")
        client.call("Runtime.enable")
        if signature_hook:
            client.call("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK_SCRIPT})
        client.call("Page.navigate", {"url": url})

        entries: dict[str, NetworkEntry] = {}
        signature_events: list[dict[str, Any]] = []
        console_events: list[dict[str, Any]] = []
        # addScriptToEvaluateOnNewDocument covers future documents; Runtime.evaluate
        # covers the currently loaded target as a fallback.
        if signature_hook:
            client.call("Runtime.evaluate", {"expression": HOOK_SCRIPT})
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            event = client.recv_event(timeout=0.5)
            if not event:
                continue
            method = event.get("method")
            params = event.get("params") or {}
            if method == "Runtime.consoleAPICalled":
                console_events.append(_compact_console_event(params))
                event = _parse_signature_console_event(params)
                if event:
                    signature_events.append(event)
            if method == "Network.requestWillBeSent":
                rid = params.get("requestId")
                req = params.get("request") or {}
                entry = entries.setdefault(rid, NetworkEntry(request_id=rid))
                entry.url = req.get("url")
                entry.method = req.get("method")
                entry.request_headers = req.get("headers") or {}
                if signature_hook:
                    signature_events.extend(_signature_events_from_request(entry.url or "", entry.request_headers))
            elif method == "Network.responseReceived":
                rid = params.get("requestId")
                resp = params.get("response") or {}
                entry = entries.setdefault(rid, NetworkEntry(request_id=rid))
                entry.url = entry.url or resp.get("url")
                entry.status = resp.get("status")
                entry.mime_type = resp.get("mimeType")
                entry.response_headers = resp.get("headers") or {}
            elif method == "Network.loadingFinished":
                rid = params.get("requestId")
                entry = entries.get(rid)
                if entry and _is_json_like(entry):
                    body_msg = client.call("Network.getResponseBody", {"requestId": rid})
                    body = ((body_msg.get("result") or {}).get("body"))
                    if body:
                        filename = f"response_{len(list(responses_dir.glob('*.json')))}.json"
                        path = responses_dir / filename
                        try:
                            parsed = json.loads(body)
                            path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                        except Exception:
                            path.write_text(body, encoding="utf-8")
                        entry.response_body_file = str(path)

        html_msg = client.call("Runtime.evaluate", {"expression": "document.documentElement.outerHTML", "returnByValue": True})
        html = (((html_msg.get("result") or {}).get("result") or {}).get("value")) or ""
        (artifact_dir / "rendered.html").write_text(html, encoding="utf-8")
        client.call("Page.captureScreenshot", {"format": "png"})
        # Screenshot data omitted in MVP to avoid base64 dependency surface in reports.
        network = [entry.to_dict() for entry in entries.values()]
        (artifact_dir / "network.json").write_text(json.dumps(network, ensure_ascii=False, indent=2), encoding="utf-8")
        if console_events:
            (artifact_dir / "console_events.json").write_text(json.dumps(console_events, ensure_ascii=False, indent=2), encoding="utf-8")
        if signature_events:
            (artifact_dir / "signature_trace.json").write_text(json.dumps(signature_events, ensure_ascii=False, indent=2), encoding="utf-8")
        report = {"url": url, "network_total": len(network), "json_responses_total": len(list(responses_dir.glob('*.json'))), "console_events_total": len(console_events), "signature_events_total": len(signature_events), "artifact_dir": str(artifact_dir)}
        (artifact_dir / "cloak_capture.yaml").write_text(_yaml_dump(report), encoding="utf-8")
        return report
    finally:
        if client:
            client.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def _signature_events_from_request(url: str, headers: dict[str, Any]) -> list[dict[str, Any]]:
    interesting = ("sign", "signature", "token", "bogus", "a_bogus", "w_rid", "anti", "nonce", "timestamp", "x-kpsdk")
    events: list[dict[str, Any]] = []
    parsed = urlparse(url)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if any(word in key.lower() for word in interesting):
            events.append({"type": "network_query_signature", "payload": {"key": key, "value": value, "url": url}, "ts": int(time.time() * 1000), "stack": None})
    for key, value in headers.items():
        if any(word in key.lower() for word in interesting):
            events.append({"type": "network_header_signature", "payload": {"key": key, "value": value, "url": url}, "ts": int(time.time() * 1000), "stack": None})
    return events


def _compact_console_event(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": params.get("type"),
        "args": [
            {"type": arg.get("type"), "value": arg.get("value"), "description": arg.get("description")}
            for arg in (params.get("args") or [])
            if isinstance(arg, dict)
        ],
    }


def _parse_signature_console_event(params: dict[str, Any]) -> dict[str, Any] | None:
    args = params.get("args") or []
    if not args:
        return None
    first = args[0].get("value") if isinstance(args[0], dict) else None
    if first != "[SPIDERPILOT_SIGNATURE]":
        return None
    if len(args) < 2:
        return None
    raw = args[1].get("value") if isinstance(args[1], dict) else None
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def _is_json_like(entry: NetworkEntry) -> bool:
    text = " ".join([entry.mime_type or "", str(entry.response_headers)]).lower()
    return "json" in text or (entry.url or "").split("?", 1)[0].endswith(".json")


def _wait_for_cdp_ws(port: int, timeout: float = 15.0) -> str:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            tabs = json.loads(urlopen(f"http://127.0.0.1:{port}/json", timeout=1).read().decode())
            if tabs:
                return tabs[0]["webSocketDebuggerUrl"]
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"CDP endpoint not ready: {last_error}")


def _yaml_dump(data: dict[str, Any]) -> str:
    try:
        import yaml
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    except Exception:
        return json.dumps(data, ensure_ascii=False, indent=2)
