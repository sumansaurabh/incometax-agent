import { PageAdapter } from "../base";

export const file_return_startAdapter: PageAdapter = {
  key: "file-return-start",
  detect: (doc) => doc.title.toLowerCase().includes("file return start") || doc.location.href.includes("file-return-start"),
  getFormSchema: () => [],
  readValidation: (doc) =>
    Array.from(doc.querySelectorAll(".error, .validation-error")).map((node) => ({
      field: "unknown",
      message: node.textContent?.trim() ?? ""
    }))
};
