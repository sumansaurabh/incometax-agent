from __future__ import annotations

import json
import unittest

from itx_workers.document_pipeline import process_document


class DocumentPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_form16_pipeline_normalizes_salary_and_tds(self) -> None:
        payload = {
            "file_name": "form16.txt",
            "mime_type": "text/plain",
            "doc_type": "form16",
            "raw_text": (
                "Form 16\n"
                "Employee Name: Alice Example\n"
                "PAN: ABCDE1234F\n"
                "Employer Name: Example Technologies Pvt Ltd\n"
                "Employer TAN: BLRA12345B\n"
                "Assessment Year: 2025-26\n"
                "Gross Salary: 1850000\n"
                "Tax deducted at source: 210000\n"
            ),
        }

        result = await process_document(payload)

        self.assertEqual(result["document_type"], "form16")
        self.assertEqual(result["normalized_fields"]["pan"], "ABCDE1234F")
        self.assertEqual(result["normalized_fields"]["salary"]["gross"], 1850000.0)
        self.assertEqual(result["normalized_fields"]["tax_paid"]["tds_salary"], 210000.0)
        self.assertEqual(result["normalized_fields"]["employer_name"], "Example Technologies Pvt Ltd")

    async def test_ais_json_pipeline_extracts_nested_facts(self) -> None:
        payload = {
            "file_name": "ais.json",
            "mime_type": "application/json",
            "raw_text": json.dumps(
                {
                    "pan": "ABCDE1234F",
                    "fullName": "Alice Example",
                    "assessmentYear": "2025-26",
                    "grossSalary": 1200000,
                    "tdsSalary": 150000,
                    "interestIncome": 12345,
                    "longTermCapitalGain": 55000,
                    "section80C": 150000,
                    "ifscCode": "HDFC0001234",
                }
            ),
        }

        result = await process_document(payload)

        self.assertEqual(result["document_type"], "ais_json")
        self.assertEqual(result["normalized_fields"]["assessment_year"], "2025-26")
        self.assertEqual(result["normalized_fields"]["salary"]["gross"], 1200000.0)
        self.assertEqual(result["normalized_fields"]["other_sources"]["total"], 12345.0)
        self.assertEqual(result["normalized_fields"]["capital_gains"]["ltcg"], 55000.0)
        self.assertEqual(result["normalized_fields"]["deductions"]["80c"], 150000.0)
        self.assertEqual(result["normalized_fields"]["bank"]["ifsc"], "HDFC0001234")