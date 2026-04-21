import React, { useEffect, useState } from "react";

import {
  ApprovalItem,
  DetectedField,
  ExecutionRecord,
  FillAction,
  FillPlan,
  PageContextPayload,
  ValidationError,
  createProposal,
  decideApproval,
  ensureThread,
  fetchTaxFacts,
  fetchThreadActions,
  normalizeApprovalItems,
  recordExecution,
  undoExecution,
} from "./backend";
import { ChatPane } from "./panes/ChatPane";
import { DetectedDetailsPane } from "./panes/DetectedDetailsPane";
import { PendingActionsPane } from "./panes/PendingActionsPane";
import { EvidencePane } from "./panes/EvidencePane";
import { SidepanelSession, createSidepanelUserId, loadSidepanelSession, saveSidepanelSession } from "./session";

type EvidenceSource = {
  documentId: string;
  documentName: string;
  documentType: "form16" | "ais" | "tis" | "form16a" | "bank_statement" | "other";
  snippet?: string;
};

type EvidenceFact = {
  factId: string;
  fieldName: string;
  displayLabel: string;
  value: string | number;
  formattedValue: string;
  category: "income" | "deduction" | "tax_paid" | "personal" | "bank";
  confidence: number;
  extractorVersion: string;
  sources: EvidenceSource[];
  validationStatus: "valid" | "warning" | "error" | "unverified";
  lastUpdated: string;
};

type RuntimeResponse<T> = {
  ok: boolean;
  payload?: T;
  error?: string;
};

type ActionBatchPayload = {
  results: Array<{
    action: { type: string; selector: string; value?: string };
    output: unknown;
    readAfterWrite?: { ok: boolean; observedValue: string };
  }>;
  validationErrors: ValidationError[];
  pageContext: PageContextPayload;
};

function mapDocumentType(value: unknown): EvidenceSource["documentType"] {
  const documentType = String(value ?? "other").toLowerCase();
  if (documentType.startsWith("ais")) return "ais";
  if (documentType.startsWith("tis")) return "tis";
  if (documentType === "form16") return "form16";
  if (documentType === "form16a") return "form16a";
  if (documentType.includes("bank")) return "bank_statement";
  return "other";
}

function inferCategory(path: string): EvidenceFact["category"] {
  if (path.startsWith("deductions")) return "deduction";
  if (path.startsWith("tax_paid")) return "tax_paid";
  if (path.startsWith("bank")) return "bank";
  if (["name", "pan", "dob", "father_name", "mobile", "email"].includes(path)) return "personal";
  return "income";
}

function formatFactValue(path: string, value: unknown): string {
  if (typeof value === "number" && !["pan", "mobile", "ifsc"].includes(path.split(".").at(-1) ?? "")) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
  }
  return String(value);
}

function flattenFacts(
  value: Record<string, unknown>,
  factEvidence: Record<string, Array<Record<string, unknown>>>,
  prefix = ""
): EvidenceFact[] {
  return Object.entries(value).flatMap(([key, nestedValue]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (nestedValue && typeof nestedValue === "object" && !Array.isArray(nestedValue)) {
      return flattenFacts(nestedValue as Record<string, unknown>, factEvidence, path);
    }

    const evidenceEntries = factEvidence[path] ?? [];
    const primaryEvidence = evidenceEntries[0] ?? {};
    return [
      {
        factId: path,
        fieldName: path,
        displayLabel: key.replace(/_/g, " "),
        value: typeof nestedValue === "number" || typeof nestedValue === "string" ? nestedValue : JSON.stringify(nestedValue),
        formattedValue: formatFactValue(path, nestedValue),
        category: inferCategory(path),
        confidence: Number(primaryEvidence.confidence ?? 0.8),
        extractorVersion: String(primaryEvidence.extractor_version ?? "phase2"),
        sources: evidenceEntries.map((entry, index) => ({
          documentId: String(entry.document_id ?? `${path}-${index}`),
          documentName: String(entry.document_name ?? entry.document_type ?? "Document"),
          documentType: mapDocumentType(entry.document_type),
          snippet: typeof entry.snippet === "string" ? entry.snippet : undefined,
        })),
        validationStatus: Number(primaryEvidence.confidence ?? 0.8) >= 0.9 ? "valid" : "unverified",
        lastUpdated: new Date().toISOString(),
      },
    ];
  });
}

function flattenPlanActions(fillPlan: FillPlan | null): FillAction[] {
  if (!fillPlan) {
    return [];
  }
  return fillPlan.pages.flatMap((page) => page.actions.map((action) => ({ ...action, page_type: action.page_type ?? page.page_type })));
}

async function sendRuntimeMessage<T>(message: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response: T) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(response);
    });
  });
}

