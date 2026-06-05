from spiderpilot.probe.cloak_cdp import _parse_signature_console_event


def test_parse_signature_console_event():
    params = {"args": [{"value": "[SPIDERPILOT_SIGNATURE]"}, {"value": '{"type":"url_param_set","payload":{"key":"sign","value":"abc"}}'}]}
    event = _parse_signature_console_event(params)
    assert event["type"] == "url_param_set"
    assert event["payload"]["key"] == "sign"
