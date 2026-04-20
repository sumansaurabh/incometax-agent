import { PageAdapter } from "../base";

export const loginAdapter: PageAdapter = {
  key: "login",
  detect: (doc) => doc.title.toLowerCase().includes("login") || doc.location.href.includes("login"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
