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


def test_locate_expected_in_json_responses(tmp_path):
    from spiderpilot.reverse.locator import locate_expected_in_json_responses
    responses = tmp_path / "responses"
    responses.mkdir()
    (responses / "api.json").write_text("{\"data\":{\"price\":\"123\"}}", encoding="utf-8")
    candidates = locate_expected_in_json_responses("price", ExpectedValue(equals="123"), "s1", tmp_path)
    assert candidates
    assert candidates[0].source == "json_response"
    assert candidates[0].path == "json_response:api.json:$.data.price"
