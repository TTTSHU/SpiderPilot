from spiderpilot.spec import ExpectedValue
from spiderpilot.reverse.locator import locate_expected_in_text


def test_locate_expected_equals_in_text():
    candidates = locate_expected_in_text(
        "title",
        ExpectedValue(equals="Example Product"),
        "sample_1",
        "<html><h1>Example Product</h1></html>",
    )
    assert len(candidates) == 1
    assert candidates[0].field == "title"
    assert candidates[0].source == "raw_html"
    assert candidates[0].matched_value == "Example Product"


def test_locate_expected_contains_in_text():
    candidates = locate_expected_in_text(
        "images",
        ExpectedValue(contains=["image-1.jpg"]),
        "sample_1",
        '<img src="https://cdn.example.com/image-1.jpg">',
    )
    assert candidates
    assert candidates[0].match_type == "contains"
