from pathlib import Path

from spiderpilot.signature.request_diff import _classify_values, analyze_signature_diff
from spiderpilot.workflow import create_task


def test_classify_signature_values():
    assert _classify_values("ts", ["1710000000", "1710000001"]) == "timestamp"
    assert _classify_values("sign", ["a" * 32, "b" * 32]) == "hash_or_signature"
    assert _classify_values("token", ["same", "same"]) == "stable_token"


def test_analyze_signature_diff(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text('''
version: 1
name: sigdiff_demo
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
    root = tmp_path / "artifacts" / "sigdiff_demo"
    (root / "signature_candidates.yaml").write_text('''
candidates:
  - location: query
    key: sign
    value_sample: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    request_url: https://e.test/api?id=1
  - location: query
    key: sign
    value_sample: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    request_url: https://e.test/api?id=2
''', encoding="utf-8")
    report = analyze_signature_diff(created["workspace"].spec_path, workspace=tmp_path)
    assert report["groups"][0]["classification"] == "hash_or_signature"
    assert (root / "signature_diff.yaml").exists()
