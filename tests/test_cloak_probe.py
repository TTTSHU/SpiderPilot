from pathlib import Path

from spiderpilot.probe.cloak_probe import check_cloakbrowser, run_cloak_probe


def test_check_cloakbrowser_shape():
    status = check_cloakbrowser()
    data = status.to_dict()
    assert "available" in data
    assert "executable" in data


def test_run_cloak_probe_writes_report(tmp_path):
    report = run_cloak_probe(Path("examples/product_detail.yaml"), workspace=tmp_path)
    assert report["task"] == "product_detail_demo"
    assert (tmp_path / "artifacts" / "product_detail_demo" / "cloak_probe_report.yaml").exists()
