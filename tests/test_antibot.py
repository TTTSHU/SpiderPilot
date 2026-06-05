from spiderpilot.antibot.precheck import detect_vendor


def test_detect_datadome_vendor():
    vendor, confidence, hits = detect_vendor("Set-Cookie: datadome=abc; DataDome captcha", [])
    assert vendor == "datadome"
    assert confidence > 0
    assert hits


def test_detect_clear_vendor():
    vendor, confidence, hits = detect_vendor("normal html page", [])
    assert vendor is None
    assert confidence == 0
    assert hits == []
