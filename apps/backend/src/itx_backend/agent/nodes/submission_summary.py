"""
Submission summary node — Phase 4 requirement.

Generates comprehensive summary before submission:
- Total income breakdown
- Tax computation
- Tax paid vs liability
- Mismatches and disclosures
- Final refund/payable amount
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from enum import Enum

from ..state import AgentState


class TaxRegime(str, Enum):
    OLD = "old"
    NEW = "new"


class MismatchSeverity(str, Enum):
    INFO = "info"           # No action needed
    WARNING = "warning"     # Should review
    ERROR = "error"         # Must resolve before filing


@dataclass
class IncomeBreakdown:
    """Breakdown of total income by source."""
    salary: Decimal = Decimal(0)
    house_property: Decimal = Decimal(0)
    capital_gains_stcg: Decimal = Decimal(0)
    capital_gains_ltcg: Decimal = Decimal(0)
    other_sources: Decimal = Decimal(0)
    business_profession: Decimal = Decimal(0)
    
    @property
    def gross_total(self) -> Decimal:
        return (
            self.salary + 
            self.house_property + 
            self.capital_gains_stcg + 
            self.capital_gains_ltcg + 
            self.other_sources +
            self.business_profession
        )


@dataclass
class DeductionBreakdown:
    """Breakdown of deductions claimed."""
    standard_deduction: Decimal = Decimal(50000)  # Or 75000 for new regime
    section_80c: Decimal = Decimal(0)
    section_80ccd_1b: Decimal = Decimal(0)
    section_80d: Decimal = Decimal(0)
    section_80e: Decimal = Decimal(0)
    section_80g: Decimal = Decimal(0)
    section_80tta: Decimal = Decimal(0)
    hra_exemption: Decimal = Decimal(0)
    lta_exemption: Decimal = Decimal(0)
    other_deductions: Decimal = Decimal(0)
    
    @property
    def total(self) -> Decimal:
        return (
            self.standard_deduction +
            self.section_80c +
            self.section_80ccd_1b +
            self.section_80d +
            self.section_80e +
            self.section_80g +
            self.section_80tta +
            self.hra_exemption +
            self.lta_exemption +
            self.other_deductions
        )


@dataclass
class TaxComputation:
    """Tax computation details."""
    taxable_income: Decimal = Decimal(0)
    tax_on_normal_income: Decimal = Decimal(0)
    tax_on_stcg: Decimal = Decimal(0)
    tax_on_ltcg: Decimal = Decimal(0)
    surcharge: Decimal = Decimal(0)
    education_cess: Decimal = Decimal(0)
    total_tax_liability: Decimal = Decimal(0)
    relief_87a: Decimal = Decimal(0)
    net_tax_liability: Decimal = Decimal(0)


@dataclass
class TaxPaidBreakdown:
    """Taxes already paid."""
    tds_salary: Decimal = Decimal(0)
    tds_other: Decimal = Decimal(0)
    tcs: Decimal = Decimal(0)
    advance_tax: Decimal = Decimal(0)
    self_assessment_tax: Decimal = Decimal(0)
    
    @property
    def total(self) -> Decimal:
        return (
            self.tds_salary +
            self.tds_other +
            self.tcs +
            self.advance_tax +
            self.self_assessment_tax
        )


@dataclass
class Mismatch:
    """A data mismatch or discrepancy."""
    field: str
    description: str
    severity: MismatchSeverity
    our_value: str
    ais_value: Optional[str] = None
    form16_value: Optional[str] = None
    resolution: Optional[str] = None


@dataclass
class SubmissionSummary:
    """Complete submission summary."""
    summary_id: str
    generated_at: str
    assessment_year: str
    itr_type: str
    regime: TaxRegime
    
    # Taxpayer info
    pan: str
    name: str
    
    # Income
    income: IncomeBreakdown
    gross_total_income: Decimal
    
    # Deductions
    deductions: DeductionBreakdown
    total_deductions: Decimal
    
    # Tax
    tax: TaxComputation
    
    # Paid
    paid: TaxPaidBreakdown
    total_tax_paid: Decimal
    
    # Result
    tax_payable: Decimal = Decimal(0)
    refund_due: Decimal = Decimal(0)
    
    # Mismatches
    mismatches: list[Mismatch] = field(default_factory=list)
    
    # Disclosure checks
    foreign_assets_declared: bool = False
    directorship_declared: bool = False
    unlisted_shares_declared: bool = False
    
    # Ready to file?
    can_submit: bool = True
    blocking_issues: list[str] = field(default_factory=list)


def calculate_tax_old_regime(taxable_income: Decimal) -> Decimal:
    """Calculate tax under old regime for individuals."""
    tax = Decimal(0)
    income = taxable_income
    
    # Slab rates for FY 2024-25 (AY 2025-26) - Old Regime
    if income <= 250000:
        return Decimal(0)
    
    if income > 250000:
        taxable = min(income - 250000, 250000)
        tax += taxable * Decimal("0.05")
    
    if income > 500000:
        taxable = min(income - 500000, 500000)
        tax += taxable * Decimal("0.20")
    
    if income > 1000000:
        taxable = income - 1000000
        tax += taxable * Decimal("0.30")
    
    return tax


def calculate_tax_new_regime(taxable_income: Decimal) -> Decimal:
    """Calculate tax under new regime for individuals."""
    tax = Decimal(0)
    income = taxable_income
    
    # Slab rates for FY 2024-25 (AY 2025-26) - New Regime
    if income <= 300000:
        return Decimal(0)
    
    slabs = [
        (300000, 600000, Decimal("0.05")),
        (600000, 900000, Decimal("0.10")),
        (900000, 1200000, Decimal("0.15")),
        (1200000, 1500000, Decimal("0.20")),
        (1500000, float('inf'), Decimal("0.30")),
    ]
    
    for lower, upper, rate in slabs:
        if income > lower:
            taxable = min(income, Decimal(upper)) - Decimal(lower)
            tax += taxable * rate
    
    return tax


def calculate_surcharge(tax: Decimal, income: Decimal) -> Decimal:
    """Calculate surcharge based on income."""
    if income <= 5000000:
        return Decimal(0)
    elif income <= 10000000:
        return tax * Decimal("0.10")
    elif income <= 20000000:
        return tax * Decimal("0.15")
    elif income <= 50000000:
        return tax * Decimal("0.25")
    else:
        return tax * Decimal("0.37")


def format_currency(value: Decimal) -> str:
    """Format as Indian currency."""
    val = float(value)
    if val >= 10000000:
        return f"₹{val/10000000:.2f} Cr"
    elif val >= 100000:
        return f"₹{val/100000:.2f} L"
    else:
        return f"₹{val:,.2f}"


async def submission_summary(state: AgentState) -> dict[str, Any]:
    """
    Generate comprehensive submission summary.
    
    Phase 4 requirement:
    - Totals, taxable income, tax payable/refund
    - Mismatches and disclosure checks
    - Blocking issues that prevent filing
    """
    tax_facts = state.get("tax_facts", {})
    reconciliation = state.get("reconciliation", {})
    regime = TaxRegime(tax_facts.get("regime", "new"))
    
    # Build income breakdown
    income = IncomeBreakdown(
        salary=Decimal(str(tax_facts.get("salary", {}).get("gross", 0))),
        house_property=Decimal(str(tax_facts.get("house_property", {}).get("net", 0))),
        capital_gains_stcg=Decimal(str(tax_facts.get("capital_gains", {}).get("stcg", 0))),
        capital_gains_ltcg=Decimal(str(tax_facts.get("capital_gains", {}).get("ltcg", 0))),
        other_sources=Decimal(str(tax_facts.get("other_sources", {}).get("total", 0))),
    )
    
    # Build deduction breakdown (only for old regime)
    deductions = DeductionBreakdown()
    if regime == TaxRegime.OLD:
        ded = tax_facts.get("deductions", {})
        deductions.standard_deduction = Decimal("50000")
        deductions.section_80c = Decimal(str(ded.get("80c", 0)))
        deductions.section_80ccd_1b = Decimal(str(ded.get("80ccd_1b", 0)))
        deductions.section_80d = Decimal(str(ded.get("80d", 0)))
        deductions.section_80e = Decimal(str(ded.get("80e", 0)))
        deductions.section_80g = Decimal(str(ded.get("80g", 0)))
        deductions.section_80tta = Decimal(str(ded.get("80tta", 0)))
        deductions.hra_exemption = Decimal(str(tax_facts.get("exemptions", {}).get("hra", 0)))
    else:
        deductions.standard_deduction = Decimal("75000")  # New regime standard deduction
    
    # Calculate taxable income
    gross_total = income.gross_total
    total_deductions = deductions.total
    taxable_income = max(gross_total - total_deductions, Decimal(0))
    
    # Calculate tax
    if regime == TaxRegime.OLD:
        base_tax = calculate_tax_old_regime(taxable_income)
    else:
        base_tax = calculate_tax_new_regime(taxable_income)
    
    # STCG and LTCG taxed separately
    stcg_tax = income.capital_gains_stcg * Decimal("0.15")  # 15% STCG
    ltcg_tax = max(income.capital_gains_ltcg - Decimal("125000"), Decimal(0)) * Decimal("0.125")  # 12.5% after 1.25L exemption
    
    total_tax = base_tax + stcg_tax + ltcg_tax
    
    # Surcharge and cess
    surcharge = calculate_surcharge(total_tax, taxable_income)
    tax_with_surcharge = total_tax + surcharge
    cess = tax_with_surcharge * Decimal("0.04")  # 4% Health & Education Cess
    
    # Relief 87A (if taxable income <= 7L in new regime or <= 5L in old)
    relief_limit = Decimal("700000") if regime == TaxRegime.NEW else Decimal("500000")
    relief_87a = Decimal(0)
    if taxable_income <= relief_limit:
        relief_87a = min(base_tax, Decimal("25000") if regime == TaxRegime.NEW else Decimal("12500"))
    
    total_liability = tax_with_surcharge + cess - relief_87a
    
    tax_computation = TaxComputation(
        taxable_income=taxable_income,
        tax_on_normal_income=base_tax,
        tax_on_stcg=stcg_tax,
        tax_on_ltcg=ltcg_tax,
        surcharge=surcharge,
        education_cess=cess,
        total_tax_liability=tax_with_surcharge + cess,
        relief_87a=relief_87a,
        net_tax_liability=total_liability,
    )
    
    # Tax paid
    paid_info = tax_facts.get("tax_paid", {})
    paid = TaxPaidBreakdown(
        tds_salary=Decimal(str(paid_info.get("tds_salary", 0))),
        tds_other=Decimal(str(paid_info.get("tds_other", 0))),
        tcs=Decimal(str(paid_info.get("tcs", 0))),
        advance_tax=Decimal(str(paid_info.get("advance_tax", 0))),
        self_assessment_tax=Decimal(str(paid_info.get("self_assessment_tax", 0))),
    )
    
    # Calculate payable/refund
    balance = total_liability - paid.total
    tax_payable = max(balance, Decimal(0))
    refund_due = abs(min(balance, Decimal(0)))
    
    # Collect mismatches from reconciliation
    mismatches = []
    for mismatch in reconciliation.get("mismatches", []):
        mismatches.append(Mismatch(
            field=mismatch.get("field", ""),
            description=mismatch.get("description", ""),
            severity=MismatchSeverity(mismatch.get("severity", "info")),
            our_value=str(mismatch.get("our_value", "")),
            ais_value=mismatch.get("ais_value"),
            form16_value=mismatch.get("form16_value"),
            resolution=mismatch.get("resolution"),
        ))
    
    # Check for blocking issues
    blocking_issues = []
    if any(m.severity == MismatchSeverity.ERROR for m in mismatches):
        blocking_issues.append("Unresolved data mismatches with ERROR severity")
    if not tax_facts.get("bank", {}).get("account_number"):
        blocking_issues.append("Bank account details not provided")
    if tax_facts.get("has_foreign_assets") and not tax_facts.get("foreign_assets_declared"):
        blocking_issues.append("Foreign assets not declared in Schedule FA")
    
    summary = SubmissionSummary(
        summary_id=f"sum-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        assessment_year=tax_facts.get("assessment_year", "2025-26"),
        itr_type=state.get("itr_type", "ITR-1"),
        regime=regime,
        pan=tax_facts.get("pan", ""),
        name=tax_facts.get("name", ""),
        income=income,
        gross_total_income=gross_total,
        deductions=deductions,
        total_deductions=total_deductions,
        tax=tax_computation,
        paid=paid,
        total_tax_paid=paid.total,
        tax_payable=tax_payable,
        refund_due=refund_due,
        mismatches=mismatches,
        foreign_assets_declared=tax_facts.get("foreign_assets_declared", False),
        directorship_declared=tax_facts.get("directorship_declared", False),
        unlisted_shares_declared=tax_facts.get("unlisted_shares_declared", False),
        can_submit=len(blocking_issues) == 0,
        blocking_issues=blocking_issues,
    )
    
    # Build summary message
    message_parts = [
        f"## 📋 Submission Summary\n",
        f"**Assessment Year:** {summary.assessment_year}\n",
        f"**ITR Type:** {summary.itr_type}\n",
        f"**Tax Regime:** {regime.value.title()}\n",
        f"\n### Income Breakdown\n",
        f"| Source | Amount |\n|--------|--------|\n",
        f"| Salary | {format_currency(income.salary)} |\n",
        f"| House Property | {format_currency(income.house_property)} |\n",
        f"| STCG | {format_currency(income.capital_gains_stcg)} |\n",
        f"| LTCG | {format_currency(income.capital_gains_ltcg)} |\n",
        f"| Other Sources | {format_currency(income.other_sources)} |\n",
        f"| **Gross Total** | **{format_currency(gross_total)}** |\n",
        f"\n### Deductions\n",
        f"| Deduction | Amount |\n|-----------|--------|\n",
        f"| Standard Deduction | {format_currency(deductions.standard_deduction)} |\n",
    ]
    
    if regime == TaxRegime.OLD:
        message_parts.extend([
            f"| Section 80C | {format_currency(deductions.section_80c)} |\n",
            f"| Section 80D | {format_currency(deductions.section_80d)} |\n",
            f"| HRA Exemption | {format_currency(deductions.hra_exemption)} |\n",
        ])
    
    message_parts.extend([
        f"| **Total Deductions** | **{format_currency(total_deductions)}** |\n",
        f"\n### Tax Computation\n",
        f"| Item | Amount |\n|------|--------|\n",
        f"| Taxable Income | {format_currency(taxable_income)} |\n",
        f"| Tax on Income | {format_currency(tax_computation.tax_on_normal_income)} |\n",
        f"| Tax on STCG | {format_currency(stcg_tax)} |\n",
        f"| Tax on LTCG | {format_currency(ltcg_tax)} |\n",
        f"| Surcharge | {format_currency(surcharge)} |\n",
        f"| Health & Edu Cess | {format_currency(cess)} |\n",
        f"| Less: Relief 87A | {format_currency(relief_87a)} |\n",
        f"| **Net Tax Liability** | **{format_currency(total_liability)}** |\n",
        f"\n### Tax Paid\n",
        f"| Source | Amount |\n|--------|--------|\n",
        f"| TDS on Salary | {format_currency(paid.tds_salary)} |\n",
        f"| TDS on Other | {format_currency(paid.tds_other)} |\n",
        f"| Advance Tax | {format_currency(paid.advance_tax)} |\n",
        f"| **Total Paid** | **{format_currency(paid.total)}** |\n",
    ])
    
    # Result
    if refund_due > 0:
        message_parts.append(f"\n### ✅ Refund Due: **{format_currency(refund_due)}**\n")
    elif tax_payable > 0:
        message_parts.append(f"\n### ⚠️ Tax Payable: **{format_currency(tax_payable)}**\n")
        message_parts.append("_Please pay the balance tax before submitting._\n")
    else:
        message_parts.append(f"\n### ✅ No Tax Due\n")
    
    # Mismatches
    if mismatches:
        message_parts.append(f"\n### ⚠️ Data Mismatches ({len(mismatches)})\n")
        for m in mismatches:
            icon = "❌" if m.severity == MismatchSeverity.ERROR else "⚠️" if m.severity == MismatchSeverity.WARNING else "ℹ️"
            message_parts.append(f"- {icon} **{m.field}**: {m.description}\n")
    
    # Blocking issues
    if blocking_issues:
        message_parts.append(f"\n### 🚫 Blocking Issues\n")
        for issue in blocking_issues:
            message_parts.append(f"- ❌ {issue}\n")
        message_parts.append("\n_Please resolve these issues before submitting._\n")
    else:
        message_parts.append(f"\n---\n")
        message_parts.append(f"✅ **Ready to submit.** Click 'Proceed to Submit' to continue.\n")
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": "".join(message_parts),
        "metadata": {
            "node": "submission_summary",
            "summary_id": summary.summary_id,
            "can_submit": summary.can_submit,
            "refund_due": float(refund_due),
            "tax_payable": float(tax_payable),
        }
    })
    
    return {
        "messages": messages,
        "submission_summary": {
            "summary_id": summary.summary_id,
            "assessment_year": summary.assessment_year,
            "itr_type": summary.itr_type,
            "regime": summary.regime.value,
            "gross_total_income": float(gross_total),
            "total_deductions": float(total_deductions),
            "taxable_income": float(taxable_income),
            "net_tax_liability": float(total_liability),
            "total_tax_paid": float(paid.total),
            "tax_payable": float(tax_payable),
            "refund_due": float(refund_due),
            "mismatch_count": len(mismatches),
            "can_submit": summary.can_submit,
            "blocking_issues": blocking_issues,
        },
        "pending_submission": {
            "assessment_year": summary.assessment_year,
            "total_income": float(gross_total),
            "tax_result": f"Refund: {format_currency(refund_due)}" if refund_due > 0 else f"Payable: {format_currency(tax_payable)}",
            "is_final": True,
        } if summary.can_submit else None
    }


# Legacy interface
def run(state: AgentState) -> AgentState:
    import asyncio
    result = asyncio.run(submission_summary(state))
    state.apply_update(result)
    return state
