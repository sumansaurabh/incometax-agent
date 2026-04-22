from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import tempfile
from typing import Any, Iterable, Optional


PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
TAN_PATTERN = re.compile(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b")
IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
AY_PATTERN = re.compile(r"A\.?Y\.?\s*[:\-]?\s*(\d{4})\s*[-–/]\s*(\d{2,4})", re.IGNORECASE)
ASSESSMENT_YEAR_PATTERN = re.compile(r"Assessment\s+Year\s*[:\-]?\s*(\d{4})\s*[-–/]\s*(\d{2,4})", re.IGNORECASE)


def normalize_text(raw_text: str) -> str:
    return raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()


def parse_json_document(raw_text: str) -> dict[str, Any]:
    return json.loads(raw_text)


def parse_csv_rows(raw_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw_text))
    return [dict(row) for row in reader]


def decode_text_bytes(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def is_meaningful_text(text: str) -> bool:
    normalized = normalize_text(text)
    if len(normalized) < 40:
        return False
    lower = normalized.lower()
    pdf_artifact_terms = ("pdf-1.", "/xobject", "endstream", "xref", "obj", "decodeparms")
    artifact_hits = sum(1 for term in pdf_artifact_terms if term in lower)
    words = re.findall(r"[A-Za-z]{3,}", normalized)
    if len(words) < 8:
        return False
    if artifact_hits >= 3 and len(words) < 80:
        return False
    return True


def _run_tesseract(image_bytes: bytes) -> str:
    language = os.getenv("ITX_OCR_LANGUAGE", "eng")
    timeout = int(os.getenv("ITX_OCR_TIMEOUT_SECONDS", "45"))
    with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
            image.save(image_file.name, format="PNG")
        except Exception:
            image_file.write(image_bytes)
            image_file.flush()

        try:
            result = subprocess.run(
                ["tesseract", image_file.name, "stdout", "-l", language, "--psm", "6"],
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
    return normalize_text(result.stdout) if result.returncode == 0 else ""


def extract_text_from_image_bytes(content: bytes) -> str:
    return _run_tesseract(content)


def _extract_pdf_pages_with_pypdf(content: bytes) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except Exception:
        return []

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception:
        return []

    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = normalize_text(page.extract_text() or "")
        except Exception:
            text = ""
        pages.append(
            {
                "page_no": index,
                "text": text,
                "ocr_used": False,
                "ocr_confidence": None,
            }
        )
    return pages


def _extract_pdf_pages_with_pymupdf(content: bytes, *, render_ocr: bool, prefer_ocr: bool = False) -> list[dict[str, Any]]:
    try:
        import fitz
    except Exception:
        return []

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        return []

    pages: list[dict[str, Any]] = []
    for index, page in enumerate(document, start=1):
        try:
            native_text = normalize_text(page.get_text("text") or "")
        except Exception:
            native_text = ""
        if (is_meaningful_text(native_text) and not prefer_ocr) or not render_ocr:
            pages.append(
                {
                    "page_no": index,
                    "text": native_text,
                    "ocr_used": False,
                    "ocr_confidence": None,
                }
            )
            continue

        ocr_text = ""
        try:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            ocr_text = _run_tesseract(pixmap.tobytes("png"))
        except Exception:
            ocr_text = ""
        pages.append(
            {
                "page_no": index,
                "text": ocr_text or native_text,
                "ocr_used": bool(ocr_text),
                "ocr_confidence": 0.68 if ocr_text else 0.0,
            }
        )
    return pages


def extract_pdf_pages_from_bytes(content: bytes, *, render_ocr: bool = True) -> list[dict[str, Any]]:
    image_heavy = content.count(b"/Subtype/Image") > 0 or content.count(b"/Image") > 2
    if render_ocr and image_heavy:
        pages = _extract_pdf_pages_with_pymupdf(content, render_ocr=True, prefer_ocr=True)
        if pages and any(is_meaningful_text(str(page.get("text") or "")) for page in pages):
            return pages

    pages = _extract_pdf_pages_with_pypdf(content)
    if pages and any(is_meaningful_text(str(page.get("text") or "")) for page in pages):
        return pages

    pages = _extract_pdf_pages_with_pymupdf(content, render_ocr=render_ocr)
    if pages and any(is_meaningful_text(str(page.get("text") or "")) for page in pages):
        return pages
    return []


def _decode_pdf_literal(value: bytes) -> str:
    out = bytearray()
    escaped = False
    octal_buffer = b""
    replacements = {
        ord("n"): b"\n",
        ord("r"): b"\r",
        ord("t"): b"\t",
        ord("b"): b"\b",
        ord("f"): b"\f",
        ord("("): b"(",
        ord(")"): b")",
        ord("\\"): b"\\",
    }
    for byte in value:
        if octal_buffer:
            if 48 <= byte <= 55 and len(octal_buffer) < 3:
                octal_buffer += bytes([byte])
                continue
            out.append(int(octal_buffer, 8))
            octal_buffer = b""
        if escaped:
            escaped = False
            if 48 <= byte <= 55:
                octal_buffer = bytes([byte])
                continue
            out.extend(replacements.get(byte, bytes([byte])))
            continue
        if byte == 92:
            escaped = True
            continue
        out.append(byte)
    if octal_buffer:
        out.append(int(octal_buffer, 8))
    return out.decode("latin-1", errors="ignore")


def extract_text_from_pdf_bytes(content: bytes) -> str:
    pages = extract_pdf_pages_from_bytes(content, render_ocr=True)
    if pages:
        return normalize_text("\n\n".join(str(page.get("text") or "") for page in pages if page.get("text")))

    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", content, re.DOTALL)
    if not streams:
        streams = [content]

    chunks: list[str] = []
    for stream in streams:
        for literal in re.findall(rb"\((.*?)\)\s*Tj", stream, re.DOTALL):
            text = _decode_pdf_literal(literal).strip()
            if text:
                chunks.append(text)
        for array_literal in re.findall(rb"\[(.*?)\]\s*TJ", stream, re.DOTALL):
            nested = re.findall(rb"\((.*?)\)", array_literal, re.DOTALL)
            text = "".join(_decode_pdf_literal(item) for item in nested).strip()
            if text:
                chunks.append(text)

    if chunks:
        return normalize_text("\n".join(chunks))

    decoded = decode_text_bytes(content)
    fallback = normalize_text("\n".join(re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.:;@#/()_\-]{4,}", decoded)))
    return fallback if is_meaningful_text(fallback) else ""


def fallback_ocr_text(content: bytes) -> str:
    if content.startswith(b"%PDF"):
        return extract_text_from_pdf_bytes(content)
    image_text = extract_text_from_image_bytes(content)
    if image_text:
        return image_text
    decoded = decode_text_bytes(content)
    chunks = re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.:;@#/()_\-]{3,}", decoded)
    fallback = normalize_text("\n".join(chunks))
    return fallback if is_meaningful_text(fallback) else ""


def parse_indian_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    cleaned = (
        text.replace(",", "")
        .replace("₹", "")
        .replace("INR", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .strip()
    )
    cleaned = cleaned.replace("(", "-").replace(")", "")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    return match.group(0) if match else None


def extract_pan(text: str) -> Optional[str]:
    return first_match(PAN_PATTERN, text)


def extract_tan(text: str) -> Optional[str]:
    return first_match(TAN_PATTERN, text)


def extract_ifsc(text: str) -> Optional[str]:
    return first_match(IFSC_PATTERN, text)


def extract_assessment_year(text: str) -> Optional[str]:
    match = AY_PATTERN.search(text)
    if not match:
        match = ASSESSMENT_YEAR_PATTERN.search(text)
    if not match:
        return None
    start_year, end_year = match.groups()
    if len(end_year) == 4:
        return f"{start_year}-{end_year[-2:]}"
    return f"{start_year}-{end_year}"


def extract_labeled_amount(text: str, labels: Iterable[str]) -> Optional[float]:
    for label in labels:
        pattern = re.compile(
            rf"{re.escape(label)}[^0-9\-]{{0,24}}([0-9][0-9,]*(?:\.[0-9]{{1,2}})?)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            amount = parse_indian_amount(match.group(1))
            if amount is not None:
                return amount
    return None


def extract_nearby_amount(text: str, labels: Iterable[str], *, window: int = 220, prefer: str = "last") -> Optional[float]:
    amount_pattern = re.compile(r"(?<![A-Z0-9])([0-9][0-9,]{2,}(?:\.[0-9]{1,2})?|[0-9]\.[0-9]{1,2})")
    for label in labels:
        match = re.search(re.escape(label), text, re.IGNORECASE)
        if not match:
            continue
        snippet = text[match.end() : match.end() + window]
        amounts = [parse_indian_amount(value) for value in amount_pattern.findall(snippet)]
        amounts = [amount for amount in amounts if amount is not None]
        if amounts:
            return amounts[0] if prefer == "first" else amounts[-1]
    return None


def extract_labeled_text(text: str, labels: Iterable[str]) -> Optional[str]:
    for label in labels:
        pattern = re.compile(rf"{re.escape(label)}\s*[:\-]?\s*([^\n]+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def deep_find(data: Any, aliases: Iterable[str]) -> Any:
    normalized_aliases = {alias.lower() for alias in aliases}

    def _walk(value: Any) -> Any:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in normalized_aliases:
                    return item
            for item in value.values():
                found = _walk(item)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = _walk(item)
                if found is not None:
                    return found
        return None

    return _walk(data)


def aggregate_csv_amount(rows: list[dict[str, str]], include_terms: Iterable[str]) -> float:
    normalized_terms = [term.lower() for term in include_terms]
    total = 0.0
    for row in rows:
        haystack = " ".join(str(value) for value in row.values()).lower()
        if not any(term in haystack for term in normalized_terms):
            continue
        for key in ("amount", "Amount", "value", "Value", "transaction_amount", "Transaction Amount"):
            amount = parse_indian_amount(row.get(key))
            if amount is not None:
                total += amount
                break
    return total
