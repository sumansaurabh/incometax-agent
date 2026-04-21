import unittest

from rules_core.engine import evaluate


class RulesEngineTest(unittest.TestCase):
    def test_evaluate_caps_and_regime(self) -> None:
        result = evaluate(180000.0, 40000.0, True, 100000.0, 120000.0)
        self.assertEqual(result["section_80c_applied"], 150000.0)
        self.assertEqual(result["section_80d_applied"], 25000.0)
        self.assertEqual(result["standard_deduction"], 50000.0)
        self.assertEqual(result["regime"]["preferred"], "old")

    def test_evaluate_expanded_rules_output(self) -> None:
        result = evaluate(
            120000.0,
            52000.0,
            True,
            95000.0,
            110000.0,
            total_income=1800000.0,
            has_capital_gains=True,
            has_business_income=False,
            donations_80g=40000.0,
            donation_qualifying_percent=0.5,
            donation_qualifying_limit=15000.0,
            savings_interest=15000.0,
            hra_received=240000.0,
            rent_paid=300000.0,
            basic_salary=600000.0,
            metro=True,
            income_heads=["salary", "capital_gains", "other_sources"],
            has_foreign_assets=True,
            has_tax_payments=True,
            days_in_india=120,
            days_in_prev_four_years=400,
            days_in_prev_seven_years=800,
            has_crypto_activity=True,
        )

        self.assertEqual(result["deductions"]["section_80d_applied"], 25000.0)
        self.assertEqual(result["deductions"]["section_80g_applied"], 15000.0)
        self.assertEqual(result["deductions"]["section_80tta_applied"], 10000.0)
        self.assertEqual(result["residential_status"]["status"], "resident")
        self.assertTrue(result["eligibility"]["itr2"])
        self.assertIn("Schedule CG", result["required_schedules"])
        self.assertIn("Schedule FA", result["required_schedules"])
        self.assertTrue(any("Foreign asset" in warning for warning in result["disclosure_checks"]))
