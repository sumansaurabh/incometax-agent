import { FieldSchema, StaticAdapterDefinition } from "./base";

function schema(fields: Array<[string, string, boolean, string?, string[]?]>): FieldSchema[] {
  return fields.map(([key, label, required, selectorHint, aliases]) => ({
    key,
    label,
    required,
    selectorHint,
    aliases,
  }));
}

export const pageCatalog: StaticAdapterDefinition[] = [
  {
    key: "login",
    keywords: ["login", "sign in", "authenticate"],
    textClues: ["pan", "password", "otp", "captcha"],
    schema: schema([
      ["pan_or_aadhaar", "PAN / Aadhaar", true, "#panOrAadhaar, input[name='pan'], input[name='userid'], input[name='username']", ["user id", "pan", "aadhaar"]],
      ["password", "Password", true, "#password, input[name='password']"],
      ["otp", "OTP", false, "#otp, input[name='otp']"],
    ]),
  },
  {
    key: "dashboard",
    keywords: ["dashboard", "file income tax return", "your returns"],
    textClues: ["view filed returns", "refund status", "e-file", "pending actions"],
    schema: schema([
      ["start_filing", "File Income Tax Return", false, "a[href*='file-return'], button[data-testid='file-return'], button[aria-label*='file return' i]", ["start filing", "e-file"]],
      ["view_returns", "View Filed Returns", false, "a[href*='filed-returns'], button[data-testid='view-returns']"],
      ["refund_status", "Refund Status", false, "a[href*='refund'], button[data-testid='refund-status']", ["know your refund"]],
      ["pending_notices", "Pending Notices", false, "a[href*='notice'], button[data-testid='notices']"],
    ]),
  },
  {
    key: "file-return-start",
    keywords: ["file return start", "file income tax return", "assessment year"],
    textClues: ["assessment year", "filing type", "mode of filing"],
    schema: schema([
      ["assessment_year", "Assessment Year", true, "select[name='assessment_year'], #assessmentYear", ["ay"]],
      ["filing_type", "Filing Type", true, "select[name='filing_type'], #filingType", ["return type"]],
      ["filing_mode", "Filing Mode", true, "select[name='filing_mode'], #filingMode", ["mode of filing"]],
    ]),
  },
  {
    key: "itr-selection",
    keywords: ["itr selection", "select itr", "itr form"],
    textClues: ["itr 1", "itr 2", "itr 3", "itr 4"],
    schema: schema([
      ["itr_type", "ITR Form", true, "select[name='itr_type'], #itrType, input[name='itr_type']", ["return form"]],
      ["residential_status", "Residential Status", true, "select[name='residential_status'], #residentialStatus"],
      ["income_profile", "Income Profile", false, "#incomeProfile, [data-field='income_profile']", ["income sources"]],
    ]),
  },
  {
    key: "personal-info",
    keywords: ["personal info", "personal information", "profile details"],
    textClues: ["date of birth", "father's name", "mobile number", "email address"],
    schema: schema([
      ["name", "Full Name", true, "#fullName, input[name='full_name']", ["assessee name", "taxpayer name"]],
      ["pan", "PAN", true, "#pan, input[name='pan']"],
      ["dob", "Date of Birth", true, "#dob, input[name='dob']", ["birth date"]],
      ["father_name", "Father's Name", true, "#fatherName, input[name='father_name']", ["father name"]],
      ["address", "Address", true, "#address, textarea[name='address']", ["residential address"]],
      ["mobile", "Mobile Number", true, "#mobile, input[name='mobile']", ["phone number"]],
      ["email", "Email Address", true, "#email, input[name='email']"],
    ]),
  },
  {
    key: "salary-schedule",
    keywords: ["salary schedule", "schedule s", "salary income"],
    textClues: ["gross salary", "employer tan", "perquisites", "standard deduction"],
    schema: schema([
      ["employer_name", "Employer Name", true, "#employerName, input[name='employer_name']"],
      ["employer_tan", "Employer TAN", true, "#employerTAN, input[name='employer_tan']", ["tan"]],
      ["gross_salary", "Gross Salary", true, "#grossSalary, input[name='gross_salary']"],
      ["hra", "HRA Received", false, "#hraReceived, input[name='hra']", ["house rent allowance"]],
      ["lta", "LTA Received", false, "#ltaReceived, input[name='lta']", ["leave travel allowance"]],
      ["perquisites", "Perquisites", false, "#perquisites, input[name='perquisites']"],
      ["standard_deduction", "Standard Deduction", false, "#standardDeduction, input[name='standard_deduction']"],
    ]),
  },
  {
    key: "deductions-vi-a",
    keywords: ["deductions vi a", "chapter vi a", "80c", "80d"],
    textClues: ["section 80c", "section 80d", "section 80g", "section 80tta"],
    schema: schema([
      ["section_80c", "Section 80C", false, "#sec80C, input[name='section_80c']"],
      ["section_80ccd_1b", "Section 80CCD(1B)", false, "#sec80CCD1B, input[name='section_80ccd_1b']", ["nps contribution"]],
      ["section_80d_self", "80D Self & Family", false, "#sec80DSelf, input[name='section_80d_self']", ["medical insurance self"]],
      ["section_80d_parents", "80D Parents", false, "#sec80DParents, input[name='section_80d_parents']", ["medical insurance parents"]],
      ["section_80g", "Section 80G", false, "#sec80G, input[name='section_80g']", ["donations"]],
      ["section_80tta", "Section 80TTA", false, "#sec80TTA, input[name='section_80tta']", ["savings interest deduction"]],
    ]),
  },
  {
    key: "other-sources",
    keywords: ["other sources", "interest income", "dividend income"],
    textClues: ["savings interest", "dividend income", "other income"],
    schema: schema([
      ["savings_interest", "Savings Interest", false, "#savingsInterest, input[name='savings_interest']"],
      ["fd_interest", "FD / RD Interest", false, "#fdInterest, input[name='fd_interest']", ["fixed deposit interest"]],
      ["dividend_income", "Dividend Income", false, "#dividendIncome, input[name='dividend_income']"],
      ["other_income", "Other Income", false, "#otherIncome, input[name='other_income']"],
    ]),
  },
  {
    key: "house-property",
    keywords: ["house property", "schedule hp", "rental income"],
    textClues: ["municipal taxes", "interest on borrowed capital", "annual value"],
    schema: schema([
      ["property_type", "Property Type", true, "select[name='property_type'], #propertyType", ["self occupied", "let out"]],
      ["rental_income", "Rental Income", false, "#rentalIncome, input[name='rental_income']", ["gross rent"]],
      ["municipal_taxes", "Municipal Taxes", false, "#municipalTax, input[name='municipal_taxes']"],
      ["home_loan_interest", "Home Loan Interest", false, "#homeLoanInterest, input[name='home_loan_interest']", ["interest on loan"]],
      ["co_owner_details", "Co-owner Details", false, "#coOwnerDetails, [data-field='co_owner_details']", ["co owner"]],
    ]),
  },
  {
    key: "capital-gains",
    keywords: ["capital gains", "schedule cg", "stcg", "ltcg"],
    textClues: ["full value of consideration", "cost of acquisition", "112a", "111a"],
    schema: schema([
      ["stcg_listed_equity", "STCG on Listed Equity", false, "#stcgEquity, input[name='stcg_listed_equity']"],
      ["stcg_other_assets", "STCG on Other Assets", false, "#stcgOther, input[name='stcg_other_assets']"],
      ["ltcg_listed_equity", "LTCG on Listed Equity", false, "#ltcgEquity, input[name='ltcg_listed_equity']"],
      ["ltcg_other_assets", "LTCG on Other Assets", false, "#ltcgOther, input[name='ltcg_other_assets']"],
      ["sale_date", "Date of Sale", false, "input[name='sale_date'], #saleDate", ["transfer date"]],
      ["acquisition_date", "Date of Acquisition", false, "input[name='acquisition_date'], #acquisitionDate", ["purchase date"]],
    ]),
  },
  {
    key: "tax-paid",
    keywords: ["tax paid", "tax details", "tds", "advance tax"],
    textClues: ["tds on salary", "advance tax", "self assessment tax"],
    schema: schema([
      ["tds_salary", "TDS on Salary", true, "#tdsSalary, input[name='tds_salary']"],
      ["tds_other", "TDS on Other Income", false, "#tdsOther, input[name='tds_other']", ["tds other than salary"]],
      ["advance_tax", "Advance Tax", false, "#advanceTax, input[name='advance_tax']"],
      ["self_assessment_tax", "Self Assessment Tax", false, "#selfAssessmentTax, input[name='self_assessment_tax']"],
    ]),
  },
  {
    key: "bank-account",
    keywords: ["bank account", "refund bank", "ifsc"],
    textClues: ["account number", "ifsc code", "prevalidate", "refund credit"],
    schema: schema([
      ["bank_name", "Bank Name", true, "#bankName, input[name='bank_name']"],
      ["account_number", "Account Number", true, "#accountNumber, input[name='account_number']"],
      ["ifsc_code", "IFSC Code", true, "#ifscCode, input[name='ifsc_code']"],
      ["account_type", "Account Type", true, "#accountType, select[name='account_type']"],
    ]),
  },
  {
    key: "regime-choice",
    keywords: ["regime choice", "tax regime", "old regime", "new regime"],
    textClues: ["old regime", "new regime", "115bac"],
    schema: schema([["regime", "Tax Regime", true, "select[name='tax_regime'], #taxRegime, input[name='tax_regime']", ["old tax regime", "new tax regime"]]]),
  },
  {
    key: "summary-review",
    keywords: ["summary review", "review return", "submission summary"],
    textClues: ["gross total income", "taxable income", "refund due", "tax payable"],
    schema: schema([
      ["gross_total_income", "Gross Total Income", false, "#grossTotalIncome, [data-field='gross_total_income']"],
      ["total_deductions", "Total Deductions", false, "#totalDeductions, [data-field='total_deductions']"],
      ["taxable_income", "Taxable Income", false, "#taxableIncome, [data-field='taxable_income']"],
      ["tax_result", "Tax Payable / Refund Due", false, "#taxResult, [data-field='tax_result']", ["refund due", "tax payable"]],
      ["proceed_to_verify", "Proceed to Verification", false, "button[data-testid='proceed-to-verify'], button[aria-label*='verify' i], a[href*='everify']", ["submit return"]],
    ]),
  },
  {
    key: "refund-status",
    keywords: ["refund status", "demand and refund status", "know your refund", "refund banker", "refund reissue"],
    schema: schema([
      ["refund_status", "Refund Status", true, "#refundStatus, [data-testid='refundStatus'], [name='refundStatus'], [data-field='refund_status']"],
      ["refund_amount", "Refund Amount", false, "#refundAmount, [data-testid='refundAmount'], [name='refundAmount'], [data-field='refund_amount']"],
      ["refund_reference", "Refund Reference", false, "#refundReference, [data-testid='refundReference'], [name='refundReference'], [data-field='refund_reference']"],
      ["issued_at", "Issued Date", false, "#refundIssuedAt, [data-testid='refundIssuedAt'], [name='refundIssuedAt'], [data-field='issued_at']"],
      ["processed_at", "Processed Date", false, "#refundProcessedAt, [data-testid='refundProcessedAt'], [name='refundProcessedAt'], [data-field='processed_at']"],
      ["refund_mode", "Refund Mode", false, "#refundMode, [data-testid='refundMode'], [name='refundMode'], [data-field='refund_mode']"],
      ["bank_account_masked", "Bank Account", false, "#refundBankAccount, [data-testid='refundBankAccount'], [name='refundBankAccount'], [data-field='bank_account_masked']"],
    ]),
  },
  {
    key: "everify",
    keywords: ["everify", "e verify", "verification"],
    textClues: ["aadhaar otp", "net banking", "demat account", "bank account"],
    schema: schema([
      ["verification_method", "Verification Method", true, "input[name='verification_method'], select[name='verification_method']", ["verification option"]],
      ["aadhaar_otp", "Aadhaar OTP", false, "button[data-testid='aadhaar-otp'], input[value='aadhaar_otp']"],
      ["net_banking", "Net Banking", false, "button[data-testid='net-banking'], input[value='net_banking']"],
      ["evc_bank_account", "EVC Through Bank Account", false, "button[data-testid='bank-account-evc'], input[value='bank_account_evc']", ["evc through bank"]],
    ]),
  },
];