import { PageAdapter } from "../base";

export const dashboardAdapter: PageAdapter = {
  key: "dashboard",
  detect: (doc) => doc.title.toLowerCase().includes("dashboard"),
  getFormSchema: () => [],
  readValidation: () => []
};
