from __future__ import annotations

import unittest

from itx_backend.services.documents import _derive_portal_password


class DerivePortalPasswordTest(unittest.TestCase):
    """Unit coverage for the PAN+DOB -> portal-password helper.

    The API-level unlock flow is exercised in test_documents.py (gated on Postgres);
    this case focuses on the pure-function derivation that underpins both the auto-unlock
    path and the resolve_document_password agent tool.
    """

    def test_standard_pan_and_ddmmyyyy(self) -> None:
        self.assertEqual(
            _derive_portal_password("ABCDE1234F", "01011990"),
            "abcde1234f01011990",
        )

    def test_iso_date_is_rewritten_to_ddmmyyyy(self) -> None:
        # 1990-01-01 → leading 4 digits look like a year, so flip to DDMMYYYY.
        self.assertEqual(
            _derive_portal_password("ABCDE1234F", "1990-01-01"),
            "abcde1234f01011990",
        )

    def test_slash_separated_date(self) -> None:
        self.assertEqual(
            _derive_portal_password("DNUPS8632E", "26/05/1992"),
            "dnups8632e26051992",
        )

    def test_pan_is_lowercased(self) -> None:
        self.assertEqual(
            _derive_portal_password("dnups8632e", "26051992"),
            "dnups8632e26051992",
        )

    def test_missing_pan_or_dob_returns_none(self) -> None:
        self.assertIsNone(_derive_portal_password(None, "01011990"))
        self.assertIsNone(_derive_portal_password("ABCDE1234F", None))
        self.assertIsNone(_derive_portal_password("", ""))

    def test_malformed_pan_rejected(self) -> None:
        self.assertIsNone(_derive_portal_password("ABC12345XX", "01011990"))

    def test_malformed_dob_rejected(self) -> None:
        self.assertIsNone(_derive_portal_password("ABCDE1234F", "not-a-date"))
        self.assertIsNone(_derive_portal_password("ABCDE1234F", "010190"))


if __name__ == "__main__":
    unittest.main()
