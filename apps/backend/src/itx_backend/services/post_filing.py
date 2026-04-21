from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from itx_backend.agent.state import AgentState


def _assessment_year_value(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"(20\d{2})", value)
    if not match:
        return None
    return int(match.group(1))


def _next_assessment_year(value: Optional[str]) -> Optional[str]:
    start = _assessment_year_value(value)
    if start is None:
        return None
    return f"{start + 1}-{str(start + 2)[-2:]}"


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return 0.0
        try:
            return float(normalized)
        except ValueError:
            return 0.0
    return 0.0


def _amount_from_text(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"([0-9][0-9,]*(?:\.\d{1,2})?)", value)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                return None
    return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _portal_value_by_field_key(portal_state: Optional[dict[str, Any]], field_key: str) -> Optional[str]:
    if not portal_state:
        return None
    for value in (portal_state.get("fields") or {}).values():
        if not isinstance(value, dict):
            continue
        if value.get("fieldKey") == field_key:
            return _text(value.get("value"))
    return None


def _currency_delta(label: str, current: float, prior: float) -> str:
    delta = current - prior
    if abs(delta) < 1:
        return f"{label} stayed broadly flat year over year."
    direction = "increased" if delta > 0 else "decreased"
    return f"{label} {direction} by INR {abs(delta):,.0f} year over year."


def _deduction_breakdown(data: dict[str, Any]) -> dict[str, float]:
    deductions = data.get("deductions") or {}
    if not isinstance(deductions, dict):
        return {}
    return {
        key: _as_float(value)
        for key, value in deductions.items()
        if isinstance(value, (int, float, Decimal, str))
    }


def assessment_year_for_state(state: AgentState) -> Optional[str]:
    if state.submission_summary and state.submission_summary.get("assessment_year"):
        return str(state.submission_summary["assessment_year"])
    if state.tax_facts.get("assessment_year"):
        return str(state.tax_facts["assessment_year"])
    return None


def select_prior_filed_state(current_state: AgentState, candidate_states: list[AgentState]) -> Optional[AgentState]:
    current_ay = _assessment_year_value(assessment_year_for_state(current_state))
    eligible = [
        state
        for state in candidate_states
        if state.user_id == current_state.user_id
        and state.thread_id != current_state.thread_id
        and (state.submission_status in {"submitted", "verified"} or bool(state.filing_artifacts))
        and assessment_year_for_state(state)
    ]
    eligible.sort(
        key=lambda state: (_assessment_year_value(assessment_year_for_state(state)) or 0, state.thread_id),
        reverse=True,
    )
    if current_ay is None:
        return eligible[0] if eligible else None
    for state in eligible:
        prior_ay = _assessment_year_value(assessment_year_for_state(state))
        if prior_ay is not None and prior_ay < current_ay:
            return state
    return eligible[0] if eligible else None


