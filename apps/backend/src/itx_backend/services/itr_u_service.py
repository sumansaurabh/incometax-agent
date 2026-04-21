"""
ITR-U (Updated Return) service — Section 139(8A) of the Income Tax Act.

An updated return allows a taxpayer to correct errors in a previously filed
return by paying additional tax.  Key constraints:
  - Must be filed within two years of the end of the relevant assessment year.
  - Cannot be used to increase a refund or reduce tax liability.
  - Cannot be filed where assessment/reassessment is already pending or complete.
  - Requires an explicit escalation confirmation (CA / reviewer gate) before
    a new thread is spawned.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from itx_backend.agent.state import AgentState


# ---------------------------------------------------------------------------
# ITR-U reason codes mandated by the Income Tax Department
# ---------------------------------------------------------------------------

VALID_REASON_CODES: dict[str, str] = {
    "income_not_disclosed": "Income not fully disclosed in original/revised return",
    "wrong_head_of_income": "Income disclosed under wrong head",
    "reduction_of_carry_forward_loss": "Reduction of carry-forward loss or unabsorbed depreciation",
    "reduction_of_tax_credit": "Reduction of tax credit u/s 115JB / 115JC",
    "wrong_rate_of_tax": "Tax computed at wrong rate",
    "other": "Any other reason (provide detail)",
}

# Assessment years follow the pattern "YYYY-YY" (e.g. "2025-26").
# The AY ends on 31 March of the second year; the ITR-U deadline is 2 years later.
_AY_DEADLINE_YEARS = 2


def _ay_end_date(assessment_year: str) -> Optional[date]:
    """Return the date on which the AY ends (31 March of the second year)."""
    try:
        _, end_yy = assessment_year.split("-")
        # Handle both "YY" and "YYYY" suffixes
        if len(end_yy) == 2:
            end_year = int(assessment_year.split("-")[0][:2] + end_yy)
        else:
            end_year = int(end_yy)
        return date(end_year, 3, 31)
    except Exception:
        return None


def _itr_u_deadline(ay_end: date) -> date:
    return ay_end.replace(year=ay_end.year + _AY_DEADLINE_YEARS)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def check_itr_u_eligibility(
    state: AgentState,
    *,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    """
    Return an eligibility dict.  ``eligible`` is True only when all checks pass.
    ``warnings`` lists conditions that may block filing even when eligible.
    ``blockers`` lists hard blockers.
    """
    today = as_of or date.today()
    blockers: list[str] = []
    warnings: list[str] = []

    # 1. Original return must have been filed.
    submission_status = state.submission_status or "draft"
    if submission_status not in ("submitted", "verified", "archived"):
        blockers.append(
            f"Original return has not been filed yet (status: {submission_status}). "
            "ITR-U can only be filed after the original return is submitted."
        )

    # 2. Must not already be an ITR-U thread (prevent double-update).
    revision_context = state.revision_context or {}
    if revision_context.get("is_itr_u"):
        blockers.append("This thread is itself an updated return. ITR-U cannot be filed on an ITR-U.")

    # 3. Deadline check.
    tax_facts = state.tax_facts or {}
    assessment_year: Optional[str] = (
        (state.submission_summary or {}).get("assessment_year")
        or tax_facts.get("assessment_year")
    )
    ay_end: Optional[date] = _ay_end_date(assessment_year) if assessment_year else None
    if ay_end is None:
        warnings.append("Assessment year could not be determined; deadline cannot be verified automatically.")
    else:
        deadline = _itr_u_deadline(ay_end)
        if today > deadline:
            blockers.append(
                f"ITR-U deadline for AY {assessment_year} has passed "
                f"(deadline was {deadline.isoformat()}, today is {today.isoformat()})."
            )
        elif (deadline - today).days <= 90:
            warnings.append(
                f"ITR-U deadline for AY {assessment_year} is approaching "
                f"({deadline.isoformat()}). File promptly."
            )

    # 4. Refund increase guard — warn if the original return already shows a refund.
    refund_due = float((state.submission_summary or {}).get("refund_due", 0) or 0)
    if refund_due > 0:
        warnings.append(
            f"The original return shows a refund of ₹{refund_due:,.0f}. "
            "ITR-U cannot be used to increase an existing refund. "
            "Ensure the updated return only corrects under-reported income."
        )

    eligible = len(blockers) == 0
    return {
        "eligible": eligible,
        "assessment_year": assessment_year,
        "ay_end_date": ay_end.isoformat() if ay_end else None,
        "deadline_date": _itr_u_deadline(ay_end).isoformat() if ay_end else None,
        "as_of_date": today.isoformat(),
        "submission_status": submission_status,
        "blockers": blockers,
        "warnings": warnings,
        "original_ack_no": (state.filing_artifacts or {}).get("ack_no"),
    }


def prepare_itr_u_escalation(
    state: AgentState,
    reason_code: str,
    reason_detail: str,
    *,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    """
    Build the escalation gate payload.  Returns eligibility plus a human-readable
    explanation of what ITR-U filing will entail and the mandatory CA confirmation
    requirement.
    """
    if reason_code not in VALID_REASON_CODES:
        raise ValueError(f"invalid_reason_code:{reason_code}")

    eligibility = check_itr_u_eligibility(state, as_of=as_of)

    reason_label = VALID_REASON_CODES[reason_code]
    tax_facts = state.tax_facts or {}

    explanation_lines = [
        "## ITR-U (Updated Return) — Escalation Gate",
        "",
        f"**Assessment Year**: {eligibility.get('assessment_year', 'Unknown')}",
        f"**Original Acknowledgement**: {eligibility.get('original_ack_no', 'Not recorded')}",
        f"**Reason for Update**: {reason_label}",
    ]
    if reason_detail:
        explanation_lines.append(f"**Detail**: {reason_detail}")

    explanation_lines += [
        "",
        "### What ITR-U filing means",
        "- You will pay additional tax (25% or 50% surcharge on incremental tax, depending on timing).",
        "- Once filed, the updated return cannot be withdrawn.",
        "- A new thread will be created with your corrected tax facts pre-loaded.",
        "",
        "### Eligibility",
        f"- Eligible: {'Yes' if eligibility['eligible'] else 'No'}",
    ]

    if eligibility["blockers"]:
        explanation_lines.append("- **Blockers**:")
        for b in eligibility["blockers"]:
            explanation_lines.append(f"  - {b}")

    if eligibility["warnings"]:
        explanation_lines.append("- **Warnings**:")
        for w in eligibility["warnings"]:
            explanation_lines.append(f"  - {w}")

    if eligibility.get("deadline_date"):
        explanation_lines.append(f"- Filing deadline: {eligibility['deadline_date']}")

    explanation_lines += [
        "",
        "### Required action",
        "A Chartered Accountant or authorised reviewer **must confirm** this escalation "
        "before the updated-return thread is created. Use `POST /api/filing/itr-u/confirm` "
        "once the taxpayer and their advisor have reviewed and agreed.",
    ]

    return {
        "thread_id": state.thread_id,
        "reason_code": reason_code,
        "reason_label": reason_label,
        "reason_detail": reason_detail,
        "eligibility": eligibility,
        "escalation_required": True,
        "escalation_md": "\n".join(explanation_lines),
        "valid_reason_codes": VALID_REASON_CODES,
    }


def build_itr_u_seed_facts(
    state: AgentState,
    reason_code: str,
    reason_detail: str,
) -> dict[str, Any]:
    """
    Return a copy of the base tax_facts augmented with ITR-U metadata.
    Used when creating the new revision thread.
    """
    facts = dict(state.tax_facts or {})
    facts["itr_u"] = {
        "base_thread_id": state.thread_id,
        "base_ack_no": (state.filing_artifacts or {}).get("ack_no"),
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "created_at": datetime.utcnow().isoformat(),
    }
    return facts
