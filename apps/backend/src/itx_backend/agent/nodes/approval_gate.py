"""
Approval gate node — Phase 3 & 4 requirement.

Hard stop requiring explicit user consent before:
1. Filling any portal field (Phase 3)
2. Submitting the return (Phase 4)

No fill/submit action is executed without a matching approval row.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import hashlib
import json

from ..state import AgentState


class ApprovalType(str, Enum):
    FILL_FIELD = "fill_field"        # Single field fill
    FILL_PAGE = "fill_page"          # All fields on a page
    FILL_PLAN = "fill_plan"          # Entire fill plan
    SUBMIT_DRAFT = "submit_draft"    # Save as draft
    SUBMIT_FINAL = "submit_final"    # Final submission
    EVERIFY = "everify"              # E-verification handoff


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"  # Replaced by newer approval request


@dataclass
class ApprovalRequest:
    """A request for user approval."""
    approval_id: str
    approval_type: ApprovalType
    thread_id: str
    user_id: str
    created_at: str
    expires_at: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    
    # What is being approved
    description: str = ""
    details: dict = field(default_factory=dict)
    
    # Actions that depend on this approval
    action_ids: list[str] = field(default_factory=list)
    
    # Consent text shown to user
    consent_text: str = ""
    
    # User response
    responded_at: Optional[str] = None
    response_hash: Optional[str] = None  # Hash of consent_text + response for audit


@dataclass
class ApprovalResponse:
    """User's response to an approval request."""
    approval_id: str
    approved: bool
    user_id: str
    responded_at: str
    consent_acknowledged: bool
    modifications: Optional[dict] = None  # Any user modifications to values
    rejection_reason: Optional[str] = None


# Consent text templates
CONSENT_TEXTS = {
    ApprovalType.FILL_FIELD: (
        "I authorize the agent to fill the field '{field_label}' with value '{value}' "
        "in the Income Tax portal. I understand this action will modify the form."
    ),
    ApprovalType.FILL_PAGE: (
        "I authorize the agent to fill {field_count} fields on the '{page_title}' page "
        "of the Income Tax portal. I have reviewed all values and confirm they are correct."
    ),
    ApprovalType.FILL_PLAN: (
        "I authorize the agent to fill {total_fields} fields across {page_count} pages "
        "as shown in the fill plan. I have reviewed all values and confirm they are correct."
    ),
    ApprovalType.SUBMIT_DRAFT: (
        "I authorize saving the current return as a draft. This does not submit the return "
        "to the Income Tax Department."
    ),
    ApprovalType.SUBMIT_FINAL: (
        "⚠️ FINAL SUBMISSION CONSENT\n\n"
        "I, the taxpayer, hereby confirm that:\n"
        "1. I have reviewed all information in this Income Tax Return\n"
        "2. All information is true, correct, and complete to the best of my knowledge\n"
        "3. I understand this will be submitted to the Income Tax Department\n"
        "4. I am aware that incorrect information may result in penalties\n\n"
        "Assessment Year: {assessment_year}\n"
        "Total Income: {total_income}\n"
        "Tax Payable/Refund: {tax_result}\n\n"
        "I authorize the submission of this return."
    ),
    ApprovalType.EVERIFY: (
        "I am ready to e-verify my Income Tax Return. The agent will guide me to the "
        "verification page, but I will complete the OTP/verification step myself."
    ),
}


