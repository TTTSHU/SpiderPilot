from spiderpilot.generator.codegen import _class_name
from spiderpilot.runner.local_runner import _extract_mvp_value
from spiderpilot.validator.result_validator import _matches_expected
from spiderpilot.spec import ExpectedValue
from spiderpilot.repair.auto_repair import _suggest_action


def test_class_name():
    assert _class_name("product_detail_demo") == "ProductDetailDemoSpider"


def test_extract_mvp_value():
    assert _extract_mvp_value("hello price 123", {"evidence": {"matched_value": "123"}}) == "123"
    assert _extract_mvp_value("hello sample2", {"evidence": {"matched_value": "sample1", "samples": {"s2": {"matched_value": "sample2"}}}}, sample_id="s2") == "sample2"
    assert _extract_mvp_value("hello", {"evidence": {"matched_value": "123"}}) is None


def test_matches_expected():
    assert _matches_expected("abc", ExpectedValue(equals="abc"))
    assert _matches_expected("abcdef", ExpectedValue(contains=["abc", "def"]))


def test_suggest_action():
    assert "required" in _suggest_action({"reason": "required_empty"})["action"]


def test_extract_json_doc_path_value():
    html = '<script type="application/ld+json">{"name":"Example Product"}</script>'
    assert _extract_mvp_value(html, {"evidence": {"path": "json_doc:0:$.name"}}) == "Example Product"


def test_extract_json_response_path_value(tmp_path):
    responses = tmp_path / "responses"
    responses.mkdir()
    (responses / "api.json").write_text("{\"data\":{\"price\":\"123\"}}", encoding="utf-8")
    assert _extract_mvp_value("", {"evidence": {"path": "json_response:api.json:$.data.price"}}, sample_dir=tmp_path) == "123"
