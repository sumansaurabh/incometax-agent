import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";

import { detectAdapter } from "../src/registry";

const fixtureDir = join(dirname(fileURLToPath(import.meta.url)), "fixtures");

function loadFixture(name: string, url: string): Document {
  const html = readFileSync(join(fixtureDir, `${name}.html`), "utf8");
  return new JSDOM(html, { url }).window.document;
}

function assertFieldSelector(doc: Document, fields: Array<{ key: string; selectorHint?: string }>, key: string): void {
  const field = fields.find((item) => item.key === key);
  assert.ok(field, `expected field ${key} to be present`);
  assert.ok(field?.selectorHint, `expected field ${key} to resolve a selector`);
  assert.ok(doc.querySelector(field?.selectorHint ?? ""), `expected selector ${field?.selectorHint} for ${key} to match the fixture DOM`);
}

const fixtureCases = [
  {
    fixture: "login",
    url: "https://www.incometax.gov.in/iec/foportal/login",
    page: "login",
    keys: ["pan_or_aadhaar", "password", "otp"],
  },
  {
    fixture: "dashboard",
    url: "https://www.incometax.gov.in/iec/foportal/dashboard",
    page: "dashboard",
    keys: ["start_filing", "view_returns", "refund_status"],
  },
  {
    fixture: "file-return-start",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/start",
    page: "file-return-start",
    keys: ["assessment_year", "filing_type", "filing_mode"],
  },
  {
    fixture: "itr-selection",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/select-itr",
    page: "itr-selection",
    keys: ["itr_type", "residential_status", "income_profile"],
  },
  {
    fixture: "personal-info",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/personal-info",
    page: "personal-info",
    keys: ["name", "pan", "dob", "father_name", "address", "mobile", "email"],
  },
  {
    fixture: "salary-schedule",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/schedule-s",
    page: "salary-schedule",
    keys: ["employer_name", "employer_tan", "gross_salary", "hra", "standard_deduction"],
  },
  {
    fixture: "deductions-vi-a",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/deductions",
    page: "deductions-vi-a",
    keys: ["section_80c", "section_80ccd_1b", "section_80d_self", "section_80g", "section_80tta"],
  },
  {
    fixture: "tax-paid",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/tax-paid",
    page: "tax-paid",
    keys: ["tds_salary", "tds_other", "advance_tax", "self_assessment_tax"],
  },
  {
    fixture: "bank-account",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/bank-account",
    page: "bank-account",
    keys: ["bank_name", "account_number", "ifsc_code", "account_type"],
  },
  {
    fixture: "summary-review",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/summary",
    page: "summary-review",
    keys: ["gross_total_income", "total_deductions", "taxable_income", "tax_result", "proceed_to_verify"],
  },
  {
    fixture: "everify",
    url: "https://www.incometax.gov.in/iec/foportal/file-return/everify",
    page: "everify",
    keys: ["verification_method", "aadhaar_otp", "net_banking", "evc_bank_account"],
  },
] as const;

for (const scenario of fixtureCases) {
  test(`detects ${scenario.page} from ${scenario.fixture} fixture`, () => {
    const doc = loadFixture(scenario.fixture, scenario.url);
    const adapter = detectAdapter(doc);

    assert.ok(adapter, `expected adapter for ${scenario.fixture}`);
    assert.equal(adapter?.key, scenario.page);

    const schema = adapter?.getFormSchema(doc) ?? [];
    for (const key of scenario.keys) {
      assertFieldSelector(doc, schema, key);
    }
  });
}

test("does not mis-detect an unrelated page", () => {
  const doc = loadFixture("unrelated", "https://www.incometax.gov.in/iec/foportal/help");
  const adapter = detectAdapter(doc);

  assert.equal(adapter, null);
});