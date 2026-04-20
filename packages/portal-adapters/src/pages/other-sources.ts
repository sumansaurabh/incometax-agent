import { PageAdapter } from "../base";

export const other_sourcesAdapter: PageAdapter = {
  key: "other-sources",
  detect: (doc) => doc.title.toLowerCase().includes("other sources") || doc.location.href.includes("other-sources"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
