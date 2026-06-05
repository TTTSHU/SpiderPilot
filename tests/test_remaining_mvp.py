from spiderpilot.generator.codegen import _class_name
from spiderpilot.runner.local_runner import _extract_mvp_value
from spiderpilot.validator.result_validator import _matches_expected
from spiderpilot.spec import ExpectedValue
from spiderpilot.repair.auto_repair import _suggest_action


def test_class_name():
    assert _class_name("product_detail_demo") == "ProductDetailDemoSpider"


def test_extract_mvp_value():
    assert _extract_mvp_value("hello price 123", {"evidence": {"matched_value": "123"}}) == "123"
    assert _extract_mvp_value("hello", {"evidence": {"matched_value": "123"}}) is None


def test_matches_expected():
    assert _matches_expected("abc", ExpectedValue(equals="abc"))
    assert _matches_expected("abcdef", ExpectedValue(contains=["abc", "def"]))


def test_suggest_action():
    assert "required" in _suggest_action({"reason": "required_empty"})["action"]
