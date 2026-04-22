from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.db.session import get_pool

logger = logging.getLogger(__name__)


_FACT_ALIASES: dict[str, list[str]] = {
    "gross_salary": [
        "gross salary", "gross total income", "total salary", "salary u/s 17(1)", "salary income",
    ],
    "taxable_salary": ["taxable salary", "income chargeable under salaries", "net salary"],
    "tds": ["tax deducted at source", "tds", "tax deducted", "total tax deducted"],
    "tds_on_salary": ["tds on salary", "tax deducted on salary"],
    "employer_name": ["name of employer", "deductor name", "employer"],
    "employer_tan": ["tan of the deductor", "tan of deductor", "employer tan", "tan"],
    "employer_pan": ["pan of the deductor", "deductor pan", "employer pan"],
    "employee_pan": ["pan of the employee", "pan of employee", "employee pan", "pan"],
    "assessment_year": ["assessment year", "ay"],
    "financial_year": ["financial year", "fy"],
    "hra_received": ["hra received", "house rent allowance", "hra exemption u/s 10(13a)"],
    "standard_deduction": ["standard deduction"],
    "section_80c": ["section 80c", "80c deduction", "deduction 80c"],
    "section_80d": ["section 80d", "80d deduction", "deduction 80d"],
    "interest_income": ["interest from savings", "interest income", "bank interest"],
    "ifsc": ["ifsc"],
    "account_number": ["account no", "account number", "a/c no"],
    "total_income": ["total income", "gross total income"],
    "total_tax_payable": ["total tax payable", "tax on total income"],
    "refund": ["refund", "refund due"],
}


