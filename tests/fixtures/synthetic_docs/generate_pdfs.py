"""Generate tiny synthetic PDF fixtures for parser smoke tests."""

from pathlib import Path


def make_pdf(text: str) -> bytes:
    # Minimal single-page PDF content stream.
    payload = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET"
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(payload)} >> stream\n{payload}\nendstream endobj\n".encode(),
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    header = b"%PDF-1.4\n"
    body = b""
    offsets = [0]
    cursor = len(header)
    for obj in objects:
        offsets.append(cursor)
        body += obj
        cursor += len(obj)

    xref_start = len(header) + len(body)
    xref = [f"xref\n0 {len(offsets)}\n0000000000 65535 f \\n".encode()]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n \\n".encode())
    trailer = f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()

    return header + body + b"".join(xref) + trailer


def main() -> None:
    base = Path(__file__).parent
    fixtures = {
        "form16_sample.pdf": "FORM 16 SYNTHETIC PAN ABCDE1234F TAN BLRA12345B Gross Salary 1250000",
        "ais_sample.pdf": "AIS SYNTHETIC PAN ABCDE1234F Interest Income 25000 Dividend 12000",
        "tis_sample.pdf": "TIS SYNTHETIC PAN ABCDE1234F Tax Paid 145000 Refund 12000",
    }
    for name, text in fixtures.items():
        out = base / name
        out.write_bytes(make_pdf(text))
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
