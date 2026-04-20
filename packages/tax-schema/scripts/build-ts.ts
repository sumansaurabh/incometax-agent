import fs from "node:fs";
import path from "node:path";

const out = `export type Regime = "old" | "new";
export type ResidentialStatus = "resident" | "rnor" | "non_resident";

export interface SalaryIncome {
  grossSalary: number;
  tds: number;
}

export interface DeductionsVIA {
  section80C: number;
  section80D: number;
}
`;

const outPath = path.join(process.cwd(), "dist/ts/index.d.ts");
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, out);
