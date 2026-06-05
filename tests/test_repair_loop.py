from pathlib import Path

from spiderpilot.repair.loop import run_repair_loop
from spiderpilot.workflow import create_task


def test_repair_loop_success(tmp_path):
    created = create_task(Path("examples/product_detail.yaml"), workspace=tmp_path)
    root = tmp_path / "artifacts" / "product_detail_demo"
    (root / "sample_1" / "raw.html").write_text("Apple iPhone 15 128GB Black 3999.00 SuperStore iphone-15-black", encoding="utf-8")
    (root / "sample_2" / "raw.html").write_text("Samsung Galaxy S24 256GB 4599.00 MobileWorld galaxy-s24", encoding="utf-8")
    report = run_repair_loop(created["workspace"].spec_path, workspace=tmp_path, max_attempts=2)
    assert report["ok"] is True
    assert report["attempts_total"] == 1
