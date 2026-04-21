import fs from "node:fs";
import path from "node:path";

const out = `export type Regime = "old" | "new";
export type ResidentialStatus = "resident" | "rnor" | "non_resident";

export interface Taxpayer {
  pan: string;
  fullName: string;
  residentialStatus: ResidentialStatus;
}

export interface SalaryIncome {
  grossSalary: number;
  tds: number;
}

export interface DeductionsVIA {
  section80C: number;
  section80D: number;
}

export interface OtherSourcesIncome {
  total: number;
}

export interface CapitalGainsIncome {
  stcg: number;
  ltcg: number;
}

export interface HousePropertyIncome {
  net: number;
  loanInterest: number;
}

export interface TaxPaidSummary {
  tdsSalary: number;
  tdsOther: number;
  advanceTax: number;
  selfAssessmentTax: number;
}

export interface BankRefund {
  accountNumberMasked: string;
  ifsc: string;
}
`;

const outPath = path.join(process.cwd(), "dist/ts/index.d.ts");
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, out);
