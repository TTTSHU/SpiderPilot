from pathlib import Path

from spiderpilot.signature.runtime_hook import HOOK_SCRIPT, write_hook_script


def test_hook_script_contains_core_hooks():
    assert "window.fetch" in HOOK_SCRIPT
    assert "XMLHttpRequest.prototype.open" in HOOK_SCRIPT
    assert "URLSearchParams.prototype.set" in HOOK_SCRIPT
    assert "[SPIDERPILOT_SIGNATURE]" in HOOK_SCRIPT


def test_write_hook_script(tmp_path):
    report = write_hook_script(Path("examples/product_detail.yaml"), workspace=tmp_path)
    path = Path(report["script_path"])
    assert path.exists()
    assert "runtime_hook.js" in str(path)