def build_year_over_year_comparison(current_state: AgentState, prior_state: Optional[AgentState]) -> dict[str, Any]:
    current_summary = current_state.submission_summary or {}
    prior_summary = (prior_state.submission_summary if prior_state else None) or {}
    current_metrics = {
        "gross_total_income": _as_float(current_summary.get("gross_total_income")),
        "total_deductions": _as_float(current_summary.get("total_deductions")),
        "taxable_income": _as_float(current_summary.get("taxable_income")),
        "net_tax_liability": _as_float(current_summary.get("net_tax_liability")),
        "tax_payable": _as_float(current_summary.get("tax_payable")),
        "refund_due": _as_float(current_summary.get("refund_due")),
        "total_tax_paid": _as_float(current_summary.get("total_tax_paid")),
    }
    prior_metrics = {
        key: _as_float(prior_summary.get(key))
        for key in current_metrics
    }
    metric_comparison = {
        key: {
            "current": current_metrics[key],
            "prior": prior_metrics[key],
            "delta": current_metrics[key] - prior_metrics[key],
        }
        for key in current_metrics
    }
    current_regime = str(current_summary.get("regime") or current_state.tax_facts.get("regime") or "unknown")
    prior_regime = str(prior_summary.get("regime") or (prior_state.tax_facts.get("regime") if prior_state else "unknown") or "unknown")
    current_deductions = _deduction_breakdown(current_state.tax_facts)
    prior_deductions = _deduction_breakdown(prior_state.tax_facts if prior_state else {})
    deduction_keys = sorted(set(current_deductions) | set(prior_deductions))
    deduction_comparison = {
        key: {
            "current": current_deductions.get(key, 0.0),
            "prior": prior_deductions.get(key, 0.0),
            "delta": current_deductions.get(key, 0.0) - prior_deductions.get(key, 0.0),
        }
        for key in deduction_keys
    }
    highlights = [
        _currency_delta("Gross income", current_metrics["gross_total_income"], prior_metrics["gross_total_income"]),
        _currency_delta("Total deductions", current_metrics["total_deductions"], prior_metrics["total_deductions"]),
        _currency_delta("Net tax liability", current_metrics["net_tax_liability"], prior_metrics["net_tax_liability"]),
    ]
    if current_regime != prior_regime and prior_state is not None:
        highlights.append(f"Regime changed from {prior_regime} to {current_regime}.")
    if current_metrics["refund_due"] > 0:
        highlights.append(f"Current filing expects a refund of INR {current_metrics['refund_due']:,.0f}.")
    if not prior_state:
        highlights.append("No prior filed return was found for automated year-over-year comparison.")
    return {
        "thread_id": current_state.thread_id,
        "current_assessment_year": assessment_year_for_state(current_state),
        "prior_thread_id": prior_state.thread_id if prior_state else None,
        "prior_assessment_year": assessment_year_for_state(prior_state) if prior_state else None,
        "regime": {
            "current": current_regime,
            "prior": prior_regime if prior_state else None,
            "changed": bool(prior_state and current_regime != prior_regime),
        },
        "metrics": metric_comparison,
        "deductions": deduction_comparison,
        "highlights": highlights,
    }


def build_next_ay_checklist(state: AgentState) -> dict[str, Any]:
    current_ay = assessment_year_for_state(state)
    target_ay = _next_assessment_year(current_ay) or "next-ay"
    tax_facts = state.tax_facts or {}
    summary = state.submission_summary or {}
    deductions = _deduction_breakdown(tax_facts)
    items: list[dict[str, Any]] = [
        {
            "code": "ais-tis",
            "title": f"Download AIS and TIS for AY {target_ay}",
            "reason": "These become the reconciliation baseline for the next filing season.",
            "category": "documents",
            "priority": "high",
            "due_by": "Before July",
            "recommended_documents": ["AIS", "TIS"],
            "status": "pending",
        },
        {
            "code": "filing-artifacts",
            "title": "Preserve this year's filing bundle and acknowledgement",
            "reason": "Prior-year artifacts help with revisions, notices, and year-over-year review.",
            "category": "records",
            "priority": "medium",
            "due_by": "Immediately after filing",
            "recommended_documents": ["ITR acknowledgement", "Submission summary", "Evidence bundle"],
            "status": "pending",
        },
    ]
    if _as_float((tax_facts.get("salary") or {}).get("gross") or tax_facts.get("gross_salary")) > 0:
        items.append(
            {
                "code": "salary-proofs",
                "title": "Collect Form 16 and final payslips",
                "reason": "Salary income was part of this filing and should be preserved for the next AY.",
                "category": "income",
                "priority": "high",
                "due_by": "When employer issues Form 16",
                "recommended_documents": ["Form 16", "Final payslips"],
                "status": "pending",
            }
        )
    if deductions:
        items.append(
            {
                "code": "deduction-proofs",
                "title": "Organize deduction proofs as you incur them",
                "reason": "This filing claimed deductions that will be easier to defend if receipts stay categorized through the year.",
                "category": "deductions",
                "priority": "high",
                "due_by": "Monthly or quarterly",
                "recommended_documents": sorted([f"Section {key.upper()} proof" for key in deductions.keys()]),
                "status": "pending",
            }
        )
    if _as_float((tax_facts.get("exemptions") or {}).get("hra") or tax_facts.get("hra")) > 0:
        items.append(
            {
                "code": "hra-proof",
                "title": "Keep rent receipts and landlord PAN trail",
                "reason": "HRA-related exemption activity was detected in this filing.",
                "category": "deductions",
                "priority": "medium",
                "due_by": "Monthly",
                "recommended_documents": ["Rent receipts", "Landlord PAN if applicable"],
                "status": "pending",
            }
        )
    if tax_facts.get("capital_gains"):
        items.append(
            {
                "code": "capital-gains",
                "title": "Export broker statements and contract notes regularly",
                "reason": "Capital-gains activity was detected and lot-level history is easier to preserve during the year.",
                "category": "capital-gains",
                "priority": "high",
                "due_by": "Monthly",
                "recommended_documents": ["Broker statements", "Contract notes", "Dividend statements"],
                "status": "pending",
            }
        )
    if tax_facts.get("house_property") or _as_float((tax_facts.get("home_loan") or {}).get("interest") or (tax_facts.get("house_property") or {}).get("interest_on_loan")) > 0:
        items.append(
            {
                "code": "home-loan",
                "title": "Request the annual home-loan interest certificate early",
                "reason": "Home-loan or property interest activity was part of this filing.",
                "category": "property",
                "priority": "medium",
                "due_by": "Before June",
                "recommended_documents": ["Interest certificate", "Principal repayment statement"],
                "status": "pending",
            }
        )
    if _as_float(summary.get("refund_due")) > 0:
        items.append(
            {
                "code": "refund-bank",
                "title": "Keep one bank account pre-validated for refunds",
                "reason": "This filing is refund-bearing, so bank readiness will matter again next AY.",
                "category": "banking",
                "priority": "medium",
                "due_by": "Before filing opens",
                "recommended_documents": ["Cancelled cheque", "IFSC confirmation"],
                "status": "pending",
            }
        )
    summary_payload = {
        "headline": f"Collect these {len(items)} items before July for AY {target_ay}.",
        "current_assessment_year": current_ay,
        "target_assessment_year": target_ay,
        "priority_count": len([item for item in items if item["priority"] == "high"]),
    }
    return {
        "thread_id": state.thread_id,
        "current_assessment_year": current_ay,
        "target_assessment_year": target_ay,
        "summary": summary_payload,
        "items": items,
    }


