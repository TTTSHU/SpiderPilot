from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from typer.testing import CliRunner

from spiderpilot.cli import app


class ProductHandler(BaseHTTPRequestHandler):
    products = {
        "/p1": {"data": {"title": "Apple iPhone 15 128GB Black", "price": "3999.00", "shop": {"name": "SuperStore"}, "images": ["iphone-15-black"]}},
        "/p2": {"data": {"title": "Samsung Galaxy S24 256GB", "price": "4599.00", "shop": {"name": "MobileWorld"}, "images": ["galaxy-s24"]}},
    }

    def log_message(self, format, *args):  # noqa: A003
        pass

    def do_GET(self):
        body = json.dumps(self.products.get(self.path, {})).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_run_all_real_http_json_probe(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProductHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        spec = tmp_path / "spec.yaml"
        spec.write_text(
            f"""
version: 1
name: mock_product_detail
target_type: product_detail
samples:
  - id: sample_1
    url: "{base}/p1"
    expected:
      title:
        equals: "Apple iPhone 15 128GB Black"
      price:
        equals: "3999.00"
      shop_name:
        equals: "SuperStore"
      images:
        contains:
          - "iphone-15-black"
  - id: sample_2
    url: "{base}/p2"
    expected:
      title:
        equals: "Samsung Galaxy S24 256GB"
      price:
        equals: "4599.00"
      shop_name:
        equals: "MobileWorld"
      images:
        contains:
          - "galaxy-s24"
fields:
  title:
    type: string
    required: true
  price:
    type: decimal
    required: true
  shop_name:
    type: string
    required: false
  images:
    type: list[string]
    required: false
""",
            encoding="utf-8",
        )
        runner = CliRunner()
        res = runner.invoke(app, ["create", "-f", str(spec), "--workspace", str(tmp_path / "workspace"), "--run-all"])
        assert res.exit_code == 0, res.output
        validation = (tmp_path / "workspace" / "results" / "mock_product_detail_validation.yaml").read_text()
        assert "ok: true" in validation
        plan = (tmp_path / "workspace" / "plans" / "mock_product_detail.yaml").read_text()
        assert "json_response" in plan
        assert (tmp_path / "workspace" / "artifacts" / "mock_product_detail" / "sample_1" / "responses" / "response_0.json").exists()
    finally:
        server.shutdown()


def test_http_runner_live_json(tmp_path):
    from spiderpilot.runner.http_runner import run_http_plan
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProductHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        spec = tmp_path / "spec.yaml"
        spec.write_text(f"""
version: 1
name: live_json
samples:
  - id: sample_1
    url: "{base}/p1"
    expected:
      price:
        equals: "3999.00"
fields:
  price:
    type: decimal
    required: true
""", encoding="utf-8")
        plan = tmp_path / "plan.yaml"
        plan.write_text("""
version: 1
name: live_json
fields:
  price:
    evidence:
      path: json_response:response_0.json:$.data.price
""", encoding="utf-8")
        report = run_http_plan(spec, plan, workspace=tmp_path)
        assert report["items_total"] == 1
        assert (tmp_path / "results" / "live_json_http.json").read_text().find("3999.00") >= 0
    finally:
        server.shutdown()
