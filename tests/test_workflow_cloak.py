from pathlib import Path

from spiderpilot.workflow import create_task, run_all


def test_run_all_with_cloak_skip_network_uses_existing_cloak_artifacts(tmp_path):
    created = create_task(Path("examples/product_detail.yaml"), workspace=tmp_path)
    root = tmp_path / "artifacts" / "product_detail_demo"
    (root / "sample_1" / "raw.html").write_text("loading", encoding="utf-8")
    (root / "sample_2" / "raw.html").write_text("loading", encoding="utf-8")
    for sid, data in {
        "sample_1": '{"data":{"title":"Apple iPhone 15 128GB Black","price":"3999.00","shop_name":"SuperStore","images":["iphone-15-black"]}}',
        "sample_2": '{"data":{"title":"Samsung Galaxy S24 256GB","price":"4599.00","shop_name":"MobileWorld","images":["galaxy-s24"]}}',
    }.items():
        d = root / sid / "cloak" / "responses"
        d.mkdir(parents=True)
        (root / sid / "cloak" / "rendered.html").write_text("rendered", encoding="utf-8")
        (d / "response_0.json").write_text(data, encoding="utf-8")
    report = run_all(created["workspace"].spec_path, workspace=tmp_path, skip_network=True, with_cloak=True)
    assert report["ok"] is True
    assert report["steps"]["antibot_strategy"]["strategy"] == "browser_probe_required_for_reverse"
