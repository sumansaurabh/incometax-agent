import React, { useEffect, useState } from "react";

import {
  ApprovalItem,
  AuthIdentity,
  DetectedField,
  EverificationRecord,
  ExecutionRecord,
  FilingArtifacts,
  FillAction,
  FillPlan,
  PageContextPayload,
  PurgeJob,
  RegimePreview,
  SupportAssessment,
  SubmissionSummaryData,
  ValidationError,
  ValidationHelpItem,
  completeEVerify,
  completeSubmission,
  counterConsentReviewerSignoff,
  createProposal,
  createRevisionThread,
  decideApproval,
  ensureThread,
  fetchCurrentIdentity,
  fetchFilingState,
  fetchRegimePreview,
  fetchSupportAssessment,
  fetchTaxFacts,
  fetchThreadActions,
  fetchValidationHelp,
  filingArtifactUrl,
  generateSubmissionSummary,
  loginToBackend,
  normalizeApprovalItems,
  prepareEVerifyApproval,
  prepareReviewHandoff,
  prepareSubmissionApproval,
  recordExecution,
  requestReviewerSignoff,
  reviewHandoffPackageUrl,
  resumeThreadQuarantine,
  revokeConsent,
  revokeCurrentSession,
  startEVerifyHandoff,
  undoExecution,
} from "./backend";
import { ChatPane } from "./panes/ChatPane";
import { DetectedDetailsPane } from "./panes/DetectedDetailsPane";
import { PendingActionsPane } from "./panes/PendingActionsPane";
import { EvidencePane } from "./panes/EvidencePane";
import { SubmissionPane } from "./panes/SubmissionPane";
import { SupportPane } from "./panes/SupportPane";
import { clearSidepanelSession, SidepanelSession, loadSidepanelSession, saveSidepanelSession } from "./session";
import {
  AuthSession,
  clearAuthSession,
  defaultDeviceName,
  getOrCreateDeviceId,
  loadAuthSession,
  saveAuthSession,
} from "../shared/auth-session";

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

