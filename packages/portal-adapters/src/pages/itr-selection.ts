import { PageAdapter } from "../base";

export const itr_selectionAdapter: PageAdapter = {
  key: "itr-selection",
  detect: (doc) => doc.title.toLowerCase().includes("itr selection") || doc.location.href.includes("itr-selection"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
