from pathlib import Path

from spiderpilot.signature.detector import _score_key_value, detect_signatures
from spiderpilot.workflow import create_task


def test_score_key_value_sign_hash():
    score, reasons = _score_key_value("x-sign", "a" * 32, "request_header")
    assert score > 0.7
    assert "signature_keyword_key" in reasons


def test_detect_signatures_from_cloak_network(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text('''
version: 1
name: sig_demo
samples:
  - id: s1
    url: "https://e.test/page"
    expected:
      title:
        equals: "x"
fields:
  title:
    type: string
''', encoding="utf-8")
    created = create_task(spec, workspace=tmp_path)
    network_dir = tmp_path / "artifacts" / "sig_demo" / "s1" / "cloak"
    network_dir.mkdir(parents=True, exist_ok=True)
    (network_dir / "network.json").write_text('''[
      {"url":"https://e.test/api?id=1&sign=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&ts=1710000000","request_headers":{"x-token":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"response_headers":{}}
    ]''', encoding="utf-8")
    report = detect_signatures(created["workspace"].spec_path, workspace=tmp_path)
    keys = {g["key"].lower() for g in report["groups"]}
    assert "sign" in keys
    assert "x-token" in keys
    assert (tmp_path / "artifacts" / "sig_demo" / "signature_candidates.yaml").exists()
