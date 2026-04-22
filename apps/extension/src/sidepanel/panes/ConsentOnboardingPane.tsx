import React from "react";

type ConsentCatalogItem = {
  purpose: string;
  title: string;
  required: boolean;
  category?: string;
  depends_on?: string[];
  description: string;
  consent_text: string;
  scope?: Record<string, unknown>;
};

function formatScope(scope?: Record<string, unknown>): string {
  if (!scope) {
    return "";
  }
  return Object.entries(scope)
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
    .join(" / ");
}

type Props = {
  items: ConsentCatalogItem[];
  activePurposes: Set<string>;
  selectedPurposes: Set<string>;
  isBusy: boolean;
  onTogglePurpose: (purpose: string) => void;
  onGrantSelected: () => void;
};

export function ConsentOnboardingPane({
  items,
  activePurposes,
  selectedPurposes,
  isBusy,
  onTogglePurpose,
  onGrantSelected,
}: Props): JSX.Element {
  const missingRequired = items.filter((item) => item.required && !activePurposes.has(item.purpose));

  return (
    <section>
      <h3>Consent Setup</h3>
      <p>
        Grant the filing purposes you want enabled for this thread before the agent prepares fills, reviewer handoffs,
        or submission workflow steps.
      </p>
      {missingRequired.length > 0 ? (
        <p>Required before guided filing continues: {missingRequired.map((item) => item.title).join(", ")}.</p>
      ) : (
        <p>All required onboarding consents are active for this thread.</p>
      )}
      <ul>
        {items.map((item) => {
          const active = activePurposes.has(item.purpose);
          const checked = active || selectedPurposes.has(item.purpose) || item.required;
          return (
            <li key={item.purpose}>
              <label>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={active || item.required || isBusy}
                  onChange={() => onTogglePurpose(item.purpose)}
                />
                {item.title} {item.required ? "(required)" : "(optional)"}
              </label>
              {item.category ? <p>Category: {item.category}</p> : null}
              {item.depends_on?.length ? <p>Depends on: {item.depends_on.join(", ")}</p> : null}
              <p>{item.description}</p>
              {item.scope ? <p>Scope: {formatScope(item.scope)}</p> : null}
              <p>{active ? "Already granted for this thread." : item.consent_text}</p>
            </li>
          );
        })}
      </ul>
      <button disabled={isBusy || missingRequired.length === 0 && selectedPurposes.size === 0} onClick={onGrantSelected}>
        Grant selected consents
      </button>
    </section>
  );
}