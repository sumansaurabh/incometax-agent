import React, { useState } from "react";

import { VerdictCardData, VerdictEvidenceAction, VerdictEvidenceItem } from "../backend";

type ResolveInput = {
  code: string;
  itemId: string;
  status: "acknowledged" | "resolved" | "open";
  actionKind?: string;
  note?: string;
  acceptedValue?: number | string | null;
};

type Props = {
  data: VerdictCardData;
  onResolve?: (input: ResolveInput) => Promise<void> | void;
  onAction?: (kind: string, code: string) => void;
  defaultOpen?: boolean;
  busy?: boolean;
};

const severityClass: Record<string, string> = {
  high: "verdict-sev-high",
  medium: "verdict-sev-medium",
  warning: "verdict-sev-medium",
  error: "verdict-sev-high",
  low: "verdict-sev-low",
};

function severityClassOf(sev: string): string {
  return severityClass[String(sev).toLowerCase()] ?? "verdict-sev-medium";
}

function statusLabel(status: string): string {
  if (status === "resolved") return "Resolved";
  if (status === "acknowledged") return "Acknowledged";
  return "Open";
}

export function VerdictCard({ data, onResolve, onAction, defaultOpen = true, busy = false }: Props): JSX.Element {
  const [expanded, setExpanded] = useState(defaultOpen);
  const [localBusyItem, setLocalBusyItem] = useState<string | null>(null);

  const { verdict, evidence, actions, trail } = data;

  const handleEvidenceAction = async (item: VerdictEvidenceItem, action: VerdictEvidenceAction) => {
    if (!onResolve) return;
    const nextStatus: ResolveInput["status"] =
      action.kind === "acknowledge"
        ? "acknowledged"
        : action.kind === "open"
          ? "open"
          : "resolved";

    let note: string | undefined;
    if (action.prompts_for_note) {
      const entered = typeof window !== "undefined" ? window.prompt("Add a note for this mismatch (visible in the audit trail):", "") : null;
      if (entered === null) return;
      const trimmed = entered.trim();
      if (!trimmed) {
        if (typeof window !== "undefined") window.alert("Note cannot be empty. Use 'Mark reviewed' if no note is needed.");
        return;
      }
      note = trimmed;
    }

    if (action.kind === "accept_ais" || action.kind === "accept_doc") {
      const label = action.kind === "accept_ais" ? "AIS" : "document";
      if (typeof window !== "undefined" && !window.confirm(`Use ${label} value ${String(action.value ?? "")} as the filing truth for this field?`)) {
        return;
      }
    }

    setLocalBusyItem(item.id);
    try {
      await onResolve({
        code: item.code,
        itemId: item.id,
        status: nextStatus,
        actionKind: action.kind,
        note,
        acceptedValue: action.value ?? null,
      });
    } finally {
      setLocalBusyItem(null);
    }
  };

  return (
    <article className={`verdict-card ${severityClassOf(verdict.severity)}`}>
      <header className="verdict-card-header">
        <button
          type="button"
          className="verdict-card-toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          <span className={`verdict-pill ${severityClassOf(verdict.severity)}`}>{verdict.severity}</span>
          <span className="verdict-card-title">{verdict.title}</span>
          {verdict.is_mode_trigger ? (
            <span className="verdict-trigger-badge" title={`This reason forces mode: ${verdict.mode_impact}`}>
              triggers {verdict.mode_impact}
            </span>
          ) : null}
          <span className="verdict-caret">{expanded ? "▾" : "▸"}</span>
        </button>
      </header>
      {expanded ? (
        <div className="verdict-card-body">
          <p className="verdict-detail">{verdict.detail}</p>

          {evidence.length > 0 ? (
            <ul className="verdict-evidence-list">
              {evidence.map((item) => {
                const isBusy = busy || localBusyItem === item.id;
                return (
                  <li key={item.id} className={`verdict-evidence-item status-${item.status}`}>
                    <div className="verdict-evidence-summary">
                      <span className={`verdict-pill ${severityClassOf(item.severity)}`}>{item.severity}</span>
                      <span className="verdict-evidence-text">{item.summary}</span>
                      <span className="verdict-status-chip">{statusLabel(item.status)}</span>
                    </div>
                    {item.resolvable ? (
                      <div className="verdict-evidence-actions">
                        {item.actions.map((action) => (
                          <button
                            key={action.id}
                            type="button"
                            disabled={isBusy}
                            className={`verdict-action verdict-action-${action.kind}`}
                            onClick={() => handleEvidenceAction(item, action)}
                          >
                            {action.label}
                            {action.requires_approval ? " *" : ""}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {item.resolution ? (
                      <div className="verdict-resolution-note">
                        {item.resolution.actor_email ? `Resolved by ${item.resolution.actor_email}` : "Resolved"}
                        {item.resolution.at ? ` · ${new Date(item.resolution.at).toLocaleString()}` : ""}
                        {item.resolution.note ? ` · ${item.resolution.note}` : ""}
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="verdict-evidence-empty">No structured evidence attached to this finding.</p>
          )}

          {actions.length > 0 ? (
            <div className="verdict-card-actions">
              {actions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  className={`verdict-action verdict-action-secondary verdict-action-${action.kind}`}
                  disabled={busy}
                  onClick={() => onAction?.(action.kind, verdict.code)}
                >
                  {action.label}
                </button>
              ))}
            </div>
          ) : null}

          {trail.length > 0 ? (
            <details className="verdict-trail">
              <summary>Audit trail ({trail.length})</summary>
              <ol>
                {trail.map((entry, index) => (
                  <li key={`${entry.at ?? index}-${entry.actor ?? index}`}>
                    <span className="verdict-trail-actor">{entry.actor ?? "system"}</span>
                    {" · "}
                    <span className="verdict-trail-verb">{entry.verb ?? "event"}</span>
                    {entry.at ? ` · ${new Date(entry.at).toLocaleString()}` : ""}
                    {entry.note ? ` — ${entry.note}` : ""}
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
