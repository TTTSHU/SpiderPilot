from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from spiderpilot.probe.cloak_cdp import capture_with_cloakbrowser, cloak_binary_path


class CloakCaptureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        pass

    def do_GET(self):
        if self.path == "/api/product":
            body = json.dumps({"data": {"title": "Cloak Product", "price": "888"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = b"""
<html><body><h1>Cloak Page</h1><script>
fetch('/api/product').then(r => r.json()).then(j => { document.body.dataset.price = j.data.price; });
</script></body></html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_cloak_capture_mock_http(tmp_path):
    if not cloak_binary_path():
        return
    server = ThreadingHTTPServer(("127.0.0.1", 0), CloakCaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/"
        report = capture_with_cloakbrowser(url, tmp_path / "cloak", wait_seconds=3.0, port=9333)
        assert report["network_total"] > 0
        assert (tmp_path / "cloak" / "rendered.html").exists()
        assert (tmp_path / "cloak" / "network.json").exists()
        assert list((tmp_path / "cloak" / "responses").glob("*.json"))
    finally:
        server.shutdown()
