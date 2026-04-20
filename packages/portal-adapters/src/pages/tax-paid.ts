import { PageAdapter } from "../base";

export const tax_paidAdapter: PageAdapter = {
  key: "tax-paid",
  detect: (doc) => doc.title.toLowerCase().includes("tax paid") || doc.location.href.includes("tax-paid"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
