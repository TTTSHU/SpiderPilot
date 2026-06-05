from pathlib import Path

from spiderpilot.probe.diff import build_probe_diff
from spiderpilot.workflow import create_task


def test_probe_diff_browser_json_only(tmp_path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text('''
version: 1
name: diff_demo
samples:
  - id: s1
    url: "https://e.test/p"
    expected:
      price:
        equals: "888"
fields:
  price:
    type: string
''', encoding="utf-8")
    created = create_task(spec_path, workspace=tmp_path)
    sample_dir = tmp_path / "artifacts" / "diff_demo" / "s1"
    (sample_dir / "raw.html").write_text("<html>loading</html>", encoding="utf-8")
    cloak_responses = sample_dir / "cloak" / "responses"
    cloak_responses.mkdir(parents=True)
    (sample_dir / "cloak" / "rendered.html").write_text("<html>price loaded</html>", encoding="utf-8")
    (cloak_responses / "response_0.json").write_text('{"price":"888"}', encoding="utf-8")
    report = build_probe_diff(created["workspace"].spec_path, workspace=tmp_path)
    assert report["summary"]["strategy_hint"] == "browser_probe_required_for_reverse"
    assert report["samples"][0]["expected_presence"]["price"]["cloak_json"] is True
