import React from "react";

type ValidationHelpItem = {
  field: string;
  field_label: string;
  message: string;
  plain_english: string;
  suggested_fix: string;
  question: string;
  severity: string;
  suggested_value?: string | null;
  recovery_mode?: string;
  recovery_actions?: string[];
  page_drift_count?: number;
};

type RegimePreview = {
  current_regime: string;
  recommended_regime: string;
  delta_vs_current: number;
  old_regime: { refund_due: number; tax_payable: number; total_deductions: number };
  new_regime: { refund_due: number; tax_payable: number; total_deductions: number };
  rationale: string[];
};

type DetectedField = {
  key: string;
  label: string;
  required: boolean;
  selectorHint?: string;
};

type ValidationError = {
  field: string;
  message: string;
};

type Props = {
  page: string;
  fields: DetectedField[];
  validationErrors: ValidationError[];
  validationHelp: ValidationHelpItem[];
  regimePreview: RegimePreview | null;
  isBusy: boolean;
  onRefreshRegimePreview: () => void;
  onPrepareRecommendedRegime: () => void;
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function DetectedDetailsPane({
  page,
  fields,
  validationErrors,
  validationHelp,
  regimePreview,
  isBusy,
  onRefreshRegimePreview,
  onPrepareRecommendedRegime,
}: Props): JSX.Element {
  return (
    <section>
      <h3>Detected Step</h3>
      <p>{page}</p>
      <p>Detected fields: {fields.length}</p>
      {fields.length > 0 ? (
        <ul>
          {fields.slice(0, 6).map((field) => (
            <li key={field.key}>
              {field.label}
              {field.required ? " (required)" : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {validationErrors.length > 0 ? (
        <>
          <h4>Validation Errors</h4>
          <ul>
            {validationErrors.map((error, idx) => (
              <li key={`${error.field}-${idx}`}>{error.message}</li>
            ))}
          </ul>
        </>
      ) : null}
      {validationHelp.length > 0 ? (
        <>
          <h4>What The Portal Means</h4>
          <ul>
            {validationHelp.map((item, idx) => (
              <li key={`${item.field}-${idx}`}>
                <strong>{item.field_label}:</strong> {item.plain_english} {item.suggested_fix}
                {item.recovery_mode ? <p>Recovery mode: {item.recovery_mode}</p> : null}
                {item.page_drift_count ? <p>Known drift events on this page: {item.page_drift_count}</p> : null}
                {item.recovery_actions?.length ? (
                  <ul>
                    {item.recovery_actions.map((action) => (
                      <li key={action}>{action}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {page === "regime-choice" ? (
        <>
          <h4>Regime Comparison</h4>
          <button disabled={isBusy} onClick={onRefreshRegimePreview}>
            Compare old vs new regime
          </button>
          {regimePreview ? (
            <>
              <p>
                Current: {regimePreview.current_regime} / Recommended: {regimePreview.recommended_regime}
              </p>
              <ul>
                <li>Old regime: refund {formatCurrency(regimePreview.old_regime.refund_due)} / payable {formatCurrency(regimePreview.old_regime.tax_payable)}</li>
                <li>New regime: refund {formatCurrency(regimePreview.new_regime.refund_due)} / payable {formatCurrency(regimePreview.new_regime.tax_payable)}</li>
                <li>Delta vs current: {formatCurrency(Math.abs(regimePreview.delta_vs_current))}</li>
              </ul>
              <ul>
                {regimePreview.rationale.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <button disabled={isBusy || regimePreview.current_regime === regimePreview.recommended_regime} onClick={onPrepareRecommendedRegime}>
                Prepare recommended regime switch
              </button>
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
