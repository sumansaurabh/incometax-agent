from __future__ import annotations

import re
from typing import Any


SECTION_PATTERN = re.compile(
    r"^(part\s+[a-z0-9]+|schedule\s+[a-z0-9]+|chapter\s+[ivxlcdm]+|annexure|summary|deductions?|tax paid|salary)\b",
    re.IGNORECASE,
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _join(tokens: list[str]) -> str:
    return " ".join(tokens).strip()


def sliding_window_chunks(text: str, *, size: int = 512, overlap: int = 64) -> list[dict[str, Any]]:
    words = _tokens(text)
    if not words:
        return []
    if len(words) <= size:
        return [{"chunk_text": _join(words), "section_name": None, "page_number": None}]

    chunks: list[dict[str, Any]] = []
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if not window:
            break
        chunks.append({"chunk_text": _join(window), "section_name": None, "page_number": None})
        if start + size >= len(words):
            break
    return chunks


def section_aware_chunks(text: str) -> list[dict[str, Any]]:
    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if SECTION_PATTERN.match(stripped) and current_lines:
            sections.append((current_title, current_lines))
            current_title = stripped[:80]
            current_lines = [stripped]
        else:
            if current_title is None and SECTION_PATTERN.match(stripped):
                current_title = stripped[:80]
            current_lines.append(stripped)

    if current_lines:
        sections.append((current_title, current_lines))

    if len(sections) <= 1:
        return sliding_window_chunks(text)

    chunks: list[dict[str, Any]] = []
    for section_name, lines in sections:
        section_text = "\n".join(lines)
        for chunk in sliding_window_chunks(section_text):
            chunk["section_name"] = section_name
            chunks.append(chunk)
    return chunks


def table_aware_chunks(tables: list[Any], *, page_number: int | None = None) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for table_index, table in enumerate(tables, start=1):
        rows = table if isinstance(table, list) else [table]
        current_rows: list[str] = []
        current_tokens = 0
        for row in rows:
            row_text = " | ".join(str(cell) for cell in row) if isinstance(row, list) else str(row)
            row_tokens = len(_tokens(row_text))
            if current_rows and current_tokens + row_tokens > 512:
                chunks.append(
                    {
                        "chunk_text": "\n".join(current_rows),
                        "section_name": f"table_{table_index}",
                        "page_number": page_number,
                    }
                )
                current_rows = []
                current_tokens = 0
            current_rows.append(row_text)
            current_tokens += row_tokens
        if current_rows:
            chunks.append(
                {
                    "chunk_text": "\n".join(current_rows),
                    "section_name": f"table_{table_index}",
                    "page_number": page_number,
                }
            )
    return chunks


def semantic_chunks(text: str) -> list[dict[str, Any]]:
    # Lightweight topic grouping for the worker: keep adjacent sentences
    # together until the chunk reaches the normal embedding window.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        token_count = len(_tokens(sentence))
        if current and current_tokens + token_count > 512:
            chunks.append({"chunk_text": " ".join(current), "section_name": None, "page_number": None})
            current = []
            current_tokens = 0
        if sentence:
            current.append(sentence)
            current_tokens += token_count
    if current:
        chunks.append({"chunk_text": " ".join(current), "section_name": None, "page_number": None})
    return chunks or sliding_window_chunks(text)


def chunk_processed_document(processed: dict[str, Any]) -> list[dict[str, Any]]:
    document_type = str(processed.get("document_type") or processed.get("doc_type") or "unknown")
    chunks: list[dict[str, Any]] = []

    if document_type in {"ais_csv", "tis", "bank_statement"} and processed.get("tables"):
        chunks.extend(table_aware_chunks(processed.get("tables", [])))

    pages = processed.get("pages") or []
    if pages:
        for page in pages:
            text = str(page.get("text") or "")
            page_no = int(page.get("page_no", 1))
            if not text.strip():
                continue
            if document_type in {"form16", "form16a", "home_loan_cert", "health_insurance"}:
                page_chunks = section_aware_chunks(text)
            elif document_type in {"ais_json", "interest_certificate", "rent_receipt"}:
                page_chunks = semantic_chunks(text)
            else:
                page_chunks = sliding_window_chunks(text)
            for chunk in page_chunks:
                chunk["page_number"] = page_no
                chunks.append(chunk)
    elif processed.get("text"):
        chunks.extend(sliding_window_chunks(str(processed["text"])))

    normalized_fields = processed.get("normalized_fields") or {}
    if normalized_fields:
        chunks.append(
            {
                "chunk_text": f"Normalized extracted tax facts: {normalized_fields}",
                "section_name": "normalized_fields",
                "page_number": None,
            }
        )

    return [
        {
            **chunk,
            "chunk_index": index,
        }
        for index, chunk in enumerate(chunks)
        if str(chunk.get("chunk_text") or "").strip()
    ]
