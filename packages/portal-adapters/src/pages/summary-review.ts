import { PageAdapter } from "../base";

export const summary_reviewAdapter: PageAdapter = {
  key: "summary-review",
  detect: (doc) => doc.title.toLowerCase().includes("summary review") || doc.location.href.includes("summary-review"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
