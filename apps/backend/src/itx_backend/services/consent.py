from __future__ import annotations

import hashlib
import json
from typing import Any


ONBOARDING_CONSENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "upload_documents": {
        "title": "Allow document intake",
        "required": True,
        "description": "Let the agent ingest AIS, TIS, Form 16, and supporting proofs for this filing thread.",
        "consent_text": (
            "I allow this filing thread to ingest and process tax documents that I upload for fact extraction, "
            "reconciliation, and evidence generation."
        ),
        "scope": {"documents": ["ais", "tis", "form16", "proofs"]},
    },
    "fill_portal": {
        "title": "Allow guided portal autofill",
        "required": True,
        "description": "Let the agent prepare and execute browser fills on the official e-Filing portal after explicit approvals.",
        "consent_text": (
            "I allow this filing thread to prepare and execute approved DOM-based fill actions on the official e-Filing portal."
        ),
        "scope": {"portal_actions": ["read", "fill", "validate", "undo"]},
    },
    "regime_compare": {
        "title": "Allow regime comparison",
        "required": True,
        "description": "Let the agent compare old and new tax regimes using the facts currently available in this filing thread.",
        "consent_text": (
            "I allow this filing thread to compare old and new tax regimes and prepare a regime-switch proposal for my review."
        ),
        "scope": {"advisory": ["regime_preview", "regime_switch_proposal"]},
    },
    "share_with_reviewer": {
        "title": "Allow CA or reviewer sharing",
        "required": True,
        "description": "Let the agent package thread data for CA handoff or reviewer sign-off when you explicitly trigger it.",
        "consent_text": (
            "I allow this filing thread to package relevant facts, approvals, and filing artifacts for reviewer sign-off or CA handoff."
        ),
        "scope": {"sharing": ["reviewer_signoff", "ca_handoff", "client_export"]},
    },
    "submit_return": {
        "title": "Allow submission workflow preparation",
        "required": True,
        "description": "Let the agent prepare submission summaries, submission approvals, and e-verification handoff steps for this filing thread.",
        "consent_text": (
            "I allow this filing thread to prepare submission summaries, submission approvals, and manual e-verification handoff steps."
        ),
        "scope": {"submission": ["summary", "submit_prepare", "everify_handoff"]},
    },
    "retain_beyond_30d": {
        "title": "Retain artifacts beyond 30 days",
        "required": False,
        "description": "Optional. Keep this thread's uploaded materials and artifacts beyond the default short retention window.",
        "consent_text": (
            "I request retention of this filing thread's uploaded materials and filing artifacts beyond the default 30-day operational window."
        ),
        "scope": {"retention": {"mode": "extended"}},
    },
}


def onboarding_catalog() -> list[dict[str, Any]]:
    return [
        {
            "purpose": purpose,
            **definition,
        }
        for purpose, definition in ONBOARDING_CONSENT_DEFINITIONS.items()
    ]


def onboarding_definition(purpose: str) -> dict[str, Any]:
    if purpose not in ONBOARDING_CONSENT_DEFINITIONS:
        raise KeyError("unknown_consent_purpose")
    return ONBOARDING_CONSENT_DEFINITIONS[purpose]


def onboarding_response_hash(*, thread_id: str, user_id: str, purpose: str, consent_text: str) -> str:
    payload = json.dumps(
        {
            "thread_id": thread_id,
            "user_id": user_id,
            "purpose": purpose,
            "consent_text": consent_text,
            "response": "accepted",
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ping() -> str:
    return "consent_ok"
