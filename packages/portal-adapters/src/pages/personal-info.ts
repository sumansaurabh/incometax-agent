import { PageAdapter } from "../base";

export const personal_infoAdapter: PageAdapter = {
  key: "personal-info",
  detect: (doc) => doc.title.toLowerCase().includes("personal info") || doc.location.href.includes("personal-info"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
