from pathlib import Path

from spiderpilot.signature.sample_collector import collect_signature_samples
from spiderpilot.workflow import create_task


def test_collect_signature_samples_from_trace(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text('''
version: 1
name: sample_sig
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
    root = tmp_path / "artifacts" / "sample_sig"
    (root / "signature_diff.yaml").write_text('''
groups:
  - location: query
    key: sign
    classification: hash_or_signature
''', encoding="utf-8")
    trace_dir = root / "s1" / "cloak"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "signature_trace.json").write_text('''[
      {"type":"network_query_signature","payload":{"key":"sign","value":"abc","url":"https://e.test/api?sign=abc"},"stack":null}
    ]''', encoding="utf-8")
    report = collect_signature_samples(created["workspace"].spec_path, workspace=tmp_path)
    assert report["samples_total"] == 1
    assert report["samples"][0]["classification"] == "hash_or_signature"
    assert (tmp_path / "signatures" / "sample_sig" / "samples.json").exists()
