from __future__ import annotations

from typing import Any

from itx_backend.agent.tool_registry import tool_registry


_DESTINATIONS: dict[str, dict[str, str]] = {
    "login": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/login",
        "label": "Login",
        "breadcrumb": "e-Filing portal → Login",
    },
    "register": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/register",
        "label": "Register",
        "breadcrumb": "e-Filing portal → Register",
    },
    "file_itr": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/e-file/income-tax-return",
        "label": "File Income Tax Return",
        "breadcrumb": "e-File → Income Tax Returns → File Income Tax Return",
    },
    "view_filed_returns": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/e-file/income-tax-returns/view-filed-returns",
        "label": "View Filed Returns",
        "breadcrumb": "e-File → Income Tax Returns → View Filed Returns",
    },
    "e_verify": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/e-file/income-tax-return/e-verify-return",
        "label": "e-Verify Return",
        "breadcrumb": "e-File → Income Tax Returns → e-Verify Return",
    },
    "form_26as": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/e-file/income-tax-return/view-form-26as",
        "label": "View Form 26AS",
        "breadcrumb": "e-File → Income Tax Returns → View Form 26AS",
    },
    "ais": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/services/ais-home",
        "label": "Annual Information Statement (AIS)",
        "breadcrumb": "Services → Annual Information Statement (AIS)",
    },
    "refund_status": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/services/refund-status",
        "label": "Know your Refund Status",
        "breadcrumb": "Services → Know your Refund Status",
    },
    "e_pay_tax": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/e-pay-tax-prelogin/user-details",
        "label": "e-Pay Tax (Challan)",
        "breadcrumb": "e-Pay Tax",
    },
    "rectification": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/services/rectification",
        "label": "Rectification (u/s 154)",
        "breadcrumb": "Services → Rectification",
    },
    "bank_account": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/profile/my-bank-account",
        "label": "My Bank Account",
        "breadcrumb": "Profile → My Bank Account",
    },
    "link_aadhaar": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/pre-login/link-aadhaar",
        "label": "Link Aadhaar",
        "breadcrumb": "Quick Links → Link Aadhaar",
    },
    "grievances": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/grievances",
        "label": "Grievances",
        "breadcrumb": "Grievances",
    },
    "updated_return": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/e-file/income-tax-return/file-itr-u",
        "label": "File Updated Return (ITR-U)",
        "breadcrumb": "e-File → Income Tax Returns → File Updated Return (ITR-U)",
    },
    "authorize_representative": {
        "url": "https://eportal.incometax.gov.in/iec/foservices/#/authorised-partners",
        "label": "Authorised Partners / Authorized Representative",
        "breadcrumb": "Authorised Partners",
    },
}


_KEYS = sorted(_DESTINATIONS.keys())


@tool_registry.tool(
    name="portal_nav",
    description=(
        "Return the direct URL and breadcrumb path for a named destination on the e-Filing "
        "portal. Use this when the user asks 'where do I go to X?' or 'what's the link for X?'. "
        "For step-by-step instructions use how_to; this tool is for the deep link alone. Returns "
        "{url, label, breadcrumb}. Available destinations: " + ", ".join(_KEYS) + "."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "enum": _KEYS,
                "description": "The named portal destination.",
            },
        },
        "required": ["destination"],
        "additionalProperties": False,
    },
)
async def portal_nav(
    *,
    thread_id: str,  # noqa: ARG001 — destinations are static
    destination: str,
) -> dict[str, Any]:
    info = _DESTINATIONS.get(destination)
    if info is None:
        return {"error": "unknown_destination", "available": _KEYS}
    return {"destination": destination, **info}
