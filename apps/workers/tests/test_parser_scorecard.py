from __future__ import annotations

from pathlib import Path
import unittest

from itx_workers.quality.parser_scorecard import build_scorecard, load_case_bank


class ParserScorecardTest(unittest.IsolatedAsyncioTestCase):
    async def test_parser_regression_bank_has_full_fixture_coverage(self) -> None:
        case_bank_path = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "synthetic_docs" / "parser_regression_cases.json"
        cases = load_case_bank(case_bank_path)

        scorecard = await build_scorecard(cases)

        self.assertGreaterEqual(scorecard["totals"]["case_count"], 12)
        self.assertEqual(scorecard["totals"]["failed_cases"], 0)
        self.assertEqual(scorecard["failed_case_ids"], [])
        self.assertEqual(scorecard["totals"]["field_coverage"], 1.0)
        self.assertIn("form16", scorecard["parsers"])
        self.assertIn("ais_json", scorecard["parsers"])
        self.assertIn("broker_capgain", scorecard["parsers"])