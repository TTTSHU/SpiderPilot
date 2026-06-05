from spiderpilot.planner.url_pattern import infer_url_pattern


def test_infer_url_pattern_numeric_ids():
    assert infer_url_pattern(["https://e.test/p/100", "https://e.test/p/200"]) == "https://e.test/p/{id1}"


def test_infer_url_pattern_single():
    assert infer_url_pattern(["https://e.test/a"]) == "https://e.test/a"


def test_infer_url_pattern_different_hosts():
    assert infer_url_pattern(["https://a.test/1", "https://b.test/2"]) is None
