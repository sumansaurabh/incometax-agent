from __future__ import annotations

from itx_workers.reconcile.ais_vs_docs import compare as compare_ais_vs_docs
from itx_workers.reconcile.duplicates import find_duplicate_documents
from itx_workers.reconcile.helpers import flatten_tax_facts

from itx_backend.agent.state import AgentState


AIS_DOC_TYPES = {"ais_json", "ais_csv", "ais_pdf", "tis"}
AIS_FIELDS = {
    "salary.gross",
    "tax_paid.tds_salary",
    "other_sources.total",
    "tax_paid.tds_other",
    "capital_gains.stcg",
    "capital_gains.ltcg",
}


def _to_reconciliation_items(document: dict, include_fields: set[str]) -> list[dict]:
    items = []
    for field, value in flatten_tax_facts("", document.get("normalized_fields", {})):
        if field not in include_fields:
            continue
        if isinstance(value, (int, float)):
            items.append(
                {
                    "field": field,
                    "amount": float(value),
                    "document_id": document.get("id"),
                    "document_type": document.get("type"),
                }
            )
    return items


async def run(state: AgentState) -> AgentState:
    documents = state.get("documents", [])

    ais_documents = [doc for doc in documents if doc.get("type") in AIS_DOC_TYPES]
    evidence_documents = [doc for doc in documents if doc.get("type") not in AIS_DOC_TYPES]

    ais_items = [item for doc in ais_documents for item in _to_reconciliation_items(doc, AIS_FIELDS)]
    doc_items = [item for doc in evidence_documents for item in _to_reconciliation_items(doc, AIS_FIELDS)]

    comparison = compare_ais_vs_docs(ais_items, doc_items)
    mismatches = []
    for group in ("duplicate", "missing_doc", "under_reporting", "prefill_issue", "human_decision"):
        mismatches.extend(comparison.get(group, []))
    mismatches.extend(find_duplicate_documents(documents))

    ais_facts = {}
    for doc in ais_documents:
        for field, value in flatten_tax_facts("", doc.get("normalized_fields", {})):
            if field in AIS_FIELDS:
                ais_facts[field] = value

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"Reconciliation complete: {len(mismatches)} mismatches detected.",
            "metadata": {"node": "reconcile"},
        }
    )

    state.apply_update(
        {
            "messages": messages,
            "ais_facts": ais_facts,
            "reconciliation": {
                "mismatches": mismatches,
                "summary": comparison.get("counts", {}),
            },
        }
    )
    return state
