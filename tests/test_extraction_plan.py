from spiderpilot.planner.extraction_plan import _select_best_candidate, _overall_confidence


def test_select_best_candidate():
    best = _select_best_candidate([
        {"path": "a", "confidence": 0.2},
        {"path": "b", "confidence": 0.8},
    ])
    assert best["path"] == "b"


def test_overall_confidence():
    assert _overall_confidence({"a": {"confidence": 0.5}, "b": {"confidence": 1.0}}) == 0.75