def prepare_notice_response(state: AgentState, notice_text: str, notice_type: str = "143(1)") -> dict[str, Any]:
    normalized_text = notice_text.strip()
    assessment_year = None
    if match := re.search(r"(?:Assessment Year|AY)\s*[:\-]?\s*(20\d{2}\s*-\s*\d{2})", normalized_text, re.IGNORECASE):
        assessment_year = match.group(1).replace(" ", "")
    reference = None
    if match := re.search(r"(?:DIN|Document Identification Number|Reference\s*No\.?|Reference)\s*[:\-]?\s*([A-Z0-9\-/]+)", normalized_text, re.IGNORECASE):
        reference = match.group(1).strip()
    issue_date = None
    if match := re.search(r"(?:Date of Issue|Issue Date|Issued on)\s*[:\-]?\s*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}|20\d{2}-\d{2}-\d{2})", normalized_text, re.IGNORECASE):
        issue_date = match.group(1)
    response_due = None
    if match := re.search(r"(?:Response due by|Due Date|Please respond by)\s*[:\-]?\s*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}|20\d{2}-\d{2}-\d{2})", normalized_text, re.IGNORECASE):
        response_due = match.group(1)
    refund_amount = None
    if match := re.search(r"(?:Refund(?:\s+determined|\s+due)?|Amount refundable)\s*[:\-]?\s*(?:Rs\.?|INR)?\s*([0-9,]+(?:\.\d{1,2})?)", normalized_text, re.IGNORECASE):
        refund_amount = _amount_from_text(match.group(1))
    demand_amount = None
    if match := re.search(r"(?:Demand(?:\s+payable|\s+raised)?|Tax payable)\s*[:\-]?\s*(?:Rs\.?|INR)?\s*([0-9,]+(?:\.\d{1,2})?)", normalized_text, re.IGNORECASE):
        demand_amount = _amount_from_text(match.group(1))
    adjustment_lines = [
        line.strip()
        for line in normalized_text.splitlines()
        if re.search(r"adjust|disallow|mismatch|difference|interest u/s|tds|income from other sources|deduction", line, re.IGNORECASE)
    ]
    keywords = "\n".join(adjustment_lines)
    documents_to_collect = ["Filed return acknowledgement", "Submission summary", "Evidence bundle"]
    if re.search(r"tds|form 16|form 16a", keywords, re.IGNORECASE):
        documents_to_collect.extend(["Form 16 / Form 16A", "AIS/TIS snapshot"])
    if re.search(r"80c|80d|deduction|chapter vi a", keywords, re.IGNORECASE):
        documents_to_collect.append("Deduction proofs and receipts")
    if re.search(r"interest|bank|other sources", keywords, re.IGNORECASE):
        documents_to_collect.append("Bank interest certificates")
    if re.search(r"salary", keywords, re.IGNORECASE):
        documents_to_collect.append("Salary slips and employer breakup")
    documents_to_collect = list(dict.fromkeys(documents_to_collect))
    action = "review_and_prepare_response" if adjustment_lines or demand_amount else "review_and_record"
    extracted_adjustments_md = [f"- {line}" for line in adjustment_lines] or [
        "- No explicit adjustment lines were detected in the pasted notice text."
    ]
    suggested_documents_md = [f"- {item}" for item in documents_to_collect]
    explanation_md = "\n".join(
        [
            f"# Notice Preparation ({notice_type})",
            "",
            f"Assessment Year: {assessment_year or assessment_year_for_state(state) or 'unknown'}",
            f"Reference: {reference or 'not found'}",
            f"Issue Date: {issue_date or 'not found'}",
            f"Response Due: {response_due or 'not stated'}",
            f"Demand Amount: INR {demand_amount:,.0f}" if demand_amount is not None else "Demand Amount: none detected",
            f"Refund Amount: INR {refund_amount:,.0f}" if refund_amount is not None else "Refund Amount: none detected",
            "",
            "## What This Means",
            "This is a read-only preparation view. The system does not file a notice response for you.",
            "Review the extracted adjustments, compare them against your filed summary and evidence bundle, and prepare the supporting documents before responding on the portal.",
            "",
            "## Extracted Adjustments",
            *extracted_adjustments_md,
            "",
            "## Suggested Response Data",
            *suggested_documents_md,
        ]
    )
    return {
        "notice_type": notice_type,
        "assessment_year": assessment_year or assessment_year_for_state(state),
        "reference": reference,
        "issue_date": issue_date,
        "response_due": response_due,
        "demand_amount": demand_amount,
        "refund_amount": refund_amount,
        "adjustments": adjustment_lines,
        "explanation_md": explanation_md,
        "suggested_response": {
            "action": action,
            "documents_to_collect": documents_to_collect,
            "supporting_summary": state.submission_summary or {},
            "response_due": response_due,
        },
    }


