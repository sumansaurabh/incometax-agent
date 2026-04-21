from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Iterable, Optional


PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
TAN_PATTERN = re.compile(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b")
IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
AY_PATTERN = re.compile(r"A\.?Y\.?\s*[:\-]?\s*(\d{4})\s*[-–/]\s*(\d{2,4})", re.IGNORECASE)


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
    return normalize_text("\n".join(re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.:;@#/()_\-]{4,}", decoded)))


def fallback_ocr_text(content: bytes) -> str:
    decoded = decode_text_bytes(content)
    chunks = re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.:;@#/()_\-]{3,}", decoded)
    return normalize_text("\n".join(chunks))


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