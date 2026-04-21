from __future__ import annotations

from collections import defaultdict
from typing import Any

from .severity import severity


FIELD_DESCRIPTIONS = {
    "salary.gross": "AIS/TIS salary differs from Form 16 salary.",
    "tax_paid.tds_salary": "AIS/TIS salary TDS differs from Form 16 TDS.",
    "capital_gains.stcg": "AIS/TIS STCG differs from broker capital-gains statement.",
    "capital_gains.ltcg": "AIS/TIS LTCG differs from broker capital-gains statement.",
    "other_sources.total": "AIS/TIS interest or other-source income differs from certificates/Form 16A.",
    "tax_paid.tds_other": "AIS/TIS non-salary TDS differs from Form 16A or bank certificate.",
}


def _doc_category(field: str, doc_types: set[str]) -> str:
    if field.startswith("salary") or field.startswith("tax_paid.tds_salary"):
        return "form16" if "form16" in doc_types else "salary_docs"
    if field.startswith("capital_gains"):
        return "broker_capgain"
    if field.startswith("other_sources") or field.startswith("tax_paid.tds_other"):
        return "interest_docs"
    return "generic"


def _index(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        indexed[item["field"]].append(item)
    return indexed


def compare(ais_items: list[dict], doc_items: list[dict]) -> dict:
    ais_index = _index(ais_items)
    doc_index = _index(doc_items)

    harmless = []
    duplicate = []
    missing_doc = []
    under_reporting = []
    prefill_issue = []
    human_decision = []

    for field, ais_group in ais_index.items():
        ais_total = sum(float(item.get("amount", 0) or 0) for item in ais_group)
        doc_group = doc_index.get(field, [])
        doc_total = sum(float(item.get("amount", 0) or 0) for item in doc_group)
        doc_types = {str(item.get("document_type") or "unknown") for item in doc_group}
        category = _doc_category(field, doc_types)
        description = FIELD_DESCRIPTIONS.get(field, "AIS/TIS value differs from extracted document value.")

        if not doc_group:
            missing_doc.append(
                {
                    "field": field,
                    "severity": severity(ais_total, reference_amount=ais_total, category="missing-doc"),
                    "category": "missing-doc",
                    "description": f"{description} No supporting document value was extracted.",
                    "ais_value": ais_total,
                    "our_value": None,
                    "doc_value": None,
                }
            )
            continue

        diff_amount = ais_total - doc_total
        if abs(diff_amount) < 0.01:
            harmless.append(
                {
                    "field": field,
                    "severity": "info",
                    "category": "harmless",
                    "description": description,
                    "ais_value": ais_total,
                    "our_value": doc_total,
                    "doc_value": doc_total,
                }
            )
            continue

        mismatch = {
            "field": field,
            "severity": severity(diff_amount, reference_amount=ais_total, category="under-reporting" if diff_amount > 0 else "prefill_issue"),
            "description": description,
            "ais_value": ais_total,
            "our_value": doc_total,
            "doc_value": doc_total,
            "category": "under-reporting" if diff_amount > 0 else "prefill_issue",
        }
        if category == "form16":
            mismatch["form16_value"] = doc_total

        if diff_amount > 0:
            under_reporting.append(mismatch)
        else:
            prefill_issue.append(mismatch)

    for field, doc_group in doc_index.items():
        if field in ais_index:
            continue
        doc_total = sum(float(item.get("amount", 0) or 0) for item in doc_group)
        human_decision.append(
            {
                "field": field,
                "severity": "warning",
                "category": "human-decision",
                "description": "Document evidence exists without a corresponding AIS/TIS item. Review before filing.",
                "ais_value": None,
                "our_value": doc_total,
                "doc_value": doc_total,
            }
        )

    return {
        "harmless": harmless,
        "duplicate": duplicate,
        "missing_doc": missing_doc,
        "under_reporting": under_reporting,
        "prefill_issue": prefill_issue,
        "human_decision": human_decision,
        "counts": {
            "ais": len(ais_items),
            "docs": len(doc_items),
            "mismatches": len(missing_doc) + len(under_reporting) + len(prefill_issue) + len(human_decision),
        },
    }
