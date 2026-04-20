import { PageAdapter } from "./base";
import { dashboardAdapter } from "./pages/dashboard";
import { file_return_startAdapter } from "./pages/file-return-start";
import { itr_selectionAdapter } from "./pages/itr-selection";
import { personal_infoAdapter } from "./pages/personal-info";
import { salary_scheduleAdapter } from "./pages/salary-schedule";
import { deductions_vi_aAdapter } from "./pages/deductions-vi-a";
import { tax_paidAdapter } from "./pages/tax-paid";
import { summary_reviewAdapter } from "./pages/summary-review";

const adapters: PageAdapter[] = [
  dashboardAdapter,
  file_return_startAdapter,
  itr_selectionAdapter,
  personal_infoAdapter,
  salary_scheduleAdapter,
  deductions_vi_aAdapter,
  tax_paidAdapter,
  summary_reviewAdapter
];

export function detectAdapter(doc: Document): PageAdapter | null {
  return adapters.find((adapter) => adapter.detect(doc)) ?? null;
}

export { adapters };
