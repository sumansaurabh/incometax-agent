export type PortalPageKey =
  | "dashboard"
  | "file-return-start"
  | "itr-selection"
  | "personal-info"
  | "salary-schedule"
  | "deductions-vi-a"
  | "tax-paid"
  | "summary-review"
  | "unknown";

export function detectPage(documentTitle: string): PortalPageKey {
  const title = documentTitle.toLowerCase();
  if (title.includes("dashboard")) return "dashboard";
  if (title.includes("file return")) return "file-return-start";
  if (title.includes("itr")) return "itr-selection";
  if (title.includes("personal")) return "personal-info";
  if (title.includes("salary")) return "salary-schedule";
  if (title.includes("deduction")) return "deductions-vi-a";
  if (title.includes("tax paid")) return "tax-paid";
  if (title.includes("summary")) return "summary-review";
  return "unknown";
}
