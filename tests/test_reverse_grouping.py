from spiderpilot.reverse.locator import FieldCandidate, group_candidates
from spiderpilot.spec import CrawlSpec, SampleSpec, FieldSpec


def test_group_candidates_stable_path_groups():
    spec = CrawlSpec(
        version=1,
        name="demo",
        target_type="detail",
        samples=[SampleSpec(id="s1", url="https://e.test/1"), SampleSpec(id="s2", url="https://e.test/2")],
        fields={"price": FieldSpec(type="string")},
    )
    grouped = group_candidates(spec, [
        FieldCandidate("price", "json_response", "json_response:a.json:$.data.price", "s1", "equals", "1", "", 0.95),
        FieldCandidate("price", "json_response", "json_response:b.json:$.data.price", "s2", "equals", "2", "", 0.95),
    ])
    assert grouped["price"]["hit_rate"] == 1
    assert grouped["price"]["stable_path_groups"][0]["path_shape"] == "json_response:*:$.data.price"
