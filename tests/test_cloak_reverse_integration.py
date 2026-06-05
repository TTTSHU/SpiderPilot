from pathlib import Path

from spiderpilot.reverse.locator import locate_expected_in_json_responses
from spiderpilot.runner.local_runner import _extract_mvp_value
from spiderpilot.spec import ExpectedValue


def test_reverse_scans_cloak_responses(tmp_path):
    responses = tmp_path / "cloak" / "responses"
    responses.mkdir(parents=True)
    (responses / "response_0.json").write_text('{"data":{"price":"888"}}', encoding="utf-8")
    candidates = locate_expected_in_json_responses("price", ExpectedValue(equals="888"), "s1", tmp_path)
    assert candidates
    assert candidates[0].source == "cloak_json_response"
    assert candidates[0].path == "json_response:cloak/response_0.json:$.data.price"


def test_runner_reads_cloak_response_path(tmp_path):
    responses = tmp_path / "cloak" / "responses"
    responses.mkdir(parents=True)
    (responses / "response_0.json").write_text('{"data":{"price":"888"}}', encoding="utf-8")
    assert _extract_mvp_value("", {"evidence": {"path": "json_response:cloak/response_0.json:$.data.price"}}, sample_dir=tmp_path) == "888"
