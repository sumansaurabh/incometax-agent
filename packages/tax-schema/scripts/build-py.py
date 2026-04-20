from pathlib import Path

out = '''from pydantic import BaseModel


class SalaryIncome(BaseModel):
    gross_salary: float
    tds: float


class DeductionsVIA(BaseModel):
    section_80c: float
    section_80d: float
'''

output = Path("dist/py/models.py")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(out)
