from __future__ import annotations

from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.hybrid_retriever import hybrid_retriever


_DOC_TYPES = [
    "form16",
    "form16a",
    "form26as",
    "ais_csv",
    "ais_json",
    "tis",
    "bank_statement",
    "interest_certificate",
    "home_loan_cert",
    "health_insurance",
    "rent_receipt",
    "unknown",
]


@tool_registry.tool(
    name="document_search",
    description=(
        "Search the user's uploaded tax documents (Form 16, Form 26AS, AIS, TIS, bank statements, "
        "rent receipts, interest certificates, loan certificates, etc.) using hybrid retrieval: "
        "dense vector search is fused with BM25 keyword search via Reciprocal Rank Fusion, and "
        "the top candidates are reranked with a cross-encoder. Call this to answer any question "
        "that references the user's own data, for example 'what was my gross salary?', 'what "
        "interest did HDFC report to AIS?', 'is this donation reflected in Form 26AS?'. Prefer "
        "this tool over general knowledge whenever the user's own figures matter. Each result "
        "carries a citation in the form `filename:p.N` which you MUST quote verbatim in your "
        "answer. If no results come back, tell the user you cannot find it in their uploads and "
        "suggest uploading the relevant document."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Short natural-language query. Include concrete nouns the user might expect "
                    "to appear in the document (e.g. 'gross salary', 'TDS deducted', 'employer PAN')."
                ),
            },
            "doc_types": {
                "type": "array",
                "items": {"type": "string", "enum": _DOC_TYPES},
                "description": (
                    "Optional narrow-down. Omit to search across every uploaded document."
                ),
            },
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
async def document_search(
    *,
    thread_id: str,
    query: str,
    doc_types: Optional[list[str]] = None,
    top_k: int = 5,
) -> dict[str, Any]:
    if not query or not query.strip():
        return {"results": [], "error": "query_required"}
    return await hybrid_retriever.retrieve(
        thread_id=thread_id,
        query=query,
        top_k=top_k,
        doc_types=doc_types,
    )
