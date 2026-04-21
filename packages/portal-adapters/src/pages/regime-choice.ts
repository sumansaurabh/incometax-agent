import { PageAdapter } from "../base";
import { readDefaultValidation } from "../base";

export const regime_choiceAdapter: PageAdapter = {
  key: "regime-choice",
  detect: (doc) => doc.title.toLowerCase().includes("regime choice") || doc.location.href.includes("regime-choice"),
  getFormSchema: () => [
    {
      key: "regime",
      label: "Tax Regime",
      required: true,
      selectorHint: "select[name='tax_regime'], #taxRegime, input[name='tax_regime']",
    },
  ],
  readValidation: (doc) => readDefaultValidation(doc),
};
