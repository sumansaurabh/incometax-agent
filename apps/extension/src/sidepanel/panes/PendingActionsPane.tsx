import React from "react";

import { ApprovalItem, ExecutionRecord, FillPlan } from "../backend";

type Props = {
  page: string;
  fillPlan: FillPlan | null;
  approvals: ApprovalItem[];
  approvedActionCount: number;
  lastExecution: ExecutionRecord | null;
  isBusy: boolean;
  onPreparePage: () => void;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
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
  onPreparePage,
  onApprove,
  onReject,
  onExecute,
  onUndo,
}: Props): JSX.Element {
  const canPrepare = page !== "unknown" && !isBusy;
  const canExecute = approvedActionCount > 0 && (fillPlan?.total_actions ?? 0) > 0 && !isBusy;
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
        <ul>
          {approvals.map((approval) => (
            <li key={approval.approvalId}>
              <strong>{approval.description}</strong>
              <div>Status: {approval.status}</div>
              <div>Scope: {approval.kind}</div>
              <div>Actions: {approval.actionIds.length}</div>
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
            </li>
          ))}
        </ul>
      ) : null}

      <button disabled={!canExecute} onClick={onExecute}>
        Execute Approved Actions
      </button>
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
