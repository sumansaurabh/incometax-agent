from __future__ import annotations

import hashlib
import json
from typing import Any


ONBOARDING_CONSENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "upload_documents": {
        "title": "Allow document intake",
        "required": True,
        "category": "filing",
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
        "category": "filing",
        "description": "Let the agent prepare and execute browser fills on the official e-Filing portal after explicit approvals.",
        "consent_text": (
            "I allow this filing thread to prepare and execute approved DOM-based fill actions on the official e-Filing portal."
        ),
        "scope": {"portal_actions": ["read", "fill", "validate", "undo"]},
    },
    "regime_compare": {
        "title": "Allow regime comparison",
        "required": True,
        "category": "advisory",
        "description": "Let the agent compare old and new tax regimes using the facts currently available in this filing thread.",
        "consent_text": (
            "I allow this filing thread to compare old and new tax regimes and prepare a regime-switch proposal for my review."
        ),
        "scope": {"advisory": ["regime_preview", "regime_switch_proposal"]},
    },
    "share_with_reviewer": {
        "title": "Allow CA or reviewer sharing",
        "required": True,
        "category": "review",
        "description": "Let the agent package thread data for CA handoff or reviewer sign-off when you explicitly trigger it.",
        "consent_text": (
            "I allow this filing thread to package relevant facts, approvals, and filing artifacts for reviewer sign-off or CA handoff."
        ),
        "scope": {"sharing": ["reviewer_signoff", "ca_handoff", "client_export"]},
    },
    "submit_return": {
        "title": "Allow submission workflow preparation",
        "required": True,
        "category": "submission",
        "description": "Let the agent prepare submission summaries, submission approvals, and e-verification handoff steps for this filing thread.",
        "consent_text": (
            "I allow this filing thread to prepare submission summaries, submission approvals, and manual e-verification handoff steps."
        ),
        "scope": {"submission": ["summary", "submit_prepare", "everify_handoff"]},
    },
    "retain_beyond_30d": {
        "title": "Retain artifacts beyond 30 days",
        "required": False,
        "category": "retention",
        "description": "Optional. Keep this thread's uploaded materials and artifacts beyond the default short retention window.",
        "consent_text": (
            "I request retention of this filing thread's uploaded materials and filing artifacts beyond the default 30-day operational window."
        ),
        "scope": {"retention": {"mode": "extended"}},
    },
    "share_review_summary": {
        "title": "Share review summary with CA",
        "required": False,
        "category": "review",
        "depends_on": ["share_with_reviewer"],
        "description": "Optional. Let the agent share the filing summary, blockers, and approval context during reviewer sign-off.",
        "consent_text": (
            "I allow this filing thread to share filing summaries, blocking issues, and approval context with a reviewer or CA."
        ),
        "scope": {"sharing": ["review_summary", "blocking_issues", "approval_context"]},
    },
    "share_supporting_documents": {
        "title": "Share supporting evidence with CA",
        "required": False,
        "category": "review",
        "depends_on": ["share_with_reviewer"],
        "description": "Optional. Let the agent include evidence snippets and supporting documents in reviewer handoff packages.",
        "consent_text": (
            "I allow this filing thread to share supporting documents and evidence snippets with a reviewer or CA for filing review."
        ),
        "scope": {"sharing": ["supporting_documents", "evidence_snippets", "handoff_package"]},
    },
    "export_filing_bundle": {
        "title": "Allow export bundle generation",
        "required": False,
        "category": "review",
        "depends_on": ["share_with_reviewer"],
        "description": "Optional. Let the agent generate downloadable export bundles that include offline JSON and filing artifacts.",
        "consent_text": (
            "I allow this filing thread to generate downloadable filing bundles for reviewer or CA workflows."
        ),
        "scope": {"sharing": ["offline_json", "artifact_export", "evidence_bundle"]},
    },
    "everify_portal_handoff": {
        "title": "Allow e-verify portal handoff",
        "required": False,
        "category": "submission",
        "depends_on": ["submit_return"],
        "description": "Optional. Let the agent open the portal handoff step and track manual e-verification completion for this thread.",
        "consent_text": (
            "I allow this filing thread to prepare e-verification handoff steps, open the portal verification page, and record the completion reference."
        ),
        "scope": {"submission": ["everify_prepare", "everify_handoff", "everify_complete"]},
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


def active_purposes(consents: list[dict[str, Any]]) -> set[str]:
    return {
        str(consent.get("purpose"))
        for consent in consents
        if consent.get("revoked_at") in (None, "")
    }


def missing_purposes(consents: list[dict[str, Any]], required_purposes: list[str]) -> list[str]:
    active = active_purposes(consents)
    return [purpose for purpose in required_purposes if purpose not in active]


def ping() -> str:
    return "consent_ok"
