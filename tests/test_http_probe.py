from pathlib import Path

from spiderpilot.probe.http_probe import _cookies_to_list, HttpProbeResult


def test_http_probe_result_to_dict():
    result = HttpProbeResult(
        sample_id="s1",
        url="https://example.com",
        final_url="https://example.com",
        status_code=200,
        ok=True,
        response_size=10,
        artifact_dir="/tmp/a",
        files={"raw_html": "/tmp/a/raw.html"},
    )
    data = result.to_dict()
    assert data["sample_id"] == "s1"
    assert data["ok"] is True
    assert data["files"]["raw_html"].endswith("raw.html")


def test_write_json_response_if_any(tmp_path):
    from spiderpilot.probe.http_probe import _write_json_response_if_any
    files = _write_json_response_if_any(b'{"ok": true}', {"Content-Type": "application/json"}, tmp_path / "responses")
    assert len(files) == 1
    assert files[0].endswith("response_0.json")
    assert (tmp_path / "responses" / "response_0.json").exists()


def test_bytes_look_like_json():
    from spiderpilot.probe.http_probe import _bytes_look_like_json
    assert _bytes_look_like_json(b' {"ok": true}')
    assert not _bytes_look_like_json(b'<html></html>')
