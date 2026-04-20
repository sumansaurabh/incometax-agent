import { PageAdapter } from "../base";

export const deductions_vi_aAdapter: PageAdapter = {
  key: "deductions-vi-a",
  detect: (doc) => doc.title.toLowerCase().includes("deductions vi a") || doc.location.href.includes("deductions-vi-a"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
