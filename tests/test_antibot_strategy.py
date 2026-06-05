from pathlib import Path

from spiderpilot.antibot.strategy import build_antibot_strategy


def test_antibot_strategy_direct_http(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text("""
version: 1
name: demo
samples:
  - id: s1
    url: "https://example.com"
    expected:
      title:
        equals: "Example"
fields:
  title:
    type: string
""", encoding="utf-8")
    root = tmp_path / "artifacts" / "demo"
    root.mkdir(parents=True)
    (root / "antibot_report.yaml").write_text("status: clear\nprimary_vendor: null\nresults: []\n", encoding="utf-8")
    (root / "probe_report.yaml").write_text("samples_ok: 1\nsamples_total: 1\n", encoding="utf-8")
    report = build_antibot_strategy(spec, workspace=tmp_path)
    assert report["strategy"] == "direct_http"
    assert (root / "antibot_strategy.yaml").exists()


def test_antibot_strategy_vendor():
    from spiderpilot.antibot.strategy import _decide_strategy
    assert _decide_strategy({"status": "detected", "primary_vendor": "datadome"}, {}, {}) == "inspect_cookie_or_signature_challenge"


def test_antibot_strategy_uses_probe_diff(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text("""
version: 1
name: diff_strategy
samples:
  - id: s1
    url: "https://example.com"
    expected:
      price:
        equals: "888"
fields:
  price:
    type: string
""", encoding="utf-8")
    root = tmp_path / "artifacts" / "diff_strategy"
    root.mkdir(parents=True)
    (root / "antibot_report.yaml").write_text("status: clear\nprimary_vendor: null\nresults: []\n", encoding="utf-8")
    (root / "probe_report.yaml").write_text("samples_ok: 1\nsamples_total: 1\n", encoding="utf-8")
    (root / "probe_diff.yaml").write_text("""
summary:
  strategy_hint: browser_probe_required_for_reverse
  signals:
    browser_discovered_json_api: 1
  fields_browser_only: 1
""", encoding="utf-8")
    report = build_antibot_strategy(spec, workspace=tmp_path)
    assert report["strategy"] == "browser_probe_required_for_reverse"
    assert "probe_diff_strategy_hint" in report["evidence"]
