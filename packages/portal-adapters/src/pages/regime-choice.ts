import { PageAdapter } from "../base";

export const regime_choiceAdapter: PageAdapter = {
  key: "regime-choice",
  detect: (doc) => doc.title.toLowerCase().includes("regime choice") || doc.location.href.includes("regime-choice"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
