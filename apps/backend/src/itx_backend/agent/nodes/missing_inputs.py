"""
Missing-input engine — Phase 2 requirement.

Turns unresolved facts into a prioritized question list.
Generates smart questions based on what's missing and what we have.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import hashlib

from ..state import AgentState


class QuestionPriority(str, Enum):
    CRITICAL = "critical"     # Blocks filing
    HIGH = "high"             # Important for accurate filing
    MEDIUM = "medium"         # Nice to have
    LOW = "low"               # Optional


class QuestionType(str, Enum):
    YES_NO = "yes_no"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    FILE_UPLOAD = "file_upload"
    CONFIRMATION = "confirmation"


@dataclass
class QuestionOption:
    """An option for choice-type questions."""
    value: str
    label: str
    description: Optional[str] = None
    recommended: bool = False


@dataclass
class MissingInputQuestion:
    """A question to resolve a missing input."""
    question_id: str
    priority: QuestionPriority
    question_type: QuestionType
    
    # Question content
    title: str
    description: str
    help_text: Optional[str] = None
    
    # For choice questions
    options: list[QuestionOption] = field(default_factory=list)
    
    # Validation
    required: bool = True
    validation_pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    # Context
    related_field: str = ""
    related_documents: list[str] = field(default_factory=list)
    
    # Prefill hint
    prefill_value: Optional[str] = None
    prefill_source: Optional[str] = None


# Question templates for common missing inputs
QUESTION_TEMPLATES = {
    "regime_choice": MissingInputQuestion(
        question_id="regime_choice",
        priority=QuestionPriority.CRITICAL,
        question_type=QuestionType.SINGLE_CHOICE,
        title="Which tax regime do you want to use?",
        description="Choose between Old and New tax regimes for this filing.",
        help_text="Old regime allows deductions (80C, 80D, HRA) but has lower slabs. New regime has higher basic exemption but fewer deductions.",
        options=[
            QuestionOption("new", "New Regime", "Higher exemption, simpler, no deductions", recommended=True),
            QuestionOption("old", "Old Regime", "Lower rates with deductions like 80C, 80D, HRA"),
        ],
        related_field="regime",
    ),
    "residential_status": MissingInputQuestion(
        question_id="residential_status",
        priority=QuestionPriority.CRITICAL,
        question_type=QuestionType.SINGLE_CHOICE,
        title="What is your residential status for this financial year?",
        description="This determines how your income is taxed.",
        options=[
            QuestionOption("resident", "Resident", "Stayed in India 182+ days", recommended=True),
            QuestionOption("rnor", "Resident but Not Ordinarily Resident (RNOR)", "NRI status in 9 of 10 preceding years"),
            QuestionOption("non_resident", "Non-Resident (NRI)", "Stayed in India < 182 days"),
        ],
        related_field="residential_status",
    ),
    "bank_account": MissingInputQuestion(
        question_id="bank_account",
        priority=QuestionPriority.CRITICAL,
        question_type=QuestionType.TEXT,
        title="Which bank account should receive your refund?",
        description="Provide your bank account details for refund credit.",
        help_text="Use a pre-validated bank account linked to your PAN for faster refund.",
        related_field="bank.account_number",
    ),
    "employer_details": MissingInputQuestion(
        question_id="employer_details",
        priority=QuestionPriority.HIGH,
        question_type=QuestionType.FILE_UPLOAD,
        title="Please upload your Form 16",
        description="Form 16 contains your salary details and TDS information from your employer.",
        help_text="You can get Form 16 from your employer's HR department.",
        related_field="salary",
        related_documents=["form16"],
    ),
    "hra_details": MissingInputQuestion(
        question_id="hra_details",
        priority=QuestionPriority.MEDIUM,
        question_type=QuestionType.YES_NO,
        title="Are you claiming HRA exemption?",
        description="If you pay rent and receive HRA, you may be eligible for exemption.",
        help_text="You'll need rent receipts and landlord's PAN (if rent > ₹1 lakh/year).",
        related_field="exemptions.hra",
    ),
    "rent_paid": MissingInputQuestion(
        question_id="rent_paid",
        priority=QuestionPriority.MEDIUM,
        question_type=QuestionType.NUMBER,
        title="How much rent did you pay this financial year?",
        description="Enter total rent paid during April to March.",
        min_value=0,
        related_field="rent_details.annual_rent",
    ),
    "investment_80c": MissingInputQuestion(
        question_id="investment_80c",
        priority=QuestionPriority.MEDIUM,
        question_type=QuestionType.NUMBER,
        title="What is your total 80C investment?",
        description="Include PPF, ELSS, LIC, tuition fees, home loan principal, etc.",
        help_text="Maximum limit is ₹1,50,000.",
        max_value=150000,
        related_field="deductions.80c.total",
    ),
    "health_insurance": MissingInputQuestion(
        question_id="health_insurance",
        priority=QuestionPriority.MEDIUM,
        question_type=QuestionType.NUMBER,
        title="How much health insurance premium did you pay?",
        description="Include premiums for self, spouse, children, and parents.",
        help_text="Limit: ₹25,000 (self/family) + ₹25,000-50,000 (parents based on age).",
        related_field="deductions.80d",
    ),
    "capital_gains": MissingInputQuestion(
        question_id="capital_gains",
        priority=QuestionPriority.HIGH,
        question_type=QuestionType.YES_NO,
        title="Did you sell any shares, mutual funds, or property this year?",
        description="If yes, you'll need to report capital gains.",
        help_text="This may change your ITR form from ITR-1 to ITR-2.",
        related_field="capital_gains",
    ),
    "foreign_assets": MissingInputQuestion(
        question_id="foreign_assets",
        priority=QuestionPriority.HIGH,
        question_type=QuestionType.YES_NO,
        title="Do you have any foreign bank accounts or assets?",
        description="This includes foreign bank accounts, shares in foreign companies, or immovable property abroad.",
        help_text="If yes, you must file ITR-2 or higher and declare in Schedule FA.",
        related_field="foreign_assets",
    ),
    "directorship": MissingInputQuestion(
        question_id="directorship",
        priority=QuestionPriority.HIGH,
        question_type=QuestionType.YES_NO,
        title="Are you a director in any company?",
        description="This includes private or public limited companies.",
        help_text="If yes, you must file ITR-2 or higher.",
        related_field="directorship",
    ),
    "ais_mismatch_salary": MissingInputQuestion(
        question_id="ais_mismatch_salary",
        priority=QuestionPriority.HIGH,
        question_type=QuestionType.CONFIRMATION,
        title="Salary amount doesn't match AIS",
        description="Your Form 16 shows {form16_value} but AIS shows {ais_value}. Which is correct?",
        options=[
            QuestionOption("form16", "Use Form 16 value", "My Form 16 is correct"),
            QuestionOption("ais", "Use AIS value", "AIS reflects correct salary"),
            QuestionOption("custom", "Enter different amount", "Both are incorrect"),
        ],
        related_field="salary.gross",
    ),
}


def generate_question_id(field: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return hashlib.sha256(f"{field}-{ts}".encode()).hexdigest()[:12]


def identify_missing_inputs(
    tax_facts: dict,
    reconciliation: dict,
    documents: list,
    itr_type: str
) -> list[MissingInputQuestion]:
    """Identify what inputs are missing and generate questions."""
    questions = []
    
    # Check regime choice
    if not tax_facts.get("regime"):
        questions.append(QUESTION_TEMPLATES["regime_choice"])
    
    # Check residential status
    if not tax_facts.get("residential_status"):
        questions.append(QUESTION_TEMPLATES["residential_status"])
    
    # Check bank account
    if not tax_facts.get("bank", {}).get("account_number"):
        questions.append(QUESTION_TEMPLATES["bank_account"])
    
    # Check if Form 16 is uploaded
    doc_types = {d.get("type") for d in documents}
    if "form16" not in doc_types and tax_facts.get("has_salary_income", True):
        questions.append(QUESTION_TEMPLATES["employer_details"])
    
    # Check capital gains for ITR type determination
    if itr_type == "ITR-1" and "capital_gains" not in tax_facts:
        questions.append(QUESTION_TEMPLATES["capital_gains"])
    
    # Check foreign assets
    if "foreign_assets" not in tax_facts:
        questions.append(QUESTION_TEMPLATES["foreign_assets"])
    
    # Check directorship
    if "directorship" not in tax_facts:
        questions.append(QUESTION_TEMPLATES["directorship"])
    
    # Add mismatch resolution questions
    for mismatch in reconciliation.get("mismatches", []):
        if mismatch.get("severity") in ["warning", "error"]:
            field = mismatch.get("field", "")
            template_key = f"ais_mismatch_{field.split('.')[0]}"
            if template_key in QUESTION_TEMPLATES:
                q = QUESTION_TEMPLATES[template_key]
                # Substitute actual values
                q.description = q.description.format(
                    form16_value=mismatch.get("doc_value", "N/A"),
                    ais_value=mismatch.get("ais_value", "N/A")
                )
                questions.append(q)
    
    # Sort by priority
    priority_order = {
        QuestionPriority.CRITICAL: 0,
        QuestionPriority.HIGH: 1,
        QuestionPriority.MEDIUM: 2,
        QuestionPriority.LOW: 3,
    }
    questions.sort(key=lambda q: priority_order[q.priority])
    
    return questions


def format_question_for_display(q: MissingInputQuestion) -> str:
    """Format a question for chat display."""
    lines = [f"### {q.title}\n", f"{q.description}\n"]
    
    if q.help_text:
        lines.append(f"\n💡 *{q.help_text}*\n")
    
    if q.question_type == QuestionType.SINGLE_CHOICE and q.options:
        lines.append("\n**Options:**\n")
        for opt in q.options:
            rec = " ⭐" if opt.recommended else ""
            desc = f" — {opt.description}" if opt.description else ""
            lines.append(f"- **{opt.label}**{desc}{rec}\n")
    elif q.question_type == QuestionType.YES_NO:
        lines.append("\n**Please answer:** Yes or No\n")
    elif q.question_type == QuestionType.NUMBER:
        constraints = []
        if q.min_value is not None:
            constraints.append(f"min: ₹{q.min_value:,.0f}")
        if q.max_value is not None:
            constraints.append(f"max: ₹{q.max_value:,.0f}")
        if constraints:
            lines.append(f"\n*Constraints: {', '.join(constraints)}*\n")
    elif q.question_type == QuestionType.FILE_UPLOAD:
        lines.append("\n📎 **Please upload the document**\n")
    
    return "".join(lines)


async def missing_inputs(state: AgentState) -> dict[str, Any]:
    """
    Missing-input engine — identifies gaps and generates questions.
    
    Phase 2 requirement:
    - Turn unresolved facts into prioritized questions
    - Smart follow-up based on answers
    """
    tax_facts = state.get("tax_facts", {})
    reconciliation = state.get("reconciliation", {})
    documents = state.get("documents", [])
    itr_type = state.get("itr_type", "ITR-1")
    answered_questions = state.get("answered_questions", set())
    
    # Identify missing inputs
    all_questions = identify_missing_inputs(tax_facts, reconciliation, documents, itr_type)
    
    # Filter out already answered questions
    pending_questions = [
        q for q in all_questions 
        if q.question_id not in answered_questions
    ]
    
    if not pending_questions:
        messages = state.get("messages", [])
        messages.append({
            "role": "assistant",
            "content": "✅ All required information has been collected. Ready to proceed!",
            "metadata": {"node": "missing_inputs", "all_complete": True}
        })
        return {
            "messages": messages,
            "missing_inputs_complete": True
        }
    
    # Get the next question to ask
    next_question = pending_questions[0]
    remaining_count = len(pending_questions) - 1
    
    # Build message
    message_parts = [
        f"## 📝 Information Needed\n",
        f"*{remaining_count} more questions after this*\n\n",
        format_question_for_display(next_question),
    ]
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": "".join(message_parts),
        "metadata": {
            "node": "missing_inputs",
            "question_id": next_question.question_id,
            "question_type": next_question.question_type.value,
            "priority": next_question.priority.value,
            "options": [
                {"value": o.value, "label": o.label, "recommended": o.recommended}
                for o in next_question.options
            ] if next_question.options else None,
            "related_field": next_question.related_field,
            "remaining_questions": remaining_count,
        }
    })
    
    return {
        "messages": messages,
        "current_question": {
            "id": next_question.question_id,
            "type": next_question.question_type.value,
            "field": next_question.related_field,
            "required": next_question.required,
        },
        "pending_questions": [
            {"id": q.question_id, "priority": q.priority.value, "title": q.title}
            for q in pending_questions
        ],
        "awaiting_user_response": True,
    }


# Legacy interface
def run(state: AgentState) -> AgentState:
    import asyncio
    result = asyncio.run(missing_inputs(state))
    state.apply_update(result)
    return state
