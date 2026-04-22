import React, { useState } from "react";

export type ProposalAction = {
  action_id: string;
  field_id: string;
  field_label: string;
  selector: string;
  value: unknown;
  formatted_value: string;
  confidence: number;
  confidence_level: "high" | "medium" | "low";
  source_document?: string | null;
  requires_approval: boolean;
};

export type ProposalPage = {
  page_type: string;
  page_title: string;
  actions: ProposalAction[];
};

export type ProposalCard = {
  proposal_id: string;
  approval_key: string;
  status: string;
  sensitivity?: string | null;
  expires_at?: string | null;
  total_actions?: number;
  high_confidence_actions?: number;
  low_confidence_actions?: number;
  pages: ProposalPage[];
  message?: string | null;
};

type Props = {
  proposal: ProposalCard;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onDecision: (input: { proposalId: string; approvalKey: string; approved: boolean; reason?: string }) => Promise<any>;
  disabled?: boolean;
};

const confidenceIcon = (level: string): string => {
  if (level === "high") return "●";
  if (level === "medium") return "◐";
  return "○";
};

/**
 * Renders a form-fill proposal returned by the agent's `propose_fill` tool.
 *
 * The card is a read-only preview until the user clicks Approve or Reject — the agent cannot
 * touch the portal by itself. Approve dispatches the backend decision (which updates the
 * underlying approval row); the extension's content script is responsible for executing the
 * actions against the real portal after the backend confirms approval.
 */
export function DiffCard({ proposal, onDecision, disabled = false }: Props): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string>(proposal.status);
  const [error, setError] = useState<string | null>(null);

  const decide = async (approved: boolean, reason?: string): Promise<void> => {
    if (busy || disabled) return;
    setBusy(true);
    setError(null);
    try {
      const result = await onDecision({
        proposalId: proposal.proposal_id,
        approvalKey: proposal.approval_key,
        approved,
        reason,
      });
      const nextStatus = result?.approval_status ?? (approved ? "approved" : "rejected");
      setStatus(nextStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record your decision.");
    } finally {
      setBusy(false);
    }
  };

  const terminal = status === "approved" || status === "rejected";
  const totalActions = proposal.total_actions ?? proposal.pages.reduce((sum, p) => sum + p.actions.length, 0);

  return (
    <article
      className={`diff-card diff-card-${proposal.sensitivity ?? "standard"}`}
      data-proposal-id={proposal.proposal_id}
    >
      <header className="diff-card-header">
        <div>
          <strong>Fill proposal</strong>
          <span className="diff-card-subtitle">
            {totalActions} field{totalActions === 1 ? "" : "s"}
            {proposal.high_confidence_actions != null
              ? ` · ${proposal.high_confidence_actions} high-confidence`
              : null}
            {proposal.sensitivity === "high" ? " · sensitive" : null}
          </span>
        </div>
        <span className={`diff-card-status diff-card-status-${status}`}>{status.replace(/_/g, " ")}</span>
      </header>

      {proposal.message ? <p className="diff-card-message">{proposal.message}</p> : null}

      {proposal.pages.map((page) => (
        <section key={page.page_type} className="diff-card-page">
          <h4>{page.page_title}</h4>
          <ul className="diff-card-actions">
            {page.actions.map((action) => (
              <li key={action.action_id} className={`diff-card-action diff-card-action-${action.confidence_level}`}>
                <span className="diff-card-action-icon" aria-hidden="true">
                  {confidenceIcon(action.confidence_level)}
                </span>
                <div className="diff-card-action-body">
                  <div className="diff-card-action-label">{action.field_label}</div>
                  <div className="diff-card-action-value">{action.formatted_value}</div>
                  {action.source_document ? (
                    <div className="diff-card-action-source">From {action.source_document}</div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {proposal.expires_at ? (
        <p className="diff-card-expiry">Expires {new Date(proposal.expires_at).toLocaleString()}</p>
      ) : null}

      {error ? <p className="diff-card-error" role="alert">{error}</p> : null}

      <footer className="diff-card-footer">
        <button
          type="button"
          className="diff-card-button diff-card-button-primary"
          onClick={() => decide(true)}
          disabled={busy || terminal || disabled}
        >
          {busy && status !== "rejected" ? "Approving…" : terminal && status === "approved" ? "Approved" : "Approve"}
        </button>
        <button
          type="button"
          className="diff-card-button diff-card-button-secondary"
          onClick={() => decide(false, "user_declined")}
          disabled={busy || terminal || disabled}
        >
          {terminal && status === "rejected" ? "Rejected" : "Reject"}
        </button>
      </footer>
    </article>
  );
}
