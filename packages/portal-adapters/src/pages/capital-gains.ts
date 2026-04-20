import { PageAdapter } from "../base";

export const capital_gainsAdapter: PageAdapter = {
  key: "capital-gains",
  detect: (doc) => doc.title.toLowerCase().includes("capital gains") || doc.location.href.includes("capital-gains"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
