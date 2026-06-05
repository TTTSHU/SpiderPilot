from spiderpilot.reverse.json_locator import extract_embedded_json, find_json_paths, get_json_path
from spiderpilot.reverse.locator import locate_expected_in_embedded_json
from spiderpilot.spec import ExpectedValue


def test_extract_json_ld_and_find_path():
    html = '<script type="application/ld+json">{"name":"Example Product","offers":{"price":"123"}}</script>'
    docs = extract_embedded_json(html)
    assert len(docs) == 1
    hits = find_json_paths(docs[0].data, "123")
    assert hits[0]["path"] == "$.offers.price"
    assert get_json_path(docs[0].data, "$.offers.price") == "123"


def test_locate_expected_in_embedded_json():
    html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"title":"Example Product"}}</script>'
    candidates = locate_expected_in_embedded_json("title", ExpectedValue(equals="Example Product"), "s1", html)
    assert candidates
    assert candidates[0].source == "embedded_json"
    assert "$.props.title" in candidates[0].path
