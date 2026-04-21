"""
Fill-plan generator node — Phase 3 requirement.

Diffs between canonical tax facts and current portal state;
Generates batched fill plans by page.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timezone
import hashlib

from ..state import AgentState


class FillActionType(str, Enum):
    FILL_TEXT = "fill_text"
    SELECT_OPTION = "select_option"
    CHECK_BOX = "check_box"
    CLICK_RADIO = "click_radio"
    UPLOAD_FILE = "upload_file"


class FillConfidence(str, Enum):
    HIGH = "high"       # >= 0.9, auto-fillable with one-click approval
    MEDIUM = "medium"   # 0.7-0.9, needs user review
    LOW = "low"         # < 0.7, requires explicit confirmation


@dataclass
class FillAction:
    """A single field fill action."""
    action_id: str
    action_type: FillActionType
    field_id: str
    field_label: str
    selector: str
    value: Any
    formatted_value: str
    source_fact_id: str
    source_document: Optional[str]
    confidence: float
    confidence_level: FillConfidence
    requires_approval: bool = True
    approval_status: str = "pending"  # pending, approved, rejected, skipped
    

@dataclass
class PageFillPlan:
    """Fill plan for a single portal page."""
    page_type: str
    page_title: str
    actions: list[FillAction] = field(default_factory=list)
    total_fields: int = 0
    fillable_fields: int = 0
    already_filled: int = 0
    requires_navigation: bool = False
    navigation_steps: list[str] = field(default_factory=list)


@dataclass
class FillPlanResult:
    """Complete fill plan across all pages."""
    plan_id: str
    created_at: str
    pages: list[PageFillPlan] = field(default_factory=list)
    total_actions: int = 0
    high_confidence_actions: int = 0
    low_confidence_actions: int = 0
    estimated_time_seconds: int = 0


# Field mappings from tax facts to portal fields
FIELD_MAPPINGS = {
    "salary-schedule": {
        "gross_salary": {"selector": "#grossSalary", "label": "Gross Salary"},
        "employer_name": {"selector": "#employerName", "label": "Name of Employer"},
        "employer_tan": {"selector": "#employerTAN", "label": "TAN of Employer"},
        "allowances.hra": {"selector": "#hraReceived", "label": "HRA Received"},
        "allowances.lta": {"selector": "#ltaReceived", "label": "LTA Received"},
        "perquisites": {"selector": "#perquisites", "label": "Value of Perquisites"},
        "standard_deduction": {"selector": "#standardDeduction", "label": "Standard Deduction"},
    },
    "deductions-vi-a": {
        "deductions.80c": {"selector": "#sec80C", "label": "Section 80C"},
        "deductions.80ccd_1b": {"selector": "#sec80CCD1B", "label": "Section 80CCD(1B) - NPS"},
        "deductions.80d": {"selector": "#sec80DSelf", "label": "80D - Self & Family"},
        "deductions.80d_parents": {"selector": "#sec80DParents", "label": "80D - Parents"},
        "deductions.80e": {"selector": "#sec80E", "label": "Section 80E - Education Loan"},
        "deductions.80g": {"selector": "#sec80G", "label": "Section 80G - Donations"},
        "deductions.80tta": {"selector": "#sec80TTA", "label": "Section 80TTA"},
    },
    "personal-info": {
        "name": {"selector": "#fullName", "label": "Full Name"},
        "pan": {"selector": "#pan", "label": "PAN"},
        "dob": {"selector": "#dob", "label": "Date of Birth"},
        "father_name": {"selector": "#fatherName", "label": "Father's Name"},
        "mobile": {"selector": "#mobile", "label": "Mobile Number"},
        "email": {"selector": "#email", "label": "Email Address"},
    },
    "bank-account": {
        "bank.name": {"selector": "#bankName", "label": "Bank Name"},
        "bank.account_number": {"selector": "#accountNumber", "label": "Account Number"},
        "bank.ifsc": {"selector": "#ifscCode", "label": "IFSC Code"},
        "bank.account_type": {"selector": "#accountType", "label": "Account Type"},
    },
    "tax-paid": {
        "tax_paid.tds_salary": {"selector": "#tdsSalary", "label": "TDS on Salary"},
        "tax_paid.tds_other": {"selector": "#tdsOther", "label": "TDS on Other Income"},
        "tax_paid.advance_tax": {"selector": "#advanceTax", "label": "Advance Tax Paid"},
        "tax_paid.self_assessment_tax": {"selector": "#selfAssessmentTax", "label": "Self Assessment Tax"},
    },
    "capital-gains": {
        "capital_gains.stcg": {"selector": "#stcgEquity", "label": "STCG on Listed Equity"},
        "capital_gains.ltcg": {"selector": "#ltcgEquity", "label": "LTCG on Listed Equity"},
    },
    "house-property": {
        "house_property.gross_rent": {"selector": "#rentalIncome", "label": "Annual Rental Income"},
        "house_property.municipal_tax": {"selector": "#municipalTax", "label": "Municipal Taxes Paid"},
        "house_property.loan_interest": {"selector": "#homeLoanInterest", "label": "Home Loan Interest"},
    },
}


def get_nested_value(data: dict, key_path: str) -> Any:
    """Get value from nested dict using dot notation."""
    keys = key_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def format_currency(value: float) -> str:
    """Format value as Indian currency."""
    if value >= 10000000:  # crore
        return f"₹{value/10000000:.2f} Cr"
    elif value >= 100000:  # lakh
        return f"₹{value/100000:.2f} L"
    else:
        return f"₹{value:,.2f}"


def generate_action_id() -> str:
    """Generate unique action ID."""
    ts = datetime.now(timezone.utc).isoformat()
    return hashlib.sha256(ts.encode()).hexdigest()[:12]


def get_confidence_level(confidence: float) -> FillConfidence:
    if confidence >= 0.9:
        return FillConfidence.HIGH
    elif confidence >= 0.7:
        return FillConfidence.MEDIUM
    return FillConfidence.LOW


def diff_portal_state(
    tax_facts: dict,
    portal_fields: dict,
    fact_evidence: dict,
    page_type: str
) -> list[FillAction]:
    """
    Compare tax facts against current portal state.
    Returns list of fill actions needed.
    """
    actions = []
    field_mappings = FIELD_MAPPINGS.get(page_type, {})
    
    for fact_key, field_config in field_mappings.items():
        # Get value from tax facts
        fact_value = get_nested_value(tax_facts, fact_key)
        if fact_value is None:
            continue
        
        # Get current portal value
        portal_value = portal_fields.get(field_config["selector"], {}).get("value")
        
        # Skip if already filled with same value
        if portal_value is not None and str(portal_value) == str(fact_value):
            continue
        
        # Get evidence for confidence
        evidence = fact_evidence.get(fact_key, {})
        confidence = evidence.get("confidence", 0.8)
        source_doc = evidence.get("source_document")
        
        # Format value for display
        if isinstance(fact_value, (int, float)) and fact_key not in ["pan", "mobile", "ifsc"]:
            formatted = format_currency(fact_value)
        else:
            formatted = str(fact_value)
        
        # Determine action type
        action_type = FillActionType.FILL_TEXT
        if "account_type" in fact_key or "type" in fact_key:
            action_type = FillActionType.SELECT_OPTION
        
        actions.append(FillAction(
            action_id=generate_action_id(),
            action_type=action_type,
            field_id=fact_key,
            field_label=field_config["label"],
            selector=field_config["selector"],
            value=fact_value,
            formatted_value=formatted,
            source_fact_id=fact_key,
            source_document=source_doc,
            confidence=confidence,
            confidence_level=get_confidence_level(confidence),
            requires_approval=confidence < 0.9,
        ))
    
    return actions


async def fill_plan(state: AgentState) -> dict[str, Any]:
    """
    Generate a fill plan by diffing tax facts against portal state.
    
    Phase 3 requirement:
    - Diff between canonical facts and current portal state
    - Batched by page
    - Each action has confidence and approval requirement
    """
    current_page = state.get("current_page", "unknown")
    tax_facts = state.get("tax_facts", {})
    portal_state = state.get("portal_state", {})
    portal_fields = portal_state.get("fields", {})
    fact_evidence = state.get("fact_evidence", {})
    
    # Generate plan ID
    plan_id = hashlib.sha256(
        f"{datetime.now(timezone.utc).isoformat()}-{current_page}".encode()
    ).hexdigest()[:16]
    
    pages_to_fill = []
    
    # If on a specific page, generate plan for that page
    if current_page in FIELD_MAPPINGS:
        actions = diff_portal_state(tax_facts, portal_fields, fact_evidence, current_page)
        if actions:
            pages_to_fill.append(PageFillPlan(
                page_type=current_page,
                page_title=current_page.replace("-", " ").title(),
                actions=actions,
                total_fields=len(FIELD_MAPPINGS[current_page]),
                fillable_fields=len(actions),
                already_filled=len(FIELD_MAPPINGS[current_page]) - len(actions),
            ))
    else:
        # Generate plan for all pages
        for page_type in FIELD_MAPPINGS.keys():
            actions = diff_portal_state(tax_facts, {}, fact_evidence, page_type)
            if actions:
                pages_to_fill.append(PageFillPlan(
                    page_type=page_type,
                    page_title=page_type.replace("-", " ").title(),
                    actions=actions,
                    total_fields=len(FIELD_MAPPINGS[page_type]),
                    fillable_fields=len(actions),
                    requires_navigation=page_type != current_page,
                ))
    
    # Calculate totals
    total_actions = sum(len(p.actions) for p in pages_to_fill)
    high_conf = sum(
        1 for p in pages_to_fill 
        for a in p.actions 
        if a.confidence_level == FillConfidence.HIGH
    )
    low_conf = sum(
        1 for p in pages_to_fill 
        for a in p.actions 
        if a.confidence_level == FillConfidence.LOW
    )
    
    fill_plan_result = FillPlanResult(
        plan_id=plan_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        pages=pages_to_fill,
        total_actions=total_actions,
        high_confidence_actions=high_conf,
        low_confidence_actions=low_conf,
        estimated_time_seconds=total_actions * 2,  # ~2 seconds per field
    )
    
    # Build user message
    if total_actions == 0:
        message = "✅ All fields are already filled correctly. Nothing to update."
    else:
        message_parts = [
            f"## Fill Plan Generated\n",
            f"**Plan ID:** `{plan_id}`\n",
            f"**Total actions:** {total_actions} fields to fill\n",
            f"- 🟢 High confidence: {high_conf}\n",
            f"- 🟡 Medium confidence: {total_actions - high_conf - low_conf}\n",
            f"- 🔴 Low confidence: {low_conf}\n",
        ]
        
        for page in pages_to_fill:
            message_parts.append(f"\n### {page.page_title}")
            for action in page.actions:
                conf_icon = "🟢" if action.confidence_level == FillConfidence.HIGH else "🟡" if action.confidence_level == FillConfidence.MEDIUM else "🔴"
                message_parts.append(
                    f"- {conf_icon} **{action.field_label}**: {action.formatted_value}"
                )
        
        message_parts.append("\n**Review the plan and approve to proceed with filling.**")
        message = "\n".join(message_parts)
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": message,
        "metadata": {
            "node": "fill_plan",
            "plan_id": plan_id,
            "total_actions": total_actions
        }
    })
    
    return {
        "messages": messages,
        "fill_plan": {
            "plan_id": fill_plan_result.plan_id,
            "created_at": fill_plan_result.created_at,
            "total_actions": fill_plan_result.total_actions,
            "high_confidence_actions": fill_plan_result.high_confidence_actions,
            "low_confidence_actions": fill_plan_result.low_confidence_actions,
            "pages": [
                {
                    "page_type": p.page_type,
                    "page_title": p.page_title,
                    "actions": [
                        {
                            "action_id": a.action_id,
                            "field_label": a.field_label,
                            "selector": a.selector,
                            "value": a.value,
                            "formatted_value": a.formatted_value,
                            "confidence": a.confidence,
                            "confidence_level": a.confidence_level.value,
                            "requires_approval": a.requires_approval,
                            "source_document": a.source_document,
                        }
                        for a in p.actions
                    ]
                }
                for p in pages_to_fill
            ]
        },
        "awaiting_approval": total_actions > 0
    }


# Legacy interface
async def run(state: AgentState) -> AgentState:
    result = await fill_plan(state)
    state.apply_update(result)
    return state