_AMOUNT_RE = re.compile(r"(?<![A-Za-z0-9])(?:rs\.?\s*|inr\s*|₹\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_TAN_RE = re.compile(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_AY_RE = re.compile(r"\b(20\d{2}\s*[-–]\s*(?:20)?\d{2})\b")


def _parse_amount(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _find_labeled_amount(text: str, labels: list[str]) -> Optional[tuple[float, int]]:
    """Return (amount, char_offset) for the first label-proximal amount found."""
    lowered = text.lower()
    for label in labels:
        idx = lowered.find(label.lower())
        if idx < 0:
            continue
        window = text[idx : idx + 280]
        match = _AMOUNT_RE.search(window[len(label):])
        if match is None:
            continue
        amount = _parse_amount(match.group(1))
        if amount is not None and amount > 0:
            return (amount, idx)
    return None


def _find_typed(text: str, kind: str) -> Optional[str]:
    """Pull a PAN / TAN / IFSC / AY out of a page."""
    if kind == "pan":
        hit = _PAN_RE.search(text)
    elif kind == "tan":
        hit = _TAN_RE.search(text)
    elif kind == "ifsc":
        hit = _IFSC_RE.search(text)
    elif kind == "ay":
        hit = _AY_RE.search(text)
    else:
        return None
    return hit.group(0) if hit else None


def _extract_from_page(fact: str, page_text: str) -> Optional[dict[str, Any]]:
    """Best-effort single-page extraction for one fact.

    Returns {value, confidence} or None. Confidence is a rough heuristic: 0.9 for a
    labelled-amount hit, 0.7 for a typed regex (PAN/TAN/IFSC), 0.0 (skipped) otherwise.
    The LLM sees confidence and can choose to disbelieve low scores.
    """
    if fact in {"employee_pan", "employer_pan"}:
        hit = _find_typed(page_text, "pan")
        return {"value": hit, "confidence": 0.7} if hit else None
    if fact == "employer_tan":
        hit = _find_typed(page_text, "tan")
        return {"value": hit, "confidence": 0.9} if hit else None
    if fact == "ifsc":
        hit = _find_typed(page_text, "ifsc")
        return {"value": hit, "confidence": 0.9} if hit else None
    if fact == "assessment_year":
        hit = _find_typed(page_text, "ay")
        return {"value": hit, "confidence": 0.85} if hit else None

    labels = _FACT_ALIASES.get(fact)
    if not labels:
        return None
    hit = _find_labeled_amount(page_text, labels)
    if hit is None:
        return None
    amount, _offset = hit
    return {"value": amount, "confidence": 0.85}


async def _fetch_document(document_id: str, thread_id: str) -> Optional[dict[str, Any]]:
    """Fetch the pages + normalized_json + metadata needed to extract facts."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            select d.id, d.thread_id, d.file_name, d.doc_type,
                   (
                       select normalized_json::text
                       from document_extractions
                       where document_id = d.id
                       order by created_at desc
                       limit 1
                   ) as normalized_json_text
            from documents d
            where d.id = $1::uuid
              and (d.thread_id = $2 or d.thread_id is null)
            """,
            document_id,
            thread_id,
        )
        if row is None:
            return None
        pages = await connection.fetch(
            """
            select page_no, text
            from document_pages
            where document_id = $1::uuid
            order by page_no asc
            """,
            document_id,
        )

    normalized: dict[str, Any] = {}
    if row["normalized_json_text"]:
        try:
            normalized = json.loads(row["normalized_json_text"])
        except json.JSONDecodeError:
            normalized = {}

    return {
        "document_id": str(row["id"]),
        "file_name": row["file_name"],
        "doc_type": row["doc_type"],
        "normalized_fields": normalized if isinstance(normalized, dict) else {},
        "pages": [
            {"page_no": int(page["page_no"]), "text": str(page["text"] or "")}
            for page in pages
        ],
    }


@tool_registry.tool(
    name="extract_facts",
    description=(
        "Read a specific uploaded tax document and extract structured facts from it: gross salary, "
        "TDS, employer TAN/PAN, assessment year, 80C deductions, HRA, interest income, etc. Call "
        "this when the user wants a precise number from one of their documents — for example 'what "
        "was my TDS on Form 16?' or 'what is the employer TAN?'. Returns a list of facts each with "
        "a value, a confidence score, and a source page number you can cite. Prefer this over "
        "document_search when the user asks for a single labelled value rather than a narrative. "
        "Document_id is the UUID returned from the documents list; facts is an array of the keys "
        "listed in the schema. Unknown or missing facts come back as {available: false} — never "
        "invent values."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The UUID of an uploaded document belonging to the current thread.",
            },
            "facts": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "string",
                    "enum": sorted(_FACT_ALIASES.keys()),
                },
                "description": "The list of fact keys to extract.",
            },
        },
        "required": ["document_id", "facts"],
        "additionalProperties": False,
    },
)
async def extract_facts(
    *,
    thread_id: str,
    document_id: str,
    facts: list[str],
) -> dict[str, Any]:
    if not document_id:
        return {"error": "document_id_required"}
    if not facts:
        return {"error": "facts_required"}

    document = await _fetch_document(document_id=document_id, thread_id=thread_id)
    if document is None:
        return {
            "error": "document_not_found",
            "hint": "Call document_search first, or list uploaded documents, to get a valid document_id.",
        }

    results: list[dict[str, Any]] = []
    normalized = document.get("normalized_fields") or {}
    pages = document.get("pages") or []

    for fact in facts:
        # Prefer the worker pipeline's normalized extraction when it has an answer.
        normalized_value = normalized.get(fact)
        if normalized_value not in (None, "", 0):
            results.append(
                {
                    "fact": fact,
                    "value": normalized_value,
                    "confidence": 0.95,
                    "source": "normalized_extraction",
                    "source_page": None,
                }
            )
            continue

        # Otherwise sweep the pages left-to-right; first match wins.
        page_hit: Optional[dict[str, Any]] = None
        for page in pages:
            extracted = _extract_from_page(fact, page["text"])
            if extracted is not None:
                page_hit = {
                    "fact": fact,
                    "value": extracted["value"],
                    "confidence": extracted["confidence"],
                    "source": "page_text_regex",
                    "source_page": page["page_no"],
                }
                break

        if page_hit is not None:
            results.append(page_hit)
        else:
            results.append(
                {
                    "fact": fact,
                    "available": False,
                    "reason": "not_found_in_document",
                }
            )

    return {
        "document_id": document["document_id"],
        "file_name": document["file_name"],
        "doc_type": document["doc_type"],
        "page_count": len(pages),
        "results": results,
    }
