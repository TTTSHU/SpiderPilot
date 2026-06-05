from spiderpilot.runner.http_runner import _extract_live_json_value


def test_extract_live_json_value_from_json_response_path():
    data = {"data": {"price": "123"}}
    field_plan = {"evidence": {"path": "json_response:api.json:$.data.price"}}
    assert _extract_live_json_value(data, field_plan) == "123"
