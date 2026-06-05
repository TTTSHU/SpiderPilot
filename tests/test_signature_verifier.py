from pathlib import Path
import shutil

from spiderpilot.signature.generator import generate_signer_skeleton
from spiderpilot.signature.verifier import verify_signer
from spiderpilot.workflow import create_task


def test_verify_signer_stub(tmp_path):
    if not shutil.which("node"):
        return
    spec = tmp_path / "spec.yaml"
    spec.write_text('''
version: 1
name: verify_sig
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
    sig_dir = tmp_path / "signatures" / "verify_sig"
    sig_dir.mkdir(parents=True)
    (sig_dir / "samples.json").write_text('[{"sample_id":"s1","location":"query","key":"sign","value":"abc","url":"https://e.test/api?sign=abc"}]', encoding="utf-8")
    generate_signer_skeleton(created["workspace"].spec_path, workspace=tmp_path)
    report = verify_signer(created["workspace"].spec_path, workspace=tmp_path)
    assert report["ok"] is True
    assert report["samples_passed"] == 1
    assert (sig_dir / "verify_report.yaml").exists()
