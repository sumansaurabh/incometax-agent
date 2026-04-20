from rules_core.engine import evaluate


def test_evaluate_caps_and_regime() -> None:
    result = evaluate(180000.0, 40000.0, True, 100000.0, 120000.0)
    assert result["section_80c_applied"] == 150000.0
    assert result["section_80d_applied"] == 25000.0
    assert result["standard_deduction"] == 50000.0
    assert result["regime"]["preferred"] == "old"
