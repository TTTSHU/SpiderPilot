from pathlib import Path

from spiderpilot.signature.generator import generate_signer_skeleton
from spiderpilot.workflow import create_task


def test_generate_signer_skeleton(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text('''
version: 1
name: gen_sig
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
    sig_dir = tmp_path / "signatures" / "gen_sig"
    sig_dir.mkdir(parents=True)
    (sig_dir / "samples.json").write_text('[{"location":"query","key":"sign","value":"abc","classification":"hash_or_signature"}]', encoding="utf-8")
    report = generate_signer_skeleton(created["workspace"].spec_path, workspace=tmp_path)
    assert Path(report["signer_path"]).exists()
    assert report["groups"][0]["key"] == "sign"
    assert (sig_dir / "signature.yaml").exists()
