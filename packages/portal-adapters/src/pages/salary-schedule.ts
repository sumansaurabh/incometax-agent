import { PageAdapter } from "../base";

export const salary_scheduleAdapter: PageAdapter = {
  key: "salary-schedule",
  detect: (doc) => doc.title.toLowerCase().includes("salary schedule") || doc.location.href.includes("salary-schedule"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
