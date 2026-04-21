from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from itx_backend.agent.nodes.submission_summary import (
    TaxRegime,
    calculate_tax_new_regime,
    calculate_tax_old_regime,
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _compute_projection(tax_facts: dict[str, Any], regime: TaxRegime) -> dict[str, Any]:
    salary = _decimal(tax_facts.get("salary", {}).get("gross"))
    house_property = _decimal(tax_facts.get("house_property", {}).get("net"))
    stcg = _decimal(tax_facts.get("capital_gains", {}).get("stcg"))
    ltcg = _decimal(tax_facts.get("capital_gains", {}).get("ltcg"))
    other_sources = _decimal(tax_facts.get("other_sources", {}).get("total"))
    gross_total_income = salary + house_property + stcg + ltcg + other_sources

    deductions = tax_facts.get("deductions", {})
    exemptions = tax_facts.get("exemptions", {})
    if regime == TaxRegime.OLD:
        standard_deduction = Decimal("50000")
        total_deductions = (
            standard_deduction
            + _decimal(deductions.get("80c"))
            + _decimal(deductions.get("80ccd_1b"))
            + _decimal(deductions.get("80d"))
            + _decimal(deductions.get("80e"))
            + _decimal(deductions.get("80g"))
            + _decimal(deductions.get("80tta"))
            + _decimal(exemptions.get("hra"))
            + _decimal(exemptions.get("lta"))
        )
    else:
        standard_deduction = Decimal("75000")
        total_deductions = standard_deduction

    taxable_income = max(gross_total_income - total_deductions, Decimal(0))
    base_tax = calculate_tax_old_regime(taxable_income) if regime == TaxRegime.OLD else calculate_tax_new_regime(taxable_income)
    stcg_tax = stcg * Decimal("0.15")
    ltcg_tax = max(ltcg - Decimal("125000"), Decimal(0)) * Decimal("0.125")
    tax_before_relief = base_tax + stcg_tax + ltcg_tax
    relief_limit = Decimal("700000") if regime == TaxRegime.NEW else Decimal("500000")
    relief_87a = Decimal(0)
    if taxable_income <= relief_limit:
        relief_87a = min(tax_before_relief, Decimal("25000") if regime == TaxRegime.NEW else Decimal("12500"))
    tax_after_relief = max(tax_before_relief - relief_87a, Decimal(0))
    cess = tax_after_relief * Decimal("0.04")
    net_tax_liability = tax_after_relief + cess
    total_tax_paid = (
        _decimal(tax_facts.get("tax_paid", {}).get("tds_salary"))
        + _decimal(tax_facts.get("tax_paid", {}).get("tds_other"))
        + _decimal(tax_facts.get("tax_paid", {}).get("advance_tax"))
        + _decimal(tax_facts.get("tax_paid", {}).get("self_assessment_tax"))
        + _decimal(tax_facts.get("tax_paid", {}).get("tcs"))
    )
    balance = net_tax_liability - total_tax_paid
    tax_payable = max(balance, Decimal(0))
    refund_due = abs(min(balance, Decimal(0)))

    return {
        "regime": regime.value,
        "gross_total_income": float(gross_total_income),
        "total_deductions": float(total_deductions),
        "taxable_income": float(taxable_income),
        "net_tax_liability": float(net_tax_liability),
        "total_tax_paid": float(total_tax_paid),
        "tax_payable": float(tax_payable),
        "refund_due": float(refund_due),
        "effective_result": float(refund_due - tax_payable),
    }


def compare_regimes(tax_facts: dict[str, Any]) -> dict[str, Any]:
    current_regime = str(tax_facts.get("regime") or "new").lower()
    old_projection = _compute_projection(deepcopy(tax_facts), TaxRegime.OLD)
    new_projection = _compute_projection(deepcopy(tax_facts), TaxRegime.NEW)

    recommended = old_projection if old_projection["effective_result"] > new_projection["effective_result"] else new_projection
    current_projection = old_projection if current_regime == TaxRegime.OLD.value else new_projection
    delta = recommended["effective_result"] - current_projection["effective_result"]
    rationale = []
    if recommended["regime"] == TaxRegime.OLD.value:
        rationale.append("Old regime preserves claimed deductions and exemptions.")
        if old_projection["total_deductions"] > new_projection["total_deductions"]:
            rationale.append("Your deduction profile materially improves the old-regime outcome.")
    else:
        rationale.append("New regime reduces liability after its higher standard deduction and slab structure.")
        if new_projection["taxable_income"] < old_projection["taxable_income"]:
            rationale.append("The simplified slab structure offsets your current deduction profile.")

    if delta == 0:
        rationale.append("Both regimes currently produce the same net outcome.")

    return {
        "current_regime": current_regime,
        "recommended_regime": recommended["regime"],
        "delta_vs_current": float(delta),
        "old_regime": old_projection,
        "new_regime": new_projection,
        "rationale": rationale,
    }