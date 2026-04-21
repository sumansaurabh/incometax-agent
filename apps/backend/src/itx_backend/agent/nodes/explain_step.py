"""
Agent Explanation Mode — explain_current_step node.

Phase 1 requirement: Detect portal page, explain what user is looking at.
"""

from typing import Any
from ..state import AgentState

STEP_EXPLANATIONS = {
    "dashboard": {
        "title": "Income Tax Dashboard",
        "description": "This is your main ITR e-filing dashboard. From here you can:",
        "actions": [
            "File a new income tax return",
            "View previously filed returns",
            "Check refund status",
            "Respond to notices",
            "Link Aadhaar with PAN"
        ],
        "next_step": "Click 'File Income Tax Return' to start a new filing."
    },
    "file-return-start": {
        "title": "Start Filing Return",
        "description": "Select the assessment year and filing type for your return.",
        "actions": [
            "Choose Assessment Year (e.g., 2025-26 for income earned in FY 2024-25)",
            "Select filing type: Original or Revised",
            "Choose filing mode: Online or Offline"
        ],
        "next_step": "Select the assessment year and click 'Continue'."
    },
    "itr-selection": {
        "title": "ITR Form Selection",
        "description": "Choose the appropriate ITR form based on your income sources.",
        "actions": [
            "ITR-1 (Sahaj): Salaried individuals with income up to ₹50 lakh",
            "ITR-2: Individuals with capital gains, foreign assets, or multiple properties",
            "ITR-3: Business/profession income",
            "ITR-4 (Sugam): Presumptive business income"
        ],
        "tips": [
            "If you have salary + bank interest only, ITR-1 is usually correct",
            "If you sold shares/mutual funds, you need ITR-2 or higher"
        ],
        "next_step": "I'll help you pick the right ITR form based on your documents."
    },
    "personal-info": {
        "title": "Personal Information",
        "description": "Verify and complete your personal details.",
        "fields": [
            "Name (as per PAN)",
            "Date of Birth",
            "Father's Name",
            "Address",
            "Mobile Number",
            "Email"
        ],
        "tips": [
            "Details are pre-filled from your profile; verify they're current",
            "Mobile and email must match for OTP verification later"
        ],
        "next_step": "Verify the pre-filled information and update if needed."
    },
    "salary-schedule": {
        "title": "Salary Income Schedule",
        "description": "Enter your salary income details from Form 16.",
        "fields": [
            "Employer Name and TAN",
            "Gross Salary (from Form 16 Part B)",
            "Allowances (HRA, LTA, etc.)",
            "Perquisites",
            "Profits in lieu of salary",
            "Less: Standard Deduction (₹50,000 / ₹75,000)"
        ],
        "tips": [
            "Cross-check with your Form 16 from employer",
            "HRA exemption is calculated based on rent paid",
            "Standard deduction is automatic (₹75,000 for new regime)"
        ],
        "next_step": "I'll auto-fill this from your Form 16 if uploaded."
    },
    "deductions-vi-a": {
        "title": "Deductions under Chapter VI-A",
        "description": "Claim tax-saving deductions (only if choosing Old Regime).",
        "fields": [
            "80C: PPF, ELSS, LIC, EPF (max ₹1,50,000)",
            "80CCD(1B): Additional NPS (max ₹50,000)",
            "80D: Health insurance premiums",
            "80E: Education loan interest",
            "80G: Donations to eligible funds",
            "80TTA/80TTB: Savings account interest"
        ],
        "tips": [
            "Keep proofs ready — investment statements, premium receipts",
            "80C has a combined limit across all instruments",
            "80D limits vary: self/family vs parents, senior citizen status"
        ],
        "next_step": "I'll pull deduction amounts from your uploaded documents."
    },
    "tax-paid": {
        "title": "Tax Paid and Verification",
        "description": "Verify taxes already paid against your liability.",
        "fields": [
            "TDS deducted by employer (from Form 16)",
            "TDS on other income (Form 16A)",
            "Advance tax paid",
            "Self-assessment tax paid"
        ],
        "tips": [
            "Compare TDS with Form 26AS/AIS to avoid mismatches",
            "If tax paid > liability, you'll get a refund",
            "If tax paid < liability, you need to pay the balance"
        ],
        "next_step": "I'll reconcile your AIS/26AS with taxes entered here."
    },
    "summary-review": {
        "title": "Summary and Review",
        "description": "Final review before submission.",
        "sections": [
            "Gross Total Income",
            "Total Deductions",
            "Taxable Income",
            "Tax Liability",
            "Tax Paid",
            "Tax Payable / Refund Due"
        ],
        "tips": [
            "Review each section carefully",
            "Compare numbers with your documents",
            "Check for any validation errors"
        ],
        "next_step": "If everything looks correct, proceed to submit."
    },
    "regime-choice": {
        "title": "Tax Regime Selection",
        "description": "Choose between Old and New tax regimes.",
        "options": [
            "Old Regime: Lower rates but with deductions/exemptions",
            "New Regime: Higher basic exemption, fewer deductions"
        ],
        "tips": [
            "Compare total tax under both regimes",
            "Old regime better if you have significant 80C/80D/HRA",
            "New regime simpler and often better for higher incomes"
        ],
        "next_step": "I'll calculate which regime saves you more tax."
    },
    "bank-account": {
        "title": "Bank Account for Refund",
        "description": "Specify where your tax refund should be credited.",
        "fields": [
            "Bank Name",
            "Account Number",
            "IFSC Code",
            "Account Type"
        ],
        "tips": [
            "Use a bank account linked to your PAN",
            "Pre-validated accounts get faster refunds",
            "You can add multiple accounts and mark one as primary"
        ],
        "next_step": "Enter or verify your bank details for refund."
    },
    "everify": {
        "title": "E-Verification",
        "description": "Verify your return using one of these methods.",
        "methods": [
            "Aadhaar OTP (instant)",
            "Net banking",
            "Demat account",
            "Bank ATM",
            "Digital Signature Certificate (DSC)",
            "Send signed ITR-V by post (120 days)"
        ],
        "tips": [
            "Aadhaar OTP is fastest — ensure mobile is linked",
            "Return is not complete until verified",
            "I'll guide you but won't enter OTP for security"
        ],
        "next_step": "Choose verification method. I'll hand off control to you for OTP."
    },
    "capital-gains": {
        "title": "Capital Gains Schedule",
        "description": "Report gains/losses from selling assets.",
        "fields": [
            "Short-term gains (held < 1-2 years)",
            "Long-term gains (held > 1-2 years)",
            "Listed equity, mutual funds, property, etc.",
            "Cost of acquisition, sale value, expenses"
        ],
        "tips": [
            "Equity LTCG > ₹1.25 lakh is taxable at 12.5%",
            "Use grandfathering for pre-2018 equity",
            "I'll parse your broker statement for transactions"
        ],
        "next_step": "Upload broker capital gains statement for auto-fill."
    },
    "house-property": {
        "title": "Income from House Property",
        "description": "Report rental income or claim home loan deductions.",
        "fields": [
            "Property type (self-occupied/let out)",
            "Rental income received",
            "Municipal taxes paid",
            "Home loan interest (Section 24)",
            "Home loan principal (under 80C)"
        ],
        "tips": [
            "Self-occupied: Only interest deduction up to ₹2 lakh",
            "Let out: 30% standard deduction on rental income",
            "Loss from house property can offset other income"
        ],
        "next_step": "I'll need your home loan certificate for auto-fill."
    },
    "other-sources": {
        "title": "Income from Other Sources",
        "description": "Report interest, dividends, and other income.",
        "fields": [
            "Savings account interest",
            "FD/RD interest",
            "Dividend income",
            "Interest from bonds",
            "Any other income"
        ],
        "tips": [
            "Check AIS for all interest credits",
            "Dividends are fully taxable now",
            "Claim 80TTA/TTB deduction on savings interest"
        ],
        "next_step": "I'll reconcile with your AIS for completeness."
    },
    "login": {
        "title": "Income Tax Portal Login",
        "description": "Log in to start filing.",
        "fields": [
            "PAN / Aadhaar",
            "Password",
            "OTP (if enabled)"
        ],
        "tips": [
            "Use PAN or Aadhaar linked to your account",
            "Enable 2FA for security",
            "I cannot see or store your password"
        ],
        "next_step": "Please log in. I'll guide you after you're authenticated."
    }
}


