import { PageAdapter } from "../base";

export const everifyAdapter: PageAdapter = {
  key: "everify",
  detect: (doc) => doc.title.toLowerCase().includes("everify") || doc.location.href.includes("everify"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
