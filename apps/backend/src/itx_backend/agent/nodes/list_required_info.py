"""
Agent Explanation Mode — list_required_info node.

Phase 1 requirement: List all information needed to complete the current page/filing.
"""

from typing import Any
from ..state import AgentState

# Required info by ITR type
ITR_REQUIRED_INFO = {
    "ITR-1": {
        "documents": [
            "Form 16 from employer",
            "Form 26AS / AIS (Annual Information Statement)",
            "Bank statements (for interest income)",
            "Investment proofs (80C, 80D, etc.) - if Old Regime"
        ],
        "information": [
            "PAN details",
            "Aadhaar (for e-verification)",
            "Bank account for refund",
            "Employer details (name, TAN)",
            "Salary breakup (gross salary, allowances)",
            "Tax-saving investments (if claiming deductions)"
        ],
        "eligibility": [
            "Total income ≤ ₹50 lakh",
            "Income from salary/pension only",
            "Income from one house property only",
            "Interest income ≤ ₹5,000",
            "Agricultural income ≤ ₹5,000",
            "No capital gains",
            "No foreign assets/income"
        ]
    },
    "ITR-2": {
        "documents": [
            "Form 16 from employer(s)",
            "Form 26AS / AIS",
            "Capital gains statements (from broker)",
            "Property sale/purchase documents",
            "Foreign asset statements (if any)",
            "Investment proofs"
        ],
        "information": [
            "All ITR-1 information",
            "Capital gains details (buy/sell dates, amounts)",
            "Multiple house property details",
            "Foreign bank accounts (if any)",
            "Directorships in companies (if any)"
        ],
        "eligibility": [
            "Individuals and HUFs",
            "Has capital gains",
            "Has foreign assets/income",
            "Multiple house properties",
            "Income > ₹50 lakh",
            "Director in a company"
        ]
    },
    "ITR-3": {
        "documents": [
            "All ITR-2 documents",
            "Profit & Loss statement",
            "Balance sheet",
            "Books of accounts",
            "GST returns (if applicable)",
            "Audit report (if turnover > ₹1 crore)"
        ],
        "information": [
            "Business income details",
            "Partner share in firm (if any)",
            "Professional income details",
            "Depreciation schedule"
        ],
        "eligibility": [
            "Income from business/profession",
            "Partner in a firm",
            "Not eligible for presumptive taxation"
        ]
    },
    "ITR-4": {
        "documents": [
            "Form 16 (if salaried)",
            "Form 26AS / AIS",
            "Bank statements",
            "Business receipts/invoices"
        ],
        "information": [
            "Gross receipts/turnover",
            "Presumptive income (6%/8%/50%)",
            "Bank account used for business"
        ],
        "eligibility": [
            "Total income ≤ ₹50 lakh",
            "Business income under ₹2 crore (44AD)",
            "Professional income under ₹50 lakh (44ADA)",
            "Opts for presumptive taxation"
        ]
    }
}

# Required info by page
PAGE_REQUIRED_INFO = {
    "personal-info": {
        "required": [
            "Full name (as per PAN)",
            "Date of birth",
            "Father's name",
            "Current address",
            "Mobile number",
            "Email address"
        ],
        "optional": [
            "Aadhaar number",
            "Employer category"
        ],
        "sources": ["PAN card", "Aadhaar card", "Passport"]
    },
    "salary-schedule": {
        "required": [
            "Employer name",
            "Employer TAN",
            "Gross salary",
            "Allowances (HRA, LTA, etc.)",
            "Perquisites value",
            "Deductions under Section 16"
        ],
        "optional": [
            "Multiple employer details"
        ],
        "sources": ["Form 16 Part B", "Salary slips"]
    },
    "deductions-vi-a": {
        "required": [],  # All deductions are optional
        "optional": [
            "80C investments (PPF, ELSS, LIC, EPF)",
            "80CCD(1B) additional NPS",
            "80D health insurance premiums",
            "80E education loan interest",
            "80G donations",
            "80TTA/TTB savings interest"
        ],
        "sources": [
            "Investment statements",
            "Premium receipts",
            "Donation receipts",
            "Bank interest certificates"
        ]
    },
    "tax-paid": {
        "required": [
            "TDS from salary (employer)",
            "TDS from other sources"
        ],
        "optional": [
            "Advance tax paid",
            "Self-assessment tax"
        ],
        "sources": ["Form 16", "Form 16A", "Form 26AS", "Challan receipts"]
    },
    "capital-gains": {
        "required": [
            "Sale consideration",
            "Cost of acquisition",
            "Date of acquisition",
            "Date of sale",
            "Type of asset"
        ],
        "optional": [
            "Improvement costs",
            "Transfer expenses",
            "Exemption claims (54, 54F, etc.)"
        ],
        "sources": ["Broker statements", "Property documents", "Contract notes"]
    },
    "house-property": {
        "required": [
            "Property type (self-occupied/let out)",
            "Property address",
            "Co-owner details (if any)"
        ],
        "optional": [
            "Rental income",
            "Municipal taxes",
            "Home loan interest",
            "Home loan principal"
        ],
        "sources": ["Rent agreement", "Home loan statement", "Municipal tax receipts"]
    },
    "bank-account": {
        "required": [
            "Bank name",
            "Account number",
            "IFSC code",
            "Account type"
        ],
        "optional": [],
        "sources": ["Bank passbook", "Cheque leaf"]
    }
}