async def explain_current_step(state: AgentState) -> dict[str, Any]:
    """
    Given the detected portal page, generate a natural-language explanation
    of what the user is looking at and what they need to do.
    """
    current_page = state.get("current_page", "unknown")
    portal_state = state.get("portal_state", {})
    
    explanation = STEP_EXPLANATIONS.get(current_page, {
        "title": "Unknown Page",
        "description": f"I detected page type: {current_page}. Let me analyze what's on screen.",
        "next_step": "Please describe what you see, and I'll help guide you."
    })
    
    # Build contextual explanation
    message_parts = [
        f"## {explanation['title']}\n",
        f"{explanation['description']}\n"
    ]
    
    # Add relevant fields if present
    if "fields" in explanation:
        message_parts.append("\n**Fields on this page:**")
        for field in explanation["fields"]:
            message_parts.append(f"- {field}")
    
    if "actions" in explanation:
        message_parts.append("\n**Available actions:**")
        for action in explanation["actions"]:
            message_parts.append(f"- {action}")
    
    if "options" in explanation:
        message_parts.append("\n**Options:**")
        for option in explanation["options"]:
            message_parts.append(f"- {option}")
    
    if "sections" in explanation:
        message_parts.append("\n**Sections to review:**")
        for section in explanation["sections"]:
            message_parts.append(f"- {section}")
    
    if "methods" in explanation:
        message_parts.append("\n**Verification methods:**")
        for method in explanation["methods"]:
            message_parts.append(f"- {method}")
    
    # Add tips
    if "tips" in explanation:
        message_parts.append("\n💡 **Tips:**")
        for tip in explanation["tips"]:
            message_parts.append(f"- {tip}")
    
    # Add next step
    message_parts.append(f"\n**Next step:** {explanation['next_step']}")
    
    # Check for validation errors on current page
    validation_errors = portal_state.get("validation_errors", [])
    if validation_errors:
        message_parts.append("\n⚠️ **Current validation errors:**")
        for error in validation_errors:
            message_parts.append(f"- {error}")
    
    # Check for pre-filled vs empty fields
    fields = portal_state.get("fields", {})
    empty_required = [k for k, v in fields.items() if v.get("required") and not v.get("value")]
    if empty_required:
        message_parts.append(f"\n**Required fields still empty:** {len(empty_required)}")
    
    explanation_text = "\n".join(message_parts)
    
    # Update messages
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": explanation_text,
        "metadata": {
            "node": "explain_current_step",
            "page": current_page,
            "has_errors": len(validation_errors) > 0
        }
    })
    
    return {
        "messages": messages,
        "last_explanation": {
            "page": current_page,
            "explanation": explanation,
            "validation_errors": validation_errors
        }
    }


async def run(state: AgentState) -> AgentState:
    result = await explain_current_step(state)
    state.apply_update(result)
    return state
