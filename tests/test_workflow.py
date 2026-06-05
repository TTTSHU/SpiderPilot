from pathlib import Path

from spiderpilot.workflow import run_all


def test_run_all_skip_network(tmp_path):
    spec_path = Path("examples/product_detail.yaml")
    # Pre-create expected raw.html artifacts after create_task would copy spec.
    # run_all(skip_network=True) calls create_task first, so we create files after
    # by monkeypatching the probe inputs through existing workspace directories.
    from spiderpilot.workflow import create_task

    created = create_task(spec_path, workspace=tmp_path)
    root = tmp_path / "artifacts" / "product_detail_demo"
    (root / "sample_1" / "raw.html").write_text(
        "Apple iPhone 15 128GB Black 3999.00 SuperStore iphone-15-black", encoding="utf-8"
    )
    (root / "sample_2" / "raw.html").write_text(
        "Samsung Galaxy S24 256GB 4599.00 MobileWorld galaxy-s24", encoding="utf-8"
    )
    report = run_all(created["workspace"].spec_path, workspace=tmp_path, skip_network=True)
    assert report["ok"] is True
    assert (tmp_path / "results" / "product_detail_demo_workflow.yaml").exists()
