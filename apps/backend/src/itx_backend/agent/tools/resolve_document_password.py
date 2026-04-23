from __future__ import annotations

from typing import Any

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.documents import _derive_portal_password, document_service


@tool_registry.tool(
    name="resolve_document_password",
    description=(
        "Unlock Income Tax portal documents (AIS PDF, TIS PDF) that were uploaded while "
        "encrypted. Call this when the user provides their PAN and date of birth in chat "
        "and one or more of their documents is showing as 'awaiting_password'. The "
        "standard portal password is the lowercase PAN concatenated with DDMMYYYY "
        "birthdate — you do NOT need to construct it yourself; just pass pan and dob and "
        "the tool derives the correct password. On success the documents are re-parsed "
        "automatically and the PAN/DOB are saved to tax_facts so future encrypted uploads "
        "unlock without prompting."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pan": {
                "type": "string",
                "description": "10-character PAN like ABCDE1234F (case-insensitive).",
            },
            "dob": {
                "type": "string",
                "description": (
                    "Date of birth. Accepts DDMMYYYY, DD/MM/YYYY, DD-MM-YYYY, or ISO "
                    "YYYY-MM-DD. The tool normalizes the format."
                ),
            },
        },
        "required": ["pan", "dob"],
        "additionalProperties": False,
    },
)
async def resolve_document_password(*, thread_id: str, pan: str, dob: str) -> dict[str, Any]:
    password = _derive_portal_password(pan, dob)
    if not password:
        return {
            "error": "invalid_pan_or_dob",
            "message": "PAN must be 10 characters (5 letters + 4 digits + 1 letter) and DOB must have 8 digits.",
        }
    outcome = await document_service.unlock_documents_for_thread(
        thread_id=thread_id,
        password=password,
        persist_profile={"pan": pan, "dob": dob},
    )
    outcome["derived_password_length"] = len(password)
    return outcome
