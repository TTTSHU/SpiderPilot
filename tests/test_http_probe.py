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
