from pathlib import Path

out = '''from pydantic import BaseModel


class Taxpayer(BaseModel):
    pan: str
    full_name: str
    residential_status: str


class SalaryIncome(BaseModel):
    gross_salary: float
    tds: float


class DeductionsVIA(BaseModel):
    section_80c: float
    section_80d: float


class OtherSourcesIncome(BaseModel):
    total: float


class CapitalGainsIncome(BaseModel):
    stcg: float
    ltcg: float


class HousePropertyIncome(BaseModel):
    net: float
    loan_interest: float


class TaxPaidSummary(BaseModel):
    tds_salary: float
    tds_other: float
    advance_tax: float
    self_assessment_tax: float


class BankRefund(BaseModel):
    account_number_masked: str
    ifsc: str
'''

output = Path("dist/py/models.py")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(out)
