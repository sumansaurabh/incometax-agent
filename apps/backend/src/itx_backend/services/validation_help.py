from __future__ import annotations

from typing import Any, Optional


FIELD_HINTS = {
    "pan": ("PAN", lambda facts: facts.get("pan")),
    "email": ("email address", lambda facts: facts.get("email")),
    "mobile": ("mobile number", lambda facts: facts.get("mobile")),
    "ifsc": ("IFSC code", lambda facts: facts.get("bank", {}).get("ifsc")),
    "account": ("bank account number", lambda facts: facts.get("bank", {}).get("account_number")),
    "regime": ("tax regime", lambda facts: facts.get("regime")),
}


def _candidate_value(field_name: str, state: Any) -> Optional[str]:
    lowered = field_name.lower()
    facts = state.tax_facts if hasattr(state, "tax_facts") else {}
    for token, (_label, resolver) in FIELD_HINTS.items():
        if token in lowered:
            value = resolver(facts)
            return str(value) if value not in (None, "") else None
    return None


def translate_validation_errors(
    *,
    page_type: str,
    validation_errors: list[dict[str, Any]],
    portal_state: Optional[dict[str, Any]],
    state: Any,
) -> list[dict[str, Any]]:
    fields = (portal_state or {}).get("fields", {}) if isinstance(portal_state, dict) else {}
    translations: list[dict[str, Any]] = []

    for error in validation_errors:
        field_key = str(error.get("field") or "unknown")
        raw_message = str(error.get("message") or "Validation error")
        lowered = raw_message.lower()
        field_meta = fields.get(field_key, {}) if isinstance(fields, dict) else {}
        field_label = str(field_meta.get("label") or error.get("field") or "this field")
        suggested_value = _candidate_value(field_label, state) or _candidate_value(field_key, state)

        plain_english = "The portal rejected this value."
        suggested_fix = "Review the field and try again."
        question = f"Do you want me to help fix {field_label}?"
        severity = "warning"

        if any(token in lowered for token in ["required", "mandatory", "please enter", "please select"]):
            plain_english = f"{field_label} is mandatory before you can continue."
            suggested_fix = (
                f"Fill {field_label} from your verified documents."
                if suggested_value is None
                else f"Fill {field_label} with {suggested_value}."
            )
            question = f"Should I fill the required value for {field_label}?"
            severity = "error"
        elif "pan" in lowered or "pan" in field_key.lower():
            plain_english = "The PAN format looks invalid to the portal."
            suggested_fix = "Use a 10-character PAN like ABCDE1234F."
            if suggested_value:
                suggested_fix += f" Your extracted PAN is {suggested_value}."
            question = "Should I replace the PAN with the value from your documents?"
            severity = "error"
        elif "ifsc" in lowered or "ifsc" in field_key.lower():
            plain_english = "The IFSC code format is invalid or incomplete."
            suggested_fix = "Use the 11-character IFSC from your bank proof."
            if suggested_value:
                suggested_fix += f" Your stored IFSC is {suggested_value}."
            question = "Should I update the refund bank IFSC from your evidence?"
            severity = "error"
        elif "date" in lowered or "dob" in lowered:
            plain_english = "The portal expects a valid date in the format it supports."
            suggested_fix = "Re-enter the date exactly as shown in your official document."
            question = f"Should I help correct the date field for {field_label}?"
        elif "regime" in lowered or "regime" in field_key.lower():
            plain_english = "The portal wants an explicit old or new tax regime choice."
            suggested_fix = "Run a regime comparison and then set the recommended regime on the page."
            question = "Should I compare old and new regime and prepare the switch for you?"
            severity = "error"
        elif "mismatch" in lowered or "not match" in lowered:
            plain_english = "The portal sees a mismatch between related values on this step."
            suggested_fix = "Review the linked fields together and resolve the mismatch before continuing."
            question = f"Should I show the related fields for {field_label} and help correct them?"

        translations.append(
            {
                "field": field_key,
                "field_label": field_label,
                "message": raw_message,
                "plain_english": plain_english,
                "suggested_fix": suggested_fix,
                "question": question,
                "severity": severity,
                "suggested_value": suggested_value,
                "page_type": page_type,
            }
        )

    return translations