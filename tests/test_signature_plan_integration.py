from pathlib import Path

import yaml

from spiderpilot.signature.plan_integration import integrate_signature_plan
from spiderpilot.workflow import create_task


def test_integrate_signature_plan(tmp_path):
    created = create_task(Path("examples/product_detail.yaml"), workspace=tmp_path)
    plan_dir = tmp_path / "plans"
    plan_dir.mkdir(exist_ok=True)
    (plan_dir / "product_detail_demo.yaml").write_text("version: 1\nname: product_detail_demo\nfields: {}\n", encoding="utf-8")
    sig_dir = tmp_path / "signatures" / "product_detail_demo"
    sig_dir.mkdir(parents=True)
    (sig_dir / "signature.yaml").write_text("""
kind: signer_stub
signer_path: signer_stub.js
groups:
  - location: query
    key: sign
    classification: hash_or_signature
""", encoding="utf-8")
    (sig_dir / "verify_report.yaml").write_text("ok: true\n", encoding="utf-8")
    plan = integrate_signature_plan(created["workspace"].spec_path, workspace=tmp_path)
    assert plan["signature"]["required"] is True
    assert plan["signature"]["verify_ok"] is True
