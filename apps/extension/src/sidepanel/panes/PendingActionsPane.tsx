import React from "react";

import { ApprovalItem, ExecutionRecord, FillPlan } from "../backend";

type Props = {
  page: string;
  fillPlan: FillPlan | null;
  approvals: ApprovalItem[];
  approvedActionCount: number;
  lastExecution: ExecutionRecord | null;
  isBusy: boolean;
  reviewerEmail: string;
  onReviewerEmailChange: (value: string) => void;
  onPreparePage: () => void;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
  onRequestReviewerSignoff: (approvalId: string) => void;
  onCounterConsentReviewerSignoff: (signoffId: string) => void;
  onExecute: () => void;
  onUndo: () => void;
};

function formatValue(value: unknown, formattedValue?: string): string {
  if (formattedValue) {
    return formattedValue;
  }
  if (value === null || value === undefined || value === "") {
    return "(empty)";
  }
  return String(value);
}

export function PendingActionsPane({
  page,
  fillPlan,
  approvals,
  approvedActionCount,
  lastExecution,
  isBusy,
  reviewerEmail,
  onReviewerEmailChange,
  onPreparePage,
  onApprove,
  onReject,
  onRequestReviewerSignoff,
  onCounterConsentReviewerSignoff,
  onExecute,
  onUndo,
}: Props): JSX.Element {
  const canPrepare = page !== "unknown" && !isBusy;
  const reviewerBlocked = approvals.some(
    (approval) => Boolean(approval.signoffId) && approval.reviewerStatus !== "client_approved" && approval.status === "approved"
  );
  const canExecute = approvedActionCount > 0 && (fillPlan?.total_actions ?? 0) > 0 && !isBusy && !reviewerBlocked;
  const canUndo = Boolean(lastExecution && lastExecution.execution_kind === "fill" && lastExecution.success && !isBusy);

  return (
    <section>
      <h3>Pending Actions</h3>
      <p>Current page: {page}</p>
      <button disabled={!canPrepare} onClick={onPreparePage}>
        Prepare Current Page
      </button>

      {fillPlan && fillPlan.total_actions > 0 ? (
        <>
          <p>
            Fill plan ready: {fillPlan.total_actions} actions across {fillPlan.pages.length} page(s)
          </p>
          <ul>
            {fillPlan.pages.flatMap((pageItem) =>
              pageItem.actions.map((action) => (
                <li key={action.action_id}>
                  {action.field_label} → {formatValue(action.value, action.formatted_value)}
                </li>
              ))
            )}
          </ul>
        </>
      ) : (
        <p>No prepared write actions yet.</p>
      )}

      {approvals.length > 0 ? (
        <>
          <label>
            Reviewer email
            <input
              type="email"
              value={reviewerEmail}
              onChange={(event) => onReviewerEmailChange(event.target.value)}
              placeholder="ca@example.com"
            />
          </label>
          <ul>
            {approvals.map((approval) => (
              <li key={approval.approvalId}>
                <strong>{approval.description}</strong>
                <div>Status: {approval.status}</div>
                <div>Scope: {approval.kind}</div>
                <div>Actions: {approval.actionIds.length}</div>
                <div>Reviewer sign-off: {approval.reviewerStatus ?? "not requested"}</div>
                {approval.reviewerEmail ? <div>Reviewer: {approval.reviewerEmail}</div> : null}
                {approval.reviewerNote ? <div>Reviewer note: {approval.reviewerNote}</div> : null}
                {approval.clientNote ? <div>Client note: {approval.clientNote}</div> : null}
                {approval.status === "pending" ? (
                  <div>
                    <button disabled={isBusy} onClick={() => onApprove(approval.approvalId)}>
                      Approve
                    </button>
                    <button disabled={isBusy} onClick={() => onReject(approval.approvalId)}>
                      Reject
                    </button>
                  </div>
                ) : null}
                {!approval.signoffId ? (
                  <button disabled={isBusy || !reviewerEmail.trim()} onClick={() => onRequestReviewerSignoff(approval.approvalId)}>
                    Request reviewer sign-off
                  </button>
                ) : null}
                {approval.signoffId && approval.reviewerStatus === "reviewer_approved" ? (
                  <button disabled={isBusy} onClick={() => onCounterConsentReviewerSignoff(approval.signoffId as string)}>
                    Counter-consent reviewer sign-off
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <button disabled={!canExecute} onClick={onExecute}>
        Execute Approved Actions
      </button>
      {reviewerBlocked ? <p>Execution is waiting for reviewer sign-off and client counter-consent.</p> : null}
      <button disabled={!canUndo} onClick={onUndo}>
        Undo Last Batch
      </button>

      {lastExecution ? (
        <p>
          Last execution: {lastExecution.execution_kind} / {lastExecution.success ? "success" : "failure"}
        </p>
      ) : null}
    </section>
  );
}