export default function App(): JSX.Element {
  const [messages, setMessages] = useState<string[]>(["IncomeTax Agent ready."]);
  const [page, setPage] = useState("unknown");
  const [detectedFields, setDetectedFields] = useState<DetectedField[]>([]);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [pageContext, setPageContext] = useState<PageContextPayload | null>(null);
  const [facts, setFacts] = useState<EvidenceFact[]>([]);
  const [session, setSession] = useState<SidepanelSession | null>(null);
  const [fillPlan, setFillPlan] = useState<FillPlan | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [approvedActions, setApprovedActions] = useState<string[]>([]);
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [isBusy, setIsBusy] = useState(false);

  const appendMessage = (message: string) => {
    setMessages((prev) => [...prev, message]);
  };

  const applyPageContext = (context: PageContextPayload) => {
    setPageContext(context);
    setPage(context.page ?? "unknown");
    setDetectedFields(context.fields ?? []);
    setValidationErrors(context.validationErrors ?? []);
  };

  const refreshSnapshot = async (): Promise<PageContextPayload | null> => {
    try {
      const response = await sendRuntimeMessage<RuntimeResponse<PageContextPayload>>({ type: "snapshot_active_page", payload: {} });
      if (!response.ok || !response.payload) {
        return null;
      }
      applyPageContext(response.payload);
      return response.payload;
    } catch (error: unknown) {
      appendMessage(`Snapshot unavailable: ${error instanceof Error ? error.message : "unknown error"}`);
      return null;
    }
  };

  const refreshBackendState = async (threadId: string) => {
    const [actionsPayload, taxFactsPayload] = await Promise.all([
      fetchThreadActions(threadId),
      fetchTaxFacts(threadId),
    ]);
    setFillPlan(actionsPayload.fill_plan);
    setApprovals(normalizeApprovalItems(actionsPayload));
    setApprovedActions(actionsPayload.approved_actions ?? []);
    setExecutions(actionsPayload.executions ?? []);
    setFacts(flattenFacts(taxFactsPayload.facts ?? {}, taxFactsPayload.fact_evidence ?? {}));
  };

  const initialize = async () => {
    setIsBusy(true);
    try {
      const storedSession = await loadSidepanelSession();
      const userId = storedSession?.userId ?? createSidepanelUserId();
      const ensured = await ensureThread(userId, storedSession?.threadId ?? null);
      const nextSession = { threadId: ensured.thread_id, userId: ensured.user_id };
      await saveSidepanelSession(nextSession);
      setSession(nextSession);
      await refreshSnapshot();
      await refreshBackendState(nextSession.threadId);
      appendMessage(`Thread ready: ${nextSession.threadId.slice(0, 8)}`);
    } catch (error: unknown) {
      appendMessage(`Initialization failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  useEffect(() => {
    const listener = (msg: { type?: string; payload?: any }) => {
      if (msg.type === "backend_message") {
        setMessages((prev) => [...prev, `Agent: ${JSON.stringify(msg.payload)}`]);
      }
      if (msg.type === "page_detected" || msg.type === "page_context") {
        applyPageContext(msg.payload as PageContextPayload);
      }
    };

    chrome.runtime.onMessage.addListener(listener);
    void initialize();
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const handlePreparePage = async () => {
    if (!session) {
      return;
    }

    setIsBusy(true);
    try {
      const snapshot = (await refreshSnapshot()) ?? pageContext;
      const pageType = snapshot?.page ?? page;
      const proposal = await createProposal({
        threadId: session.threadId,
        pageType,
        portalState: snapshot?.portalState ?? pageContext?.portalState ?? null,
      });
      setFillPlan(proposal.fill_plan);
      appendMessage(`Prepared ${proposal.fill_plan?.total_actions ?? 0} action(s) for ${pageType}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Proposal failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleApproval = async (approvalId: string, approved: boolean) => {
    if (!session) {
      return;
    }

    setIsBusy(true);
    try {
      await decideApproval({
        threadId: session.threadId,
        approvalId,
        approved,
        rejectionReason: approved ? undefined : "Rejected from extension sidepanel",
      });
      appendMessage(`${approved ? "Approved" : "Rejected"} approval ${approvalId}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Approval update failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleExecute = async () => {
    if (!session || !fillPlan) {
      return;
    }

    setIsBusy(true);
    try {
      const beforeSnapshot = await refreshSnapshot();
      if (!beforeSnapshot?.portalState) {
        throw new Error("Portal snapshot unavailable before execution");
      }

      const planActions = flattenPlanActions(fillPlan).filter(
        (action) => action.requires_approval === false || approvedActions.includes(action.action_id)
      );
      if (planActions.length === 0) {
        throw new Error("No approved actions are ready to execute");
      }

      const batchResponse = await sendRuntimeMessage<RuntimeResponse<ActionBatchPayload>>({
        type: "run_action_batch",
        payload: {
          actions: planActions.map((action) => ({
            type: "fill",
            selector: action.selector,
            value: String(action.value ?? ""),
          })),
        },
      });
      if (!batchResponse.ok || !batchResponse.payload) {
        throw new Error(batchResponse.error ?? "Action batch failed");
      }

      const afterContext = batchResponse.payload.pageContext;
      applyPageContext(afterContext);
      const normalizedValidationErrors = (batchResponse.payload.validationErrors ?? []).map((error) => ({
        field: error.field,
        message: error.message,
        parsed_reason: error.parsedReason ?? error.parsed_reason,
      }));

      const executionResults = planActions.map((action, index) => {
        const batchResult = batchResponse.payload?.results[index];
        const previousValue = beforeSnapshot.portalState.fields[action.selector]?.value ?? null;
        const observedValue = afterContext.portalState.fields[action.selector]?.value ?? batchResult?.readAfterWrite?.observedValue ?? null;
        const hasValidationError = normalizedValidationErrors.some((error) =>
          [action.field_id, action.selector, action.field_label].includes(error.field)
        );

        return {
          ...action,
          result: hasValidationError ? "validation_error" : (batchResult?.readAfterWrite?.ok ? "ok" : "readback_mismatch"),
          read_after_write: {
            ok: Boolean(batchResult?.readAfterWrite?.ok) && !hasValidationError,
            observed_value: observedValue,
            previous_value: previousValue,
          },
        };
      });

      const recorded = await recordExecution({
        threadId: session.threadId,
        portalStateBefore: beforeSnapshot.portalState,
        portalStateAfter: afterContext.portalState,
        executionResults,
        validationErrors: normalizedValidationErrors,
      });

      appendMessage(`Executed ${recorded.validation_summary.executed} action(s).`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Execution failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleUndo = async () => {
    if (!session) {
      return;
    }

    const lastFillExecution = executions.find((execution) => execution.execution_kind === "fill" && execution.success);
    if (!lastFillExecution) {
      return;
    }

    const revertibleActions = (lastFillExecution.results.executed_actions ?? []).filter(
      (action) => action.selector && action.read_after_write && action.read_after_write.previous_value !== undefined
    );
    if (revertibleActions.length === 0) {
      appendMessage("Nothing to undo for the last execution.");
      return;
    }

    setIsBusy(true);
    try {
      const beforeUndo = await refreshSnapshot();
      if (!beforeUndo?.portalState) {
        throw new Error("Portal snapshot unavailable before undo");
      }

      const undoBatch = await sendRuntimeMessage<RuntimeResponse<ActionBatchPayload>>({
        type: "run_action_batch",
        payload: {
          actions: revertibleActions.map((action) => ({
            type: "fill",
            selector: action.selector,
            value: String(action.read_after_write?.previous_value ?? ""),
          })),
        },
      });
      if (!undoBatch.ok) {
        throw new Error(undoBatch.error ?? "Undo batch failed");
      }

      const undone = await undoExecution({
        threadId: session.threadId,
        executionId: lastFillExecution.execution_id,
        portalState: beforeUndo.portalState,
      });
      appendMessage(`Undo completed with execution ${undone.execution_id}.`);
      const afterUndo = await refreshSnapshot();
      if (afterUndo) {
        applyPageContext(afterUndo);
      }
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Undo failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const sendMessage = (text: string) => {
    setMessages((prev) => [...prev, `You: ${text}`]);
    chrome.runtime.sendMessage({
      type: "chat_message",
      payload: {
        text,
        page
      }
    });
  };

  return (
    <main>
      <h2>IncomeTax Agent</h2>
      {session ? <p>Thread: {session.threadId.slice(0, 8)}</p> : null}
      <DetectedDetailsPane page={page} fields={detectedFields} validationErrors={validationErrors} />
      <ChatPane onSend={sendMessage} messages={messages} />
      <PendingActionsPane
        page={page}
        fillPlan={fillPlan}
        approvals={approvals}
        approvedActionCount={approvedActions.length}
        lastExecution={executions[0] ?? null}
        isBusy={isBusy}
        onPreparePage={handlePreparePage}
        onApprove={(approvalId) => void handleApproval(approvalId, true)}
        onReject={(approvalId) => void handleApproval(approvalId, false)}
        onExecute={() => void handleExecute()}
        onUndo={() => void handleUndo()}
      />
      <EvidencePane facts={facts} />
    </main>
  );
}
