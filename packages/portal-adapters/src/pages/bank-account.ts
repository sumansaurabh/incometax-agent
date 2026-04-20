import { PageAdapter } from "../base";

export const bank_accountAdapter: PageAdapter = {
  key: "bank-account",
  detect: (doc) => doc.title.toLowerCase().includes("bank account") || doc.location.href.includes("bank-account"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
