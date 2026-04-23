from __future__ import annotations

import io
import unittest

from itx_workers.parsers.common import (
    PasswordRequiredError,
    _looks_like_encrypted_ais_json,
    decrypt_pdf_bytes,
    detect_pdf_encryption,
)
from itx_workers.pipelines.text_extract import run as text_extract_run


def _make_plain_pdf(text: str) -> bytes:
    """Minimal PDF builder copied-down from test_document_pipeline helpers."""
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
    offsets, cursor = [], len(header)
    for obj in objects:
        offsets.append(cursor)
        cursor += len(obj)
    xref = [f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode()]
    for offset in offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer << /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()
    return header + body + b"".join(xref) + trailer


def _make_encrypted_pdf(text: str, password: str) -> bytes:
    """Encrypt a synthetic PDF with pypdf so tests have no external fixture dependency."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(_make_plain_pdf(text)))
    writer = PdfWriter(clone_from=reader)
    writer.encrypt(user_password=password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class PdfEncryptionDetectionTest(unittest.TestCase):
    def test_plain_pdf_is_not_detected_as_encrypted(self) -> None:
        self.assertFalse(detect_pdf_encryption(_make_plain_pdf("hello")))

    def test_encrypted_pdf_is_detected(self) -> None:
        self.assertTrue(detect_pdf_encryption(_make_encrypted_pdf("hello", "s3cret")))

    def test_decrypt_with_correct_password_returns_plaintext_pdf(self) -> None:
        encrypted = _make_encrypted_pdf("hello world", "pw123")
        result = decrypt_pdf_bytes(encrypted, "pw123")
        self.assertIsNotNone(result)
        self.assertFalse(detect_pdf_encryption(result))

    def test_decrypt_with_wrong_password_returns_none(self) -> None:
        encrypted = _make_encrypted_pdf("hello", "correct")
        self.assertIsNone(decrypt_pdf_bytes(encrypted, "wrong"))

    def test_text_extract_raises_password_required_for_encrypted_pdf(self) -> None:
        encrypted = _make_encrypted_pdf("hello", "correct")
        with self.assertRaises(PasswordRequiredError) as ctx:
            text_extract_run(
                {
                    "content_bytes": encrypted,
                    "mime_type": "application/pdf",
                    "file_name": "Form16.pdf",
                }
            )
        self.assertEqual(ctx.exception.kind, "pdf")


class AisJsonEncryptionDetectionTest(unittest.TestCase):
    def test_plain_json_is_not_flagged(self) -> None:
        self.assertFalse(_looks_like_encrypted_ais_json(b'{"ok": true}', "example_AIS.json"))

    def test_non_json_extension_is_ignored(self) -> None:
        # Encrypted-looking payload but wrong extension — skip silently, let other paths handle it.
        payload = b"a" * 64 + b"QkFTRTY0"
        self.assertFalse(_looks_like_encrypted_ais_json(payload, "example_AIS.txt"))

    def test_hex_header_plus_base64_body_is_flagged(self) -> None:
        payload = (b"0" * 64) + (b"A" * 64)
        self.assertTrue(_looks_like_encrypted_ais_json(payload, "example_AIS.json"))

    def test_text_extract_raises_for_encrypted_ais_json(self) -> None:
        payload = (b"0" * 64) + (b"A" * 64)
        with self.assertRaises(PasswordRequiredError) as ctx:
            text_extract_run(
                {
                    "content_bytes": payload,
                    "mime_type": "application/json",
                    "file_name": "XXXPS8632X_2025-26_AIS_23042026.json",
                }
            )
        self.assertEqual(ctx.exception.kind, "ais_json")
        self.assertEqual(ctx.exception.hint, "upload_ais_pdf_instead")


if __name__ == "__main__":
    unittest.main()
