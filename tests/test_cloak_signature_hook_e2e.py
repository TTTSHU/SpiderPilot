from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from spiderpilot.probe.cloak_cdp import capture_with_cloakbrowser, cloak_binary_path


class SignatureHookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        pass

    def do_GET(self):
        body = b"""
<html><body><script>
setTimeout(() => {
  const p = new URLSearchParams();
  p.set('sign', 'abcdef1234567890abcdef1234567890');
  fetch('/api?' + p.toString()).catch(() => {});
}, 500);
</script></body></html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_cloak_signature_hook_capture(tmp_path):
    if not cloak_binary_path():
        return
    server = ThreadingHTTPServer(("127.0.0.1", 0), SignatureHookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = capture_with_cloakbrowser(f"http://127.0.0.1:{server.server_port}/", tmp_path / "cloak", wait_seconds=5, port=9334, signature_hook=True)
        assert report["signature_events_total"] > 0
        trace = (tmp_path / "cloak" / "signature_trace.json").read_text(encoding="utf-8")
        assert "url_param_set" in trace or "network_query_signature" in trace
        assert "sign" in trace
    finally:
        server.shutdown()