def get_missing_info(
    page: str,
    current_facts: dict,
    portal_fields: dict
) -> dict:
    """Determine what information is still missing for a page."""
    page_info = PAGE_REQUIRED_INFO.get(page, {})
    
    missing_required = []
    missing_optional = []
    
    for field in page_info.get("required", []):
        field_key = field.lower().replace(" ", "_").replace("(", "").replace(")", "")
        if not current_facts.get(field_key) and not portal_fields.get(field_key, {}).get("value"):
            missing_required.append(field)
    
    for field in page_info.get("optional", []):
        field_key = field.lower().replace(" ", "_").replace("(", "").replace(")", "")
        if not current_facts.get(field_key) and not portal_fields.get(field_key, {}).get("value"):
            missing_optional.append(field)
    
    return {
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "sources": page_info.get("sources", [])
    }


async def list_required_info(state: AgentState) -> dict[str, Any]:
    """
    List all required information for the current page or entire filing.
    Highlights what's already collected vs what's still needed.
    """
    current_page = state.get("current_page", "unknown")
    itr_type = state.get("itr_type", "ITR-1")
    tax_facts = state.get("tax_facts", {})
    portal_state = state.get("portal_state", {})
    portal_fields = portal_state.get("fields", {})
    documents_uploaded = state.get("documents", [])
    
    message_parts = ["## Required Information\n"]
    
    # Current page requirements
    if current_page in PAGE_REQUIRED_INFO:
        missing = get_missing_info(current_page, tax_facts, portal_fields)
        
        message_parts.append(f"### For this page ({current_page.replace('-', ' ').title()})\n")
        
        if missing["missing_required"]:
            message_parts.append("**❌ Required (still needed):**")
            for item in missing["missing_required"]:
                message_parts.append(f"- {item}")
        else:
            message_parts.append("**✅ All required fields have data**")
        
        if missing["missing_optional"]:
            message_parts.append("\n**➖ Optional (can provide):**")
            for item in missing["missing_optional"]:
                message_parts.append(f"- {item}")
        
        if missing["sources"]:
            message_parts.append(f"\n📄 **Source documents:** {', '.join(missing['sources'])}")
    
    # Overall ITR requirements
    itr_info = ITR_REQUIRED_INFO.get(itr_type, ITR_REQUIRED_INFO["ITR-1"])
    
    message_parts.append(f"\n### For {itr_type} Filing\n")
    
    # Check documents
    uploaded_types = {doc.get("type") for doc in documents_uploaded}
    required_docs = itr_info.get("documents", [])
    
    message_parts.append("**Documents:**")
    for doc in required_docs:
        doc_type = doc.split("(")[0].strip().lower().replace(" ", "_")
        status = "✅" if any(t in doc_type for t in uploaded_types) else "❌"
        message_parts.append(f"- {status} {doc}")
    
    # Summary stats
    facts_collected = len([v for v in tax_facts.values() if v])
    docs_uploaded = len(documents_uploaded)
    
    message_parts.append(f"\n### Progress Summary")
    message_parts.append(f"- 📊 Tax facts collected: {facts_collected}")
    message_parts.append(f"- 📎 Documents uploaded: {docs_uploaded}")
    
    # Eligibility check
    message_parts.append(f"\n### {itr_type} Eligibility Criteria")
    for criterion in itr_info.get("eligibility", []):
        message_parts.append(f"- {criterion}")
    
    explanation_text = "\n".join(message_parts)
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": explanation_text,
        "metadata": {
            "node": "list_required_info",
            "page": current_page,
            "itr_type": itr_type
        }
    })
    
    return {
        "messages": messages,
        "required_info": {
            "page": current_page,
            "itr_type": itr_type,
            "page_requirements": PAGE_REQUIRED_INFO.get(current_page, {}),
            "itr_requirements": itr_info
        }
    }


def run(state: AgentState) -> AgentState:
    import asyncio

    result = asyncio.run(list_required_info(state))
    state.apply_update(result)
    return state
