"""
E-verification handoff node — Phase 4 requirement.

Guides user to e-verification but NEVER automates OTP entry.
Branches for: Aadhaar OTP, EVC, Net Banking, DSC.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ..state import AgentState


class EVerifyMethod(str, Enum):
    AADHAAR_OTP = "aadhaar_otp"
    NET_BANKING = "net_banking"
    BANK_ATM = "bank_atm"
    DEMAT = "demat"
    DSC = "dsc"  # Digital Signature Certificate
    PHYSICAL_ITRV = "physical"  # Send signed ITR-V by post


class HandoffStatus(str, Enum):
    PENDING = "pending"
    USER_IN_CONTROL = "user_in_control"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class EVerifyHandoff:
    """E-verification handoff state."""
    handoff_id: str
    method: EVerifyMethod
    status: HandoffStatus
    created_at: str
    
    # Navigation info
    target_url: str
    navigation_steps: list[str]
    
    # User guidance
    user_instructions: str
    security_notice: str
    
    # Completion
    completed_at: Optional[str] = None
    itrv_acknowledgement: Optional[str] = None


VERIFICATION_METHODS = {
    EVerifyMethod.AADHAAR_OTP: {
        "name": "Aadhaar OTP",
        "icon": "🔐",
        "description": "Verify using OTP sent to your Aadhaar-linked mobile number",
        "requirements": [
            "Mobile number linked to Aadhaar",
            "Access to linked mobile for OTP"
        ],
        "time": "~2 minutes",
        "steps": [
            "I'll navigate you to the e-verify page",
            "Select 'I would like to e-verify using Aadhaar OTP'",
            "Click 'Generate Aadhaar OTP'",
            "Enter the 6-digit OTP from your mobile",
            "Click 'Validate'"
        ],
        "security_notice": (
            "⚠️ **Security Notice**: I will NOT ask for or enter your OTP. "
            "You must enter it yourself. Never share your OTP with anyone."
        )
    },
    EVerifyMethod.NET_BANKING: {
        "name": "Net Banking",
        "icon": "🏦",
        "description": "Verify through your bank's net banking portal",
        "requirements": [
            "Net banking enabled with a pre-validated bank",
            "Bank account linked to PAN"
        ],
        "time": "~5 minutes",
        "steps": [
            "I'll navigate you to the e-verify page",
            "Select 'Through Net Banking'",
            "Choose your bank from the list",
            "You'll be redirected to your bank's login page",
            "Log in and authorize the verification",
            "You'll be redirected back to the ITR portal"
        ],
        "security_notice": (
            "⚠️ **Security Notice**: You will be redirected to your bank's website. "
            "Verify the URL before entering credentials. I cannot see your bank login."
        )
    },
    EVerifyMethod.BANK_ATM: {
        "name": "Bank ATM",
        "icon": "🏧",
        "description": "Generate EVC at your bank's ATM",
        "requirements": [
            "Debit card of a bank linked to PAN",
            "Access to the bank's ATM"
        ],
        "time": "~10 minutes",
        "steps": [
            "Visit your bank's ATM",
            "Insert your debit card",
            "Select 'Generate EVC for Income Tax Filing'",
            "EVC will be sent to your registered mobile",
            "Come back here and enter the EVC"
        ],
        "security_notice": (
            "⚠️ **Security Notice**: The EVC is valid for 72 hours. "
            "Keep it confidential until you verify your return."
        )
    },
    EVerifyMethod.DEMAT: {
        "name": "Demat Account",
        "icon": "📈",
        "description": "Verify through your demat account",
        "requirements": [
            "Demat account with NSDL/CDSL",
            "Account linked to PAN"
        ],
        "time": "~5 minutes",
        "steps": [
            "I'll navigate you to the e-verify page",
            "Select 'Through Demat Account'",
            "Choose your depository (NSDL/CDSL)",
            "Log in to your demat account",
            "Authorize the verification"
        ],
        "security_notice": (
            "⚠️ **Security Notice**: You will be redirected to your depository's website. "
            "I cannot see your demat login credentials."
        )
    },
    EVerifyMethod.DSC: {
        "name": "Digital Signature Certificate",
        "icon": "✍️",
        "description": "Sign using your registered DSC",
        "requirements": [
            "Valid Class 2 or Class 3 DSC",
            "DSC registered on the ITR portal",
            "DSC dongle and driver installed"
        ],
        "time": "~3 minutes",
        "steps": [
            "Ensure your DSC dongle is connected",
            "I'll navigate you to the e-verify page",
            "Select 'I already have a Digital Signature Certificate'",
            "Enter your DSC password",
            "Click 'Sign'"
        ],
        "security_notice": (
            "⚠️ **Security Notice**: Never share your DSC password. "
            "Ensure your DSC software is from a trusted source."
        )
    },
    EVerifyMethod.PHYSICAL_ITRV: {
        "name": "Send Signed ITR-V by Post",
        "icon": "📮",
        "description": "Print, sign, and mail ITR-V to CPC Bengaluru",
        "requirements": [
            "Printer",
            "Blue ink pen for signature",
            "Envelope and postal service"
        ],
        "time": "120 days deadline",
        "steps": [
            "Download ITR-V from the portal",
            "Print on A4 paper",
            "Sign in blue ink in the designated area",
            "Do NOT fold the signed ITR-V",
            "Send by ordinary/speed post to CPC Bengaluru",
            "Address: CPC, Income Tax Department, Bengaluru 560500"
        ],
        "security_notice": (
            "⚠️ **Important**: The ITR-V must reach CPC within 120 days of filing. "
            "Your return is NOT valid until ITR-V is received and processed."
        )
    },
}


def generate_handoff_id() -> str:
    """Generate unique handoff ID."""
    import hashlib
    ts = datetime.now(timezone.utc).isoformat()
    return f"ev-{hashlib.sha256(ts.encode()).hexdigest()[:8]}"


async def everify_handoff(state: AgentState) -> dict[str, Any]:
    """
    E-verification handoff node.
    
    Phase 4 requirement:
    - Guide user to verification
    - NEVER automate OTP entry
    - Support all verification methods
    """
    user_choice = state.get("everify_method")
    submission_summary = state.get("submission_summary", {})
    
    # If user hasn't chosen a method, present options
    if not user_choice:
        message_parts = [
            "## 🔐 E-Verification Required\n",
            "Your return has been submitted successfully. Now you need to verify it.\n",
            "\n### Choose a verification method:\n",
        ]
        
        # Recommended first
        message_parts.append("\n**Recommended:**\n")
        method_info = VERIFICATION_METHODS[EVerifyMethod.AADHAAR_OTP]
        message_parts.append(
            f"- {method_info['icon']} **{method_info['name']}** — {method_info['description']} "
            f"({method_info['time']})\n"
        )
        
        message_parts.append("\n**Other options:**\n")
        for method, info in VERIFICATION_METHODS.items():
            if method != EVerifyMethod.AADHAAR_OTP:
                message_parts.append(
                    f"- {info['icon']} **{info['name']}** — {info['description']} "
                    f"({info['time']})\n"
                )
        
        message_parts.append("\n_Select a method to continue._")
        
        messages = state.get("messages", [])
        messages.append({
            "role": "assistant",
            "content": "".join(message_parts),
            "metadata": {
                "node": "everify_handoff",
                "awaiting_selection": True,
                "options": [m.value for m in EVerifyMethod]
            }
        })
        
        return {
            "messages": messages,
            "awaiting_everify_selection": True
        }
    
    # User has selected a method
    try:
        method = EVerifyMethod(user_choice)
    except ValueError:
        messages = state.get("messages", [])
        messages.append({
            "role": "assistant",
            "content": f"❌ Invalid verification method: {user_choice}. Please select a valid option.",
            "metadata": {"node": "everify_handoff", "error": True}
        })
        return {"messages": messages}
    
    method_info = VERIFICATION_METHODS[method]
    handoff = EVerifyHandoff(
        handoff_id=generate_handoff_id(),
        method=method,
        status=HandoffStatus.USER_IN_CONTROL,
        created_at=datetime.now(timezone.utc).isoformat(),
        target_url="https://eportal.incometax.gov.in/iec/foservices/#/e-verify",
        navigation_steps=method_info["steps"],
        user_instructions="\n".join(method_info["steps"]),
        security_notice=method_info["security_notice"]
    )
    
    # Build guidance message
    message_parts = [
        f"## {method_info['icon']} {method_info['name']}\n",
        f"\n**Requirements:**\n",
    ]
    for req in method_info["requirements"]:
        message_parts.append(f"- {req}\n")
    
    message_parts.append(f"\n**Steps to complete:**\n")
    for i, step in enumerate(method_info["steps"], 1):
        message_parts.append(f"{i}. {step}\n")
    
    message_parts.append(f"\n---\n")
    message_parts.append(f"{method_info['security_notice']}\n")
    message_parts.append(f"\n---\n")
    message_parts.append(f"**Handoff ID:** `{handoff.handoff_id}`\n")
    
    if method == EVerifyMethod.PHYSICAL_ITRV:
        message_parts.append("\n📥 **Download your ITR-V** from the portal and follow the steps above.\n")
    else:
        message_parts.append("\n🎯 **I'll navigate you to the verification page.** ")
        message_parts.append("Once there, follow the steps above to complete verification.\n")
        message_parts.append("\n⏳ I'll wait here. Let me know when you've completed verification ")
        message_parts.append("or if you need help.\n")
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": "".join(message_parts),
        "metadata": {
            "node": "everify_handoff",
            "handoff_id": handoff.handoff_id,
            "method": method.value,
            "user_in_control": True
        }
    })
    
    # Navigation action for non-physical methods
    navigation_action = None
    if method != EVerifyMethod.PHYSICAL_ITRV:
        navigation_action = {
            "action": "navigate",
            "url": handoff.target_url,
            "reason": f"Navigate to e-verification page for {method_info['name']}"
        }
    
    return {
        "messages": messages,
        "everify_handoff": {
            "handoff_id": handoff.handoff_id,
            "method": method.value,
            "status": handoff.status.value,
            "target_url": handoff.target_url,
            "security_notice": handoff.security_notice,
        },
        "pending_navigation": navigation_action,
        "user_in_control": True,
        "awaiting_verification_complete": True
    }


# Legacy interface
def run(state: AgentState) -> AgentState:
    import asyncio
    result = asyncio.run(everify_handoff(state))
    state.apply_update(result)
    return state
