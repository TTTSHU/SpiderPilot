from pathlib import Path

import yaml

from spiderpilot.spec import build_task_summary, load_spec, prepare_task_workspace


def test_load_example_spec():
    spec = load_spec(Path("examples/product_detail.yaml"))
    assert spec.name == "product_detail_demo"
    assert len(spec.samples) == 2
    assert "title" in spec.fields


def test_prepare_task_workspace(tmp_path):
    spec_path = Path("examples/product_detail.yaml")
    spec = load_spec(spec_path)
    workspace = prepare_task_workspace(spec, spec_path, workspace=tmp_path)
    assert workspace.spec_path.exists()
    assert (workspace.artifacts_dir / "sample_1").is_dir()
    assert (workspace.artifacts_dir / "sample_2").is_dir()
    summary = build_task_summary(spec, workspace)
    assert summary["task"] == "product_detail_demo"
    assert summary["samples_total"] == 2