type TrustStatus = {
  status: "verified" | "lookalike" | "unsupported" | "missing";
  host: string | null;
  url: string | null;
  canOperate: boolean;
  message: string;
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
  const [authSession, setAuthSession] = useState<AuthSession | null>(null);
  const [identity, setIdentity] = useState<AuthIdentity | null>(null);
  const [authEmail, setAuthEmail] = useState("");
  const [trustStatus, setTrustStatus] = useState<TrustStatus | null>(null);
  const [consents, setConsents] = useState<Array<Record<string, unknown>>>([]);
  const [purgeJobs, setPurgeJobs] = useState<PurgeJob[]>([]);
  const [supportAssessment, setSupportAssessment] = useState<SupportAssessment | null>(null);
  const [validationHelp, setValidationHelp] = useState<ValidationHelpItem[]>([]);
  const [regimePreview, setRegimePreview] = useState<RegimePreview | null>(null);
  const [fillPlan, setFillPlan] = useState<FillPlan | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [approvedActions, setApprovedActions] = useState<string[]>([]);
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [submissionSummary, setSubmissionSummary] = useState<SubmissionSummaryData | null>(null);
  const [submissionStatus, setSubmissionStatus] = useState("draft");
  const [filingArtifacts, setFilingArtifacts] = useState<FilingArtifacts | null>(null);
  const [everification, setEverification] = useState<EverificationRecord | null>(null);
  const [reviewerEmail, setReviewerEmail] = useState("");
  const [isArchived, setIsArchived] = useState(false);
  const [nextRevisionNumber, setNextRevisionNumber] = useState(1);
  const [isBusy, setIsBusy] = useState(false);

  const appendMessage = (message: string) => {
    setMessages((prev) => [...prev, message]);
  };

  const resetThreadState = () => {
    setFillPlan(null);
    setApprovals([]);
    setApprovedActions([]);
    setExecutions([]);
    setSubmissionSummary(null);
    setSubmissionStatus("draft");
    setFilingArtifacts(null);
    setEverification(null);
    setIsArchived(false);
    setNextRevisionNumber(1);
    setFacts([]);
    setConsents([]);
    setPurgeJobs([]);
    setSupportAssessment(null);
    setValidationHelp([]);
    setRegimePreview(null);
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

  const refreshTrust = async () => {
    try {
      const response = await sendRuntimeMessage<RuntimeResponse<TrustStatus>>({ type: "get_active_tab_trust", payload: {} });
      if (response.ok && response.payload) {
        setTrustStatus(response.payload);
      }
    } catch {
      setTrustStatus(null);
    }
  };

  const refreshContextualInsights = async (threadId: string, context: PageContextPayload) => {
    if (context.validationErrors.length > 0) {
      try {
        const translated = await fetchValidationHelp({
          threadId,
          pageType: context.page,
          portalState: context.portalState,
          validationErrors: context.validationErrors,
        });
        setValidationHelp(translated.items ?? []);
      } catch (error: unknown) {
        appendMessage(`Validation help unavailable: ${error instanceof Error ? error.message : "unknown error"}`);
      }
    } else {
      setValidationHelp([]);
    }

    if (context.page === "regime-choice") {
      try {
        setRegimePreview(await fetchRegimePreview(threadId));
      } catch (error: unknown) {
        appendMessage(`Regime preview unavailable: ${error instanceof Error ? error.message : "unknown error"}`);
        setRegimePreview(null);
      }
    } else {
      setRegimePreview(null);
    }
  };

  const refreshBackendState = async (threadId: string) => {
    const [actionsPayload, taxFactsPayload, filingPayload, supportPayload] = await Promise.all([
      fetchThreadActions(threadId),
      fetchTaxFacts(threadId),
      fetchFilingState(threadId),
      fetchSupportAssessment(threadId),
    ]);
    setFillPlan(actionsPayload.fill_plan);
    setApprovals(normalizeApprovalItems(actionsPayload));
    setApprovedActions(actionsPayload.approved_actions ?? []);
    setExecutions(actionsPayload.executions ?? []);
    setFacts(flattenFacts(taxFactsPayload.facts ?? {}, taxFactsPayload.fact_evidence ?? {}));
    setSubmissionSummary(filingPayload.submission_summary);
    setSubmissionStatus(filingPayload.submission_status ?? "draft");
    setFilingArtifacts(filingPayload.artifacts);
    setEverification(filingPayload.everification);
    setIsArchived(Boolean(filingPayload.archived));
    setNextRevisionNumber(Number((filingPayload.revision?.revision_number as number | undefined) ?? 0) + 1);
    setConsents(filingPayload.consents ?? []);
    setPurgeJobs((filingPayload.purge_jobs ?? []) as PurgeJob[]);
    setSupportAssessment(supportPayload);
  };

  const bootstrapThread = async (userId: string) => {
    const storedSession = await loadSidepanelSession();
    const ensured = await ensureThread(userId, storedSession?.threadId ?? null);
    const nextSession = { threadId: ensured.thread_id, userId: ensured.user_id };
    await saveSidepanelSession(nextSession);
    setSession(nextSession);
    const snapshot = await refreshSnapshot();
    if (snapshot) {
      await refreshContextualInsights(nextSession.threadId, snapshot);
    }
    await refreshBackendState(nextSession.threadId);
    appendMessage(`Thread ready: ${nextSession.threadId.slice(0, 8)}`);
  };

  const initialize = async () => {
    setIsBusy(true);
    try {
      await refreshTrust();
      const storedAuth = await loadAuthSession();
      if (!storedAuth) {
        setAuthSession(null);
        setIdentity(null);
        setSession(null);
        resetThreadState();
        return;
      }

      setAuthSession(storedAuth);
      const me = await fetchCurrentIdentity();
      setIdentity(me);
      await bootstrapThread(me.user_id);
    } catch (error: unknown) {
      await clearAuthSession();
      await clearSidepanelSession();
      setAuthSession(null);
      setIdentity(null);
      setSession(null);
      resetThreadState();
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
      if (msg.type === "trust_status") {
        setTrustStatus(msg.payload as TrustStatus);
      }
    };

    chrome.runtime.onMessage.addListener(listener);
    void initialize();
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  useEffect(() => {
    if (!session?.threadId || !pageContext) {
      return;
    }
    void refreshContextualInsights(session.threadId, pageContext);
  }, [pageContext, session?.threadId]);

  const handlePreparePage = async () => {
    if (!session || !trustStatus?.canOperate) {
      appendMessage(trustStatus?.message ?? "Open the official portal to prepare a fill plan.");
      return;
    }
    if (supportAssessment && !supportAssessment.can_autofill) {
      appendMessage(`Assisted autofill is paused: ${supportAssessment.reasons[0]?.title ?? "manual review is required"}.`);
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
    if (!session || !fillPlan || !trustStatus?.canOperate) {
      if (!trustStatus?.canOperate) {
        appendMessage(trustStatus?.message ?? "Open the official portal to execute approved actions.");
      }
      return;
    }
    if (supportAssessment && !supportAssessment.can_autofill) {
      appendMessage(`Execution is paused: ${supportAssessment.reasons[0]?.title ?? "manual review is required"}.`);
      return;
    }
    const blockingReviewer = approvals.find(
      (approval) => Boolean(approval.signoffId) && approval.reviewerStatus !== "client_approved" && approval.status === "approved"
    );
    if (blockingReviewer) {
      appendMessage(
        `Execution is waiting for reviewer sign-off on ${blockingReviewer.description.toLowerCase()} and your counter-consent.`
      );
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
    if (!session || !trustStatus?.canOperate) {
      if (!trustStatus?.canOperate) {
        appendMessage(trustStatus?.message ?? "Open the official portal to undo a fill batch.");
      }
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

  const handleGenerateSummary = async () => {
    if (!session) {
      return;
    }

    setIsBusy(true);
    try {
      const result = await generateSubmissionSummary({ threadId: session.threadId, isFinal: true });
      setSubmissionSummary(result.submission_summary);
      setSubmissionStatus(result.submission_status);
      appendMessage("Submission summary refreshed.");
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Summary generation failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handlePrepareSubmit = async () => {
    if (!session) {
      return;
    }
    if (supportAssessment && !supportAssessment.can_submit) {
      appendMessage(`Submission is paused: ${supportAssessment.reasons[0]?.title ?? "resolve the guided checklist first"}.`);
      return;
    }

    setIsBusy(true);
    try {
      await prepareSubmissionApproval({ threadId: session.threadId, isFinal: true });
      appendMessage("Submission approval requested.");
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Submission approval failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCompleteSubmission = async (ackNo: string, portalRef: string) => {
    if (!session) {
      return;
    }
    if (supportAssessment && !supportAssessment.can_submit) {
      appendMessage(`Submission archive is paused: ${supportAssessment.reasons[0]?.title ?? "resolve the guided checklist first"}.`);
      return;
    }

    setIsBusy(true);
    try {
      const result = await completeSubmission({
        threadId: session.threadId,
        ackNo,
        portalRef,
      });
      setSubmissionStatus(result.submission_status);
      setFilingArtifacts(result.artifacts);
      appendMessage(`Submission archived${result.artifacts.ack_no ? ` with acknowledgement ${result.artifacts.ack_no}` : ""}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Submission archive failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handlePrepareEVerify = async (method: string) => {
    if (!session) {
      return;
    }
    if (supportAssessment && !supportAssessment.can_submit) {
      appendMessage(`E-verification is paused: ${supportAssessment.reasons[0]?.title ?? "resolve the guided checklist first"}.`);
      return;
    }

    setIsBusy(true);
    try {
      await prepareEVerifyApproval({ threadId: session.threadId, method });
      appendMessage(`E-verify approval requested for ${method.replace(/_/g, " ")}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`E-verify approval failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleStartEVerify = async (method: string) => {
    if (!session) {
      return;
    }
    if (supportAssessment && !supportAssessment.can_submit) {
      appendMessage(`E-verification handoff is paused: ${supportAssessment.reasons[0]?.title ?? "resolve the guided checklist first"}.`);
      return;
    }

    setIsBusy(true);
    try {
      const result = await startEVerifyHandoff({ threadId: session.threadId, method });
      const targetUrl =
        (typeof result.pending_navigation?.url === "string" ? result.pending_navigation.url : null) ??
        (typeof result.everification?.target_url === "string" ? result.everification.target_url : null) ??
        (typeof result.everify_handoff?.target_url === "string" ? result.everify_handoff.target_url : null);
      if (targetUrl) {
        const navigation = await sendRuntimeMessage<RuntimeResponse<{ tabId: number; url: string }>>({
          type: "navigate_active_tab",
          payload: { url: targetUrl },
        });
        if (!navigation.ok) {
          throw new Error(navigation.error ?? "Failed to open e-verification page");
        }
      }
      appendMessage(`Opened e-verification handoff for ${method.replace(/_/g, " ")}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`E-verify handoff failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCompleteEVerify = async (portalRef: string) => {
    if (!session || !everification?.handoff_id) {
      return;
    }

    setIsBusy(true);
    try {
      const result = await completeEVerify({
        threadId: session.threadId,
        handoffId: everification.handoff_id,
        portalRef,
      });
      setSubmissionStatus(result.submission_status);
      setEverification(result.everification);
      setIsArchived(Boolean(result.archived));
      appendMessage("E-verification marked complete.");
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`E-verification completion failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCreateRevision = async (reason: string) => {
    if (!session) {
      return;
    }

    setIsBusy(true);
    try {
      const result = await createRevisionThread({
        threadId: session.threadId,
        reason,
        revisionNumber: nextRevisionNumber,
      });
      const nextSession = { threadId: result.revision_thread_id, userId: session.userId };
      await saveSidepanelSession(nextSession);
      setSession(nextSession);
      appendMessage(`Revision branch created: ${result.revision_thread_id.slice(0, 8)}`);
      await refreshBackendState(nextSession.threadId);
    } catch (error: unknown) {
      appendMessage(`Revision creation failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleLogin = async () => {
    if (!authEmail.trim()) {
      appendMessage("Enter an email address to sign in.");
      return;
    }

    setIsBusy(true);
    try {
      const nextAuth = await loginToBackend({
        email: authEmail.trim(),
        deviceId: await getOrCreateDeviceId(),
        deviceName: defaultDeviceName(),
      });
      await saveAuthSession(nextAuth);
      setAuthSession(nextAuth);
      chrome.runtime.sendMessage({ type: "auth_session_updated" });
      appendMessage(`Signed in as ${nextAuth.email}.`);
      await initialize();
    } catch (error: unknown) {
      appendMessage(`Sign-in failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleLogout = async () => {
    setIsBusy(true);
    try {
      await revokeCurrentSession().catch(() => undefined);
      await clearAuthSession();
      await clearSidepanelSession();
      chrome.runtime.sendMessage({ type: "auth_session_cleared" });
      setAuthSession(null);
      setIdentity(null);
      setSession(null);
      resetThreadState();
      appendMessage("Signed out and local session cleared.");
    } finally {
      setIsBusy(false);
    }
  };

  const handleOpenArtifact = async (artifactName: "itr-v" | "offline-json" | "evidence-bundle" | "summary") => {
    if (!session) {
      return;
    }
    try {
      const latestAuth = await loadAuthSession();
      if (!latestAuth) {
        throw new Error("Authentication required");
      }
      window.open(filingArtifactUrl(session.threadId, artifactName, latestAuth), "_blank", "noopener,noreferrer");
    } catch (error: unknown) {
      appendMessage(`Artifact download failed: ${error instanceof Error ? error.message : "unknown error"}`);
    }
  };

  const handleRevokeConsent = async (consentId: string) => {
    if (!session) {
      return;
    }
    setIsBusy(true);
    try {
      const result = await revokeConsent({ threadId: session.threadId, consentId });
      appendMessage(`Consent revoked. Purge job ${result.purge_job.job_id} is ${result.purge_job.status}.`);
      await clearSidepanelSession();
      resetThreadState();
      if (identity) {
        await bootstrapThread(identity.user_id);
      }
    } catch (error: unknown) {
      appendMessage(`Consent revocation failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleRefreshRegimePreview = async () => {
    if (!session) {
      return;
    }
    setIsBusy(true);
    try {
      const preview = await fetchRegimePreview(session.threadId);
      setRegimePreview(preview);
      appendMessage(`Regime comparison refreshed. Recommended regime: ${preview.recommended_regime}.`);
    } catch (error: unknown) {
      appendMessage(`Regime comparison failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handlePrepareRecommendedRegime = async () => {
    if (!session || !regimePreview) {
      return;
    }
    if (supportAssessment && !supportAssessment.can_autofill) {
      appendMessage(`Regime switch preparation is paused: ${supportAssessment.reasons[0]?.title ?? "manual review is required"}.`);
      return;
    }
    setIsBusy(true);
    try {
      const snapshot = (await refreshSnapshot()) ?? pageContext;
      const proposal = await createProposal({
        threadId: session.threadId,
        pageType: "regime-choice",
        fieldId: "regime",
        targetValue: regimePreview.recommended_regime,
        portalState: snapshot?.portalState ?? pageContext?.portalState ?? null,
      });
      setFillPlan(proposal.fill_plan);
      appendMessage(`Prepared regime switch to ${regimePreview.recommended_regime}. Review the approval card before execution.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Failed to prepare regime switch: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handlePrepareReviewHandoff = async () => {
    if (!session) {
      return;
    }
    setIsBusy(true);
    try {
      const handoff = await prepareReviewHandoff({ threadId: session.threadId });
      appendMessage(`Prepared CA handoff package ${handoff.handoff_id.slice(0, 8)} for ${handoff.support_mode}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`CA handoff preparation failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleRequestReviewerSignoff = async (approvalId: string) => {
    if (!session) {
      return;
    }
    if (!reviewerEmail.trim()) {
      appendMessage("Enter a reviewer email before requesting sign-off.");
      return;
    }
    setIsBusy(true);
    try {
      const signoff = await requestReviewerSignoff({
        threadId: session.threadId,
        approvalId,
        reviewerEmail: reviewerEmail.trim(),
      });
      appendMessage(`Requested reviewer sign-off from ${signoff.reviewer_email}.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Reviewer sign-off request failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCounterConsentReviewer = async (signoffId: string) => {
    if (!session) {
      return;
    }
    setIsBusy(true);
    try {
      await counterConsentReviewerSignoff({ signoffId, approved: true });
      appendMessage("Reviewer sign-off counter-consent recorded.");
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Counter-consent failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleOpenReviewHandoff = async (handoffId: string) => {
    if (!session) {
      return;
    }
    try {
      const latestAuth = await loadAuthSession();
      if (!latestAuth) {
        throw new Error("Authentication required");
      }
      window.open(reviewHandoffPackageUrl(session.threadId, handoffId, latestAuth), "_blank", "noopener,noreferrer");
    } catch (error: unknown) {
      appendMessage(`CA handoff download failed: ${error instanceof Error ? error.message : "unknown error"}`);
    }
  };

  const handleResumeQuarantine = async () => {
    if (!session) {
      return;
    }
    setIsBusy(true);
    try {
      await resumeThreadQuarantine({ threadId: session.threadId, note: "user_reviewed_anomaly" });
      appendMessage("Automation quarantine cleared after review.");
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendMessage(`Failed to resume automation: ${error instanceof Error ? error.message : "unknown error"}`);
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

  const submitApprovalApproved = approvals.some(
    (approval) => approval.status === "approved" && ["submit_final", "submit_draft"].includes(approval.kind)
  );
  const everifyApprovalApproved = approvals.some(
    (approval) => approval.status === "approved" && approval.kind === "everify"
  );

  if (!authSession) {
    return (
      <main>
        <h2>IncomeTax Agent</h2>
        {trustStatus ? <p>Portal trust: {trustStatus.message}</p> : null}
        <p>Sign in to bind this browser device and start a protected filing session.</p>
        <input
          value={authEmail}
          onChange={(event) => setAuthEmail(event.target.value)}
          placeholder="Email address"
          type="email"
        />
        <button disabled={isBusy} onClick={() => void handleLogin()}>
          Sign in on this device
        </button>
      </main>
    );
  }

  return (
    <main>
      <h2>IncomeTax Agent</h2>
      <p>Signed in as {identity?.email ?? authSession.email}</p>
      <button disabled={isBusy} onClick={() => void handleLogout()}>
        Sign out
      </button>
      {trustStatus ? <p>Portal trust: {trustStatus.message}</p> : null}
      {session ? <p>Thread: {session.threadId.slice(0, 8)}</p> : null}
      <DetectedDetailsPane
        page={page}
        fields={detectedFields}
        validationErrors={validationErrors}
        validationHelp={validationHelp}
        regimePreview={regimePreview}
        isBusy={isBusy}
        onRefreshRegimePreview={() => void handleRefreshRegimePreview()}
        onPrepareRecommendedRegime={() => void handlePrepareRecommendedRegime()}
      />
      <SupportPane
        supportAssessment={supportAssessment}
        isBusy={isBusy}
        onPrepareHandoff={() => void handlePrepareReviewHandoff()}
        onOpenHandoff={(handoffId) => void handleOpenReviewHandoff(handoffId)}
        onResumeQuarantine={() => void handleResumeQuarantine()}
      />
      <ChatPane onSend={sendMessage} messages={messages} />
      <PendingActionsPane
        page={page}
        fillPlan={fillPlan}
        approvals={approvals}
        approvedActionCount={approvedActions.length}
        lastExecution={executions[0] ?? null}
        isBusy={isBusy}
        reviewerEmail={reviewerEmail}
        onReviewerEmailChange={setReviewerEmail}
        onPreparePage={handlePreparePage}
        onApprove={(approvalId) => void handleApproval(approvalId, true)}
        onReject={(approvalId) => void handleApproval(approvalId, false)}
        onRequestReviewerSignoff={(approvalId) => void handleRequestReviewerSignoff(approvalId)}
        onCounterConsentReviewerSignoff={(signoffId) => void handleCounterConsentReviewer(signoffId)}
        onExecute={() => void handleExecute()}
        onUndo={() => void handleUndo()}
      />
      <SubmissionPane
        submissionStatus={submissionStatus}
        submissionSummary={submissionSummary}
        artifacts={filingArtifacts}
        everification={everification}
        archived={isArchived}
        isBusy={isBusy}
        submitApprovalApproved={submitApprovalApproved}
        everifyApprovalApproved={everifyApprovalApproved}
        nextRevisionNumber={nextRevisionNumber}
        consents={consents}
        purgeJobs={purgeJobs}
        onGenerateSummary={() => void handleGenerateSummary()}
        onPrepareSubmit={() => void handlePrepareSubmit()}
        onCompleteSubmission={(ackNo, portalRef) => void handleCompleteSubmission(ackNo, portalRef)}
        onPrepareEVerify={(method) => void handlePrepareEVerify(method)}
        onStartEVerify={(method) => void handleStartEVerify(method)}
        onCompleteEVerify={(portalRef) => void handleCompleteEVerify(portalRef)}
        onCreateRevision={(reason) => void handleCreateRevision(reason)}
        onRevokeConsent={(consentId) => void handleRevokeConsent(consentId)}
        onOpenArtifact={(artifactName) => void handleOpenArtifact(artifactName)}
      />
      <EvidencePane facts={facts} />
    </main>
  );
}
