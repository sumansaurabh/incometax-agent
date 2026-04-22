from __future__ import annotations

import json
import unittest

from itx_workers.document_pipeline import process_document


def _make_pdf(text: str) -> bytes:
    payload = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET"
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(payload)} >> stream\n{payload}\nendstream endobj\n".encode(),
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    header = b"%PDF-1.4\n"
    body = b"".join(objects)
    xref_start = len(header) + len(body)
    offsets = []
    cursor = len(header)
    for obj in objects:
        offsets.append(cursor)
        cursor += len(obj)
    xref = [f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode()]
    for offset in offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer << /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()
    return header + body + b"".join(xref) + trailer


class DocumentPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_form16_realistic_layout_extracts_employee_and_employer_identity(self) -> None:
        payload = {
            "file_name": "form16-part-a.txt",
            "mime_type": "text/plain",
            "doc_type": "form16",
            "raw_text": (
                "FORM NO. 16\n"
                "PARTA\n"
                "Name and address of the Employer/Specified Bank Name and address of the Employee/Specified senior citizen\n"
                "APTUSDATALABS TECHNOLOGIES PRIVATE LIMITED\n"
                "SY NO.283/58/7, AURBIS BUSINESSPARKS PLTD.\n"
                "DEVARABEESANAHALLI VILLAG, AKANSHA SINHA\n"
                "VARTHUR HOBLI, BANGALORE - 560103 84/170, NEAR OLD RTO OFFICE, MAQBOOL GANJ, LUCKNOW -\n"
                "Karnataka 226018 Uttar Pradesh\n"
                "PAN of the Employee Reference No. provided by the\n"
                "PAN of the Deductor TAN of the Deductor Employee/Specified senior citizen by the Employer\n"
                "Summary of amount paid/credited and tax deducted at source thereon in respect of the employee\n"
                "Qa FXDREWPT 730907.00 82768.00 82768.00\n"
                "Certificate Number: VDMZRMA TAN of Employer: BLRA20443D PAN of Employee: GWPPS0879L Assessment Year: 2025-26\n"
            ),
        }

        result = await process_document(payload)

        self.assertEqual(result["document_type"], "form16")
        self.assertEqual(result["normalized_fields"]["name"], "AKANSHA SINHA")
        self.assertEqual(result["normalized_fields"]["employer_name"], "APTUSDATALABS TECHNOLOGIES PRIVATE LIMITED")
        self.assertEqual(result["normalized_fields"]["employer_tan"], "BLRA20443D")
        self.assertEqual(result["normalized_fields"]["tax_paid"]["tds_salary"], 82768.0)

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

    async def test_pdf_bytes_extract_form16_text_without_raw_text(self) -> None:
        payload = {
            "file_name": "form16.pdf",
            "mime_type": "application/pdf",
            "doc_type": "form16",
            "content_bytes": _make_pdf(
                "Form 16 PAN ABCDE1234F Employer TAN BLRA12345B Gross Salary 1250000 Tax deducted at source 125000"
            ),
        }

        result = await process_document(payload)

        self.assertEqual(result["document_type"], "form16")
        self.assertTrue(result["text"])
        self.assertGreater(result["text_extraction_confidence"], 0)
        self.assertFalse(result.get("ocr_used", False))
        self.assertEqual(result["normalized_fields"]["pan"], "ABCDE1234F")
        self.assertEqual(result["normalized_fields"]["salary"]["gross"], 1250000.0)

    async def test_health_insurance_pipeline_extracts_80d(self) -> None:
        payload = {
            "file_name": "health-insurance.txt",
            "mime_type": "text/plain",
            "doc_type": "health_insurance",
            "raw_text": (
                "Health Insurance Premium Certificate\n"
                "Policy Holder: Alice Example\n"
                "Self and Family Premium: 18000\n"
                "Parents Premium: 32000\n"
            ),
        }

        result = await process_document(payload)

        self.assertEqual(result["document_type"], "health_insurance")
        self.assertEqual(result["normalized_fields"]["deductions"]["80d"], 50000.0)
        self.assertEqual(result["normalized_fields"]["deductions"]["80d_parents"], 32000.0)