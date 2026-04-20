import { PageAdapter } from "../base";

export const house_propertyAdapter: PageAdapter = {
  key: "house-property",
  detect: (doc) => doc.title.toLowerCase().includes("house property") || doc.location.href.includes("house-property"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
