import { FieldSchema, StaticAdapterDefinition } from "./base";

function schema(fields: Array<[string, string, boolean, string?]>): FieldSchema[] {
  return fields.map(([key, label, required, selectorHint]) => ({
    key,
    label,
    required,
    selectorHint,
  }));
}

export const pageCatalog: StaticAdapterDefinition[] = [
  {
    key: "login",
    keywords: ["login", "sign in", "authenticate"],
    schema: schema([
      ["pan_or_aadhaar", "PAN / Aadhaar", true],
      ["password", "Password", true],
      ["otp", "OTP", false],
    ]),
  },
  {
    key: "dashboard",
    keywords: ["dashboard", "file income tax return", "your returns"],
    schema: [],
  },
  {
    key: "file-return-start",
    keywords: ["file return start", "file income tax return", "assessment year"],
    schema: schema([
      ["assessment_year", "Assessment Year", true],
      ["filing_type", "Filing Type", true],
      ["filing_mode", "Filing Mode", true],
    ]),
  },
  {
    key: "itr-selection",
    keywords: ["itr selection", "select itr", "itr form"],
    schema: schema([
      ["itr_type", "ITR Form", true],
      ["residential_status", "Residential Status", true],
      ["income_profile", "Income Profile", false],
    ]),
  },
  {
    key: "personal-info",
    keywords: ["personal info", "personal information", "profile details"],
    schema: schema([
      ["name", "Full Name", true, "#fullName"],
      ["pan", "PAN", true, "#pan"],
      ["dob", "Date of Birth", true, "#dob"],
      ["father_name", "Father's Name", true, "#fatherName"],
      ["address", "Address", true],
      ["mobile", "Mobile Number", true, "#mobile"],
      ["email", "Email Address", true, "#email"],
    ]),
  },
  {
    key: "salary-schedule",
    keywords: ["salary schedule", "schedule s", "salary income"],
    schema: schema([
      ["employer_name", "Employer Name", true, "#employerName"],
      ["employer_tan", "Employer TAN", true, "#employerTAN"],
      ["gross_salary", "Gross Salary", true, "#grossSalary"],
      ["hra", "HRA Received", false, "#hraReceived"],
      ["lta", "LTA Received", false, "#ltaReceived"],
      ["perquisites", "Perquisites", false, "#perquisites"],
      ["standard_deduction", "Standard Deduction", false, "#standardDeduction"],
    ]),
  },
  {
    key: "deductions-vi-a",
    keywords: ["deductions vi a", "chapter vi a", "80c", "80d"],
    schema: schema([
      ["section_80c", "Section 80C", false, "#sec80C"],
      ["section_80ccd_1b", "Section 80CCD(1B)", false, "#sec80CCD1B"],
      ["section_80d_self", "80D Self & Family", false, "#sec80DSelf"],
      ["section_80d_parents", "80D Parents", false, "#sec80DParents"],
      ["section_80g", "Section 80G", false, "#sec80G"],
      ["section_80tta", "Section 80TTA", false, "#sec80TTA"],
    ]),
  },
  {
    key: "other-sources",
    keywords: ["other sources", "interest income", "dividend income"],
    schema: schema([
      ["savings_interest", "Savings Interest", false],
      ["fd_interest", "FD / RD Interest", false],
      ["dividend_income", "Dividend Income", false],
      ["other_income", "Other Income", false],
    ]),
  },
  {
    key: "house-property",
    keywords: ["house property", "schedule hp", "rental income"],
    schema: schema([
      ["property_type", "Property Type", true],
      ["rental_income", "Rental Income", false, "#rentalIncome"],
      ["municipal_taxes", "Municipal Taxes", false, "#municipalTax"],
      ["home_loan_interest", "Home Loan Interest", false, "#homeLoanInterest"],
      ["co_owner_details", "Co-owner Details", false],
    ]),
  },
  {
    key: "capital-gains",
    keywords: ["capital gains", "schedule cg", "stcg", "ltcg"],
    schema: schema([
      ["stcg_listed_equity", "STCG on Listed Equity", false, "#stcgEquity"],
      ["stcg_other_assets", "STCG on Other Assets", false, "#stcgOther"],
      ["ltcg_listed_equity", "LTCG on Listed Equity", false, "#ltcgEquity"],
      ["ltcg_other_assets", "LTCG on Other Assets", false, "#ltcgOther"],
      ["sale_date", "Date of Sale", false],
      ["acquisition_date", "Date of Acquisition", false],
    ]),
  },
  {
    key: "tax-paid",
    keywords: ["tax paid", "tax details", "tds", "advance tax"],
    schema: schema([
      ["tds_salary", "TDS on Salary", true, "#tdsSalary"],
      ["tds_other", "TDS on Other Income", false, "#tdsOther"],
      ["advance_tax", "Advance Tax", false, "#advanceTax"],
      ["self_assessment_tax", "Self Assessment Tax", false, "#selfAssessmentTax"],
    ]),
  },
  {
    key: "bank-account",
    keywords: ["bank account", "refund bank", "ifsc"],
    schema: schema([
      ["bank_name", "Bank Name", true, "#bankName"],
      ["account_number", "Account Number", true, "#accountNumber"],
      ["ifsc_code", "IFSC Code", true, "#ifscCode"],
      ["account_type", "Account Type", true, "#accountType"],
    ]),
  },
  {
    key: "regime-choice",
    keywords: ["regime choice", "tax regime", "old regime", "new regime"],
    schema: schema([["tax_regime", "Tax Regime", true]]),
  },
  {
    key: "summary-review",
    keywords: ["summary review", "review return", "submission summary"],
    schema: schema([
      ["gross_total_income", "Gross Total Income", false],
      ["total_deductions", "Total Deductions", false],
      ["taxable_income", "Taxable Income", false],
      ["tax_result", "Tax Payable / Refund Due", false],
    ]),
  },
  {
    key: "everify",
    keywords: ["everify", "e verify", "verification"],
    schema: schema([["verification_method", "Verification Method", true]]),
  },
];