def build_refund_status_capture(
    state: AgentState,
    *,
    page_type: Optional[str],
    page_title: Optional[str],
    page_url: Optional[str],
    portal_state: Optional[dict[str, Any]],
    manual_status: Optional[str],
    manual_portal_ref: Optional[str],
    manual_refund_amount: Optional[Any],
    manual_issued_at: Optional[str],
    manual_processed_at: Optional[str],
    manual_refund_mode: Optional[str],
    manual_bank_masked: Optional[str],
) -> dict[str, Any]:
    parsed = {
        "status": _text(manual_status) or _portal_value_by_field_key(portal_state, "refund_status"),
        "portal_ref": _text(manual_portal_ref) or _portal_value_by_field_key(portal_state, "refund_reference"),
        "refund_amount": _amount_from_text(manual_refund_amount) or _amount_from_text(_portal_value_by_field_key(portal_state, "refund_amount")),
        "issued_at": _text(manual_issued_at) or _portal_value_by_field_key(portal_state, "issued_at"),
        "processed_at": _text(manual_processed_at) or _portal_value_by_field_key(portal_state, "processed_at"),
        "refund_mode": _text(manual_refund_mode) or _portal_value_by_field_key(portal_state, "refund_mode"),
        "bank_masked": _text(manual_bank_masked) or _portal_value_by_field_key(portal_state, "bank_account_masked"),
    }
    if not parsed["status"]:
        raise ValueError("refund_status_unavailable")
    source = "portal_snapshot" if page_type == "refund-status" else "manual"
    return {
        "thread_id": state.thread_id,
        "assessment_year": assessment_year_for_state(state),
        "status": parsed["status"],
        "portal_ref": parsed["portal_ref"],
        "refund_amount": parsed["refund_amount"],
        "issued_at": parsed["issued_at"],
        "processed_at": parsed["processed_at"],
        "refund_mode": parsed["refund_mode"],
        "bank_masked": parsed["bank_masked"],
        "source": source,
        "observation": {
            "page_type": page_type,
            "page_title": page_title,
            "page_url": page_url,
            "portal_state": portal_state or {},
        },
    }