from rules_core.caps.chapter_vi_a import cap_80c, cap_80d
from rules_core.caps.standard_deduction import standard_deduction
from rules_core.regime.old_vs_new import compare


def evaluate(deductions_80c: float, deductions_80d: float, is_salary: bool, old_tax: float, new_tax: float) -> dict:
    return {
        "section_80c_applied": cap_80c(deductions_80c),
        "section_80d_applied": cap_80d(deductions_80d),
        "standard_deduction": standard_deduction(is_salary),
        "regime": compare(old_tax, new_tax)
    }
