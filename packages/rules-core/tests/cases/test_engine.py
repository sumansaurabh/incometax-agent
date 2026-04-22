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

    def test_evaluate_extended_deductions_and_itr4_eligibility(self) -> None:
        result = evaluate(
            0.0,
            0.0,
            False,
            48000.0,
            52000.0,
            total_income=2200000.0,
            resident=True,
            has_business_income=True,
            presumptive_income=True,
            senior_citizen=True,
            senior_interest=70000.0,
            education_loan_interest_80e=63000.0,
            first_home_interest_80ee=90000.0,
            affordable_home_interest_80eea=200000.0,
            rent_paid_80gg=180000.0,
            adjusted_total_income=720000.0,
            income_heads=["business", "other_sources"],
            has_tax_payments=True,
            has_foreign_income=True,
            is_director=True,
            has_unlisted_equity=True,
            agricultural_income=10000.0,
        )

        self.assertEqual(result["deductions"]["section_80ttb_applied"], 50000.0)
        self.assertEqual(result["deductions"]["section_80e_applied"], 63000.0)
        self.assertEqual(result["deductions"]["section_80ee_applied"], 50000.0)
        self.assertEqual(result["deductions"]["section_80eea_applied"], 150000.0)
        self.assertEqual(result["deductions"]["section_80gg_applied"], 60000.0)
        self.assertFalse(result["eligibility"]["itr4"])
        self.assertIn("Schedule BP", result["required_schedules"])
        self.assertIn("Schedule TDS/TCS", result["required_schedules"])
        self.assertIn("Schedule EI", result["required_schedules"])
        self.assertTrue(any("Director details" in warning for warning in result["disclosure_checks"]))
        self.assertTrue(any("Agricultural income" in warning for warning in result["disclosure_checks"]))

    def test_evaluate_itr1_disqualification_for_foreign_assets_and_multiple_house_properties(self) -> None:
        result = evaluate(
            150000.0,
            25000.0,
            True,
            15000.0,
            20000.0,
            total_income=480000.0,
            resident=True,
            has_capital_gains=False,
            has_multiple_house_properties=True,
            has_foreign_assets=True,
            agricultural_income=12000.0,
            income_heads=["salary", "house_property"],
        )

        self.assertFalse(result["eligibility"]["itr1"])
        self.assertIn("Schedule FA", result["required_schedules"])
        self.assertIn("Schedule EI", result["required_schedules"])
        self.assertTrue(any("Foreign asset" in warning for warning in result["disclosure_checks"]))
