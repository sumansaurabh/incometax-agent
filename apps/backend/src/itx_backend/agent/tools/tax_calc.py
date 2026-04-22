from __future__ import annotations

import logging
from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry

logger = logging.getLogger(__name__)


def _call_rules_core(**kwargs: Any) -> dict[str, Any]:
    """Call rules_core.evaluate lazily so a missing sibling package does not break tool import.

    The backend and workers share the rules_core package. When the worker app is on the path
    the import succeeds and we delegate. Otherwise we surface a diagnostic so the LLM can tell
    the user calculations are temporarily unavailable, instead of crashing the turn.
    """
    try:
        from rules_core import evaluate  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(f"rules_core_unavailable:{exc}") from exc
    return evaluate(**kwargs)


@tool_registry.tool(
    name="tax_calc",
    description=(
        "Perform deterministic Indian income-tax calculations using the project's rules engine. "
        "Use this whenever the user asks for numeric tax outcomes — old-vs-new regime comparison, "
        "HRA exemption, 80C/80D/80G caps, standard deduction, residential status, ITR form "
        "eligibility. Never do the math yourself; always delegate to this tool. Returns the "
        "calculator's full response including per-section deduction caps, regime comparison, "
        "eligible ITR form, required schedules, and disclosure checks. All money values are in "
        "rupees (no symbols). If you do not have a required input, ask the user — never invent."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "total_income": {
                "type": "number",
                "description": "Total income in rupees for the assessment year.",
            },
            "is_salary": {
                "type": "boolean",
                "description": "True if the user has salary income (enables standard deduction).",
            },
            "old_tax": {
                "type": "number",
                "description": "Pre-computed tax under the OLD regime in rupees (for regime compare).",
            },
            "new_tax": {
                "type": "number",
                "description": "Pre-computed tax under the NEW regime in rupees (for regime compare).",
            },
            "deductions_80c": {"type": "number", "description": "80C investments (₹, pre-cap)."},
            "deductions_80d": {"type": "number", "description": "80D health-insurance premium (₹, pre-cap)."},
            "donations_80g": {"type": "number", "description": "80G donations in rupees."},
            "donation_qualifying_percent": {
                "type": "number",
                "description": "0.5 for 50%-eligible donees, 1.0 for 100%-eligible.",
            },
            "donation_qualifying_limit": {"type": "number", "description": "Qualifying limit ceiling in rupees."},
            "savings_interest": {"type": "number", "description": "Savings-bank interest for 80TTA."},
            "senior_interest": {"type": "number", "description": "Senior-citizen interest for 80TTB."},
            "hra_received": {"type": "number", "description": "HRA received from employer (₹)."},
            "rent_paid": {"type": "number", "description": "Annual rent paid (₹)."},
            "basic_salary": {"type": "number", "description": "Basic salary for HRA calc (₹)."},
            "metro": {"type": "boolean", "description": "True if the rented house is in a metro city."},
            "senior_citizen": {"type": "boolean", "description": "True if age 60+."},
            "has_capital_gains": {"type": "boolean"},
            "has_business_income": {"type": "boolean"},
            "presumptive_income": {"type": "boolean", "description": "True if filing under 44AD/44ADA/44AE."},
            "resident": {"type": "boolean", "description": "True if Indian resident for the year."},
            "has_foreign_assets": {"type": "boolean"},
            "has_foreign_income": {"type": "boolean"},
            "has_multiple_house_properties": {"type": "boolean"},
            "agricultural_income": {"type": "number"},
        },
        "additionalProperties": False,
    },
)
async def tax_calc(
    *,
    thread_id: str,  # noqa: ARG001 — required by runner contract; calc is thread-independent
    total_income: float = 0.0,
    is_salary: bool = False,
    old_tax: float = 0.0,
    new_tax: float = 0.0,
    deductions_80c: float = 0.0,
    deductions_80d: float = 0.0,
    donations_80g: float = 0.0,
    donation_qualifying_percent: float = 0.5,
    donation_qualifying_limit: float = 0.0,
    savings_interest: float = 0.0,
    senior_interest: float = 0.0,
    hra_received: float = 0.0,
    rent_paid: float = 0.0,
    basic_salary: float = 0.0,
    metro: bool = False,
    senior_citizen: bool = False,
    has_capital_gains: bool = False,
    has_business_income: bool = False,
    presumptive_income: bool = False,
    resident: bool = True,
    has_foreign_assets: bool = False,
    has_foreign_income: bool = False,
    has_multiple_house_properties: bool = False,
    agricultural_income: float = 0.0,
    **extra: Any,
) -> dict[str, Any]:
    try:
        result = _call_rules_core(
            deductions_80c=float(deductions_80c),
            deductions_80d=float(deductions_80d),
            is_salary=bool(is_salary),
            old_tax=float(old_tax),
            new_tax=float(new_tax),
            total_income=float(total_income),
            has_capital_gains=bool(has_capital_gains),
            resident=bool(resident),
            has_business_income=bool(has_business_income),
            presumptive_income=bool(presumptive_income),
            senior_citizen=bool(senior_citizen),
            donations_80g=float(donations_80g),
            donation_qualifying_percent=float(donation_qualifying_percent),
            donation_qualifying_limit=float(donation_qualifying_limit),
            savings_interest=float(savings_interest),
            senior_interest=float(senior_interest),
            hra_received=float(hra_received),
            rent_paid=float(rent_paid),
            basic_salary=float(basic_salary),
            metro=bool(metro),
            has_foreign_assets=bool(has_foreign_assets),
            has_foreign_income=bool(has_foreign_income),
            has_multiple_house_properties=bool(has_multiple_house_properties),
            agricultural_income=float(agricultural_income),
        )
    except RuntimeError as exc:
        logger.warning("tax_calc.unavailable", extra={"error": str(exc)})
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — calc errors should surface as tool errors
        logger.exception("tax_calc.failed")
        return {"error": f"rules_core_failed:{type(exc).__name__}:{exc}"}

    return {
        "inputs_echo": {
            "total_income": total_income,
            "is_salary": is_salary,
            "old_tax": old_tax,
            "new_tax": new_tax,
        },
        "result": result,
    }