def generate_approval_id(approval_type: ApprovalType, thread_id: str) -> str:
    """Generate unique approval ID."""
    ts = datetime.now(timezone.utc).isoformat()
    data = f"{approval_type.value}-{thread_id}-{ts}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def hash_consent_response(consent_text: str, approved: bool, user_id: str) -> str:
    """Create audit hash of consent interaction."""
    data = json.dumps({
        "consent_text": consent_text,
        "approved": approved,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def create_approval_request(
    approval_type: ApprovalType,
    thread_id: str,
    user_id: str,
    details: dict,
    action_ids: list[str],
    expiry_minutes: int = 30
) -> ApprovalRequest:
    """Create a new approval request."""
    now = datetime.now(timezone.utc)
    expires = datetime.fromtimestamp(
        now.timestamp() + expiry_minutes * 60, 
        tz=timezone.utc
    )
    
    # Build consent text from template
    template = CONSENT_TEXTS.get(approval_type, "I authorize this action.")
    consent_text = template.format(**details) if details else template
    
    # Build description
    descriptions = {
        ApprovalType.FILL_FIELD: f"Fill '{details.get('field_label', 'field')}'",
        ApprovalType.FILL_PAGE: f"Fill {details.get('field_count', 0)} fields on {details.get('page_title', 'page')}",
        ApprovalType.FILL_PLAN: f"Execute fill plan with {details.get('total_fields', 0)} fields",
        ApprovalType.SUBMIT_DRAFT: "Save return as draft",
        ApprovalType.SUBMIT_FINAL: "Submit final return to Income Tax Department",
        ApprovalType.EVERIFY: "Proceed to e-verification",
    }
    
    return ApprovalRequest(
        approval_id=generate_approval_id(approval_type, thread_id),
        approval_type=approval_type,
        thread_id=thread_id,
        user_id=user_id,
        created_at=now.isoformat(),
        expires_at=expires.isoformat(),
        description=descriptions.get(approval_type, "Approve action"),
        details=details,
        action_ids=action_ids,
        consent_text=consent_text,
    )


def process_approval_response(
    request: ApprovalRequest,
    response: ApprovalResponse
) -> ApprovalRequest:
    """Process user's response to approval request."""
    request.status = ApprovalStatus.APPROVED if response.approved else ApprovalStatus.REJECTED
    request.responded_at = response.responded_at
    request.response_hash = hash_consent_response(
        request.consent_text,
        response.approved,
        response.user_id
    )
    return request


async def approval_gate(state: AgentState) -> dict[str, Any]:
    """
    Approval gate node — creates approval requests and processes responses.
    
    Requirements:
    1. No fill action without prior approval
    2. No submission without explicit consent
    3. All approvals logged with hash for audit
    """
    thread_id = state.get("thread_id", "unknown")
    user_id = state.get("user_id", "unknown")
    fill_plan = state.get("fill_plan")
    pending_submission = state.get("pending_submission")
    user_response = state.get("last_user_response", {})
    
    # Check if we have a pending approval response
    if user_response.get("type") == "approval_response":
        approval_id = user_response.get("approval_id")
        approved = user_response.get("approved", False)
        
        # Find the pending approval
        pending_approvals = state.get("pending_approvals", [])
        for approval in pending_approvals:
            if approval.get("approval_id") == approval_id:
                response = ApprovalResponse(
                    approval_id=approval_id,
                    approved=approved,
                    user_id=user_id,
                    responded_at=datetime.now(timezone.utc).isoformat(),
                    consent_acknowledged=user_response.get("consent_acknowledged", False),
                    modifications=user_response.get("modifications"),
                    rejection_reason=user_response.get("rejection_reason"),
                )
                
                if approved:
                    message = f"✅ Approval granted for: {approval.get('description')}"
                    return {
                        "messages": state.get("messages", []) + [{
                            "role": "assistant",
                            "content": message,
                            "metadata": {"node": "approval_gate", "approved": True}
                        }],
                        "approved_actions": approval.get("action_ids", []),
                        "approval_status": "approved",
                        "response_hash": hash_consent_response(
                            approval.get("consent_text", ""),
                            True,
                            user_id
                        )
                    }
                else:
                    message = f"❌ Approval denied for: {approval.get('description')}"
                    if response.rejection_reason:
                        message += f"\nReason: {response.rejection_reason}"
                    return {
                        "messages": state.get("messages", []) + [{
                            "role": "assistant",
                            "content": message,
                            "metadata": {"node": "approval_gate", "approved": False}
                        }],
                        "approval_status": "rejected",
                        "rejection_reason": response.rejection_reason
                    }
    
    # Create new approval request based on context
    if pending_submission:
        # Submission approval (Phase 4)
        approval_type = (
            ApprovalType.SUBMIT_FINAL 
            if pending_submission.get("is_final") 
            else ApprovalType.SUBMIT_DRAFT
        )
        details = {
            "assessment_year": pending_submission.get("assessment_year", "2025-26"),
            "total_income": f"₹{pending_submission.get('total_income', 0):,.2f}",
            "tax_result": pending_submission.get("tax_result", "Calculating..."),
        }
        action_ids = ["submit"]
        
    elif fill_plan and fill_plan.get("total_actions", 0) > 0:
        # Fill plan approval (Phase 3)
        approval_type = ApprovalType.FILL_PLAN
        details = {
            "total_fields": fill_plan.get("total_actions", 0),
            "page_count": len(fill_plan.get("pages", [])),
        }
        action_ids = [
            action["action_id"]
            for page in fill_plan.get("pages", [])
            for action in page.get("actions", [])
        ]
    else:
        # Nothing to approve
        return {
            "messages": state.get("messages", []),
            "approval_status": "no_action_needed"
        }
    
    # Create the approval request
    request = create_approval_request(
        approval_type=approval_type,
        thread_id=thread_id,
        user_id=user_id,
        details=details,
        action_ids=action_ids,
    )
    
    # Build approval UI message
    message_parts = [
        f"## 🔐 Approval Required\n",
        f"**{request.description}**\n",
        f"\n{request.consent_text}\n",
        f"\n---\n",
        f"**Approval ID:** `{request.approval_id}`\n",
        f"**Expires:** {request.expires_at}\n",
        f"\n_Please review and click Approve or Reject._"
    ]
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": "\n".join(message_parts),
        "metadata": {
            "node": "approval_gate",
            "approval_id": request.approval_id,
            "requires_response": True
        }
    })
    
    return {
        "messages": messages,
        "pending_approvals": state.get("pending_approvals", []) + [{
            "approval_id": request.approval_id,
            "approval_type": request.approval_type.value,
            "description": request.description,
            "consent_text": request.consent_text,
            "action_ids": request.action_ids,
            "created_at": request.created_at,
            "expires_at": request.expires_at,
        }],
        "awaiting_approval": True,
        "current_approval_id": request.approval_id,
    }


# Legacy interface
def run(state: AgentState) -> AgentState:
    import asyncio
    result = asyncio.run(approval_gate(state))
    state.apply_update(result)
    return state
