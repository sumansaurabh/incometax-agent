import React, { useEffect, useMemo, useState } from "react";

import "./styles/tokens.css";
import "./styles/chat.css";

import {
  ApprovalItem,
  AuthIdentity,
  BackendError,
  ChatApiMessage,
  ConsentCatalogItem,
  FillPlan,
  PageContextPayload,
  RegimePreview,
  SupportAssessment,
  ThreadDocument,
  createProposal,
  decideApproval,
  ensureThread,
  fetchChatMessages,
  fetchConsentCatalog,
  fetchCurrentIdentity,
  fetchFilingState,
  fetchRegimePreview,
  fetchSupportAssessment,
  fetchTaxFacts,
  fetchThreadActions,
  fetchThreadDocuments,
  grantOnboardingConsents,
  loginToBackend,
  normalizeApprovalItems,
  revokeCurrentSession,
  searchDocuments,
  sendChatMessage,
  uploadDocumentFile,
} from "./backend";
import { ChatPane } from "./panes/ChatPane";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { ChatCard, ChatMessage, UploadedDocument } from "./components/chat-types";
import { clearSidepanelSession, loadSidepanelSession, saveSidepanelSession, SidepanelSession } from "./session";
import {
  AuthSession,
  clearAuthSession,
  defaultDeviceName,
  getOrCreateDeviceId,
  loadAuthSession,
  saveAuthSession,
} from "../shared/auth-session";

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

const PILOT_MODE = true;
const CHAT_STORAGE_PREFIX = "itx_sidepanel_chat:";

function newId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function makeWelcomeMessage(): ChatMessage {
  return {
    id: newId("welcome"),
    role: "agent",
    createdAt: new Date().toISOString(),
    content: "Hi! I'm your IncomeTax filing assistant. Type **File my income tax return** to get started.",
    cards: [
      {
        id: "welcome-actions",
        kind: "welcome",
        title: "What do you want to do?",
        body: "Start with a filing request or upload Form 16, AIS, TIS, bank, deduction, and proof documents.",
        actions: [
          { id: "start-filing", label: "File my return", variant: "primary" },
          { id: "upload-documents", label: "Upload documents" },
          { id: "refund-status", label: "Check refund" },
          { id: "compare-regimes", label: "Compare regimes" },
        ],
      },
    ],
  };
}

function mapServerMessage(message: ChatApiMessage): ChatMessage {
  const metadataCards = Array.isArray(message.metadata?.cards) ? (message.metadata.cards as ChatCard[]) : [];
  const proposalsRaw = message.metadata?.proposals;
  const proposals = Array.isArray(proposalsRaw)
    ? (proposalsRaw as ChatMessage["proposals"])
    : undefined;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    status: message.role === "user" ? "delivered" : undefined,
    cards: metadataCards,
    proposals,
  };
}

function mapDocument(document: ThreadDocument): UploadedDocument {
  return {
    documentId: document.document_id,
    fileName: document.file_name,
    documentType: document.document_type,
    status: document.status,
    uploadedAt: document.uploaded_at,
    parsedAt: document.parsed_at,
  };
}

function countLeafFacts(value: unknown): number {
  if (!value || typeof value !== "object") {
    return value === undefined || value === null || value === "" ? 0 : 1;
  }
  if (Array.isArray(value)) {
    return value.reduce<number>((count, item) => count + countLeafFacts(item), 0);
  }
  return Object.values(value as Record<string, unknown>).reduce<number>((count, item) => count + countLeafFacts(item), 0);
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

async function loadStoredMessages(threadId: string): Promise<ChatMessage[] | null> {
  const stored = await chrome.storage.local.get(`${CHAT_STORAGE_PREFIX}${threadId}`);
  const value = stored[`${CHAT_STORAGE_PREFIX}${threadId}`];
  return Array.isArray(value) ? (value as ChatMessage[]) : null;
}

async function saveStoredMessages(threadId: string, messages: ChatMessage[]): Promise<void> {
  await chrome.storage.local.set({ [`${CHAT_STORAGE_PREFIX}${threadId}`]: messages.slice(-100) });
}

export default function App(): JSX.Element {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [session, setSession] = useState<SidepanelSession | null>(null);
  const [authSession, setAuthSession] = useState<AuthSession | null>(null);
  const [identity, setIdentity] = useState<AuthIdentity | null>(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [trustStatus, setTrustStatus] = useState<TrustStatus | null>(null);
  const [pageContext, setPageContext] = useState<PageContextPayload | null>(null);
  const [consentCatalog, setConsentCatalog] = useState<ConsentCatalogItem[]>([]);
  const [consents, setConsents] = useState<Array<Record<string, unknown>>>([]);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [fillPlan, setFillPlan] = useState<FillPlan | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [supportAssessment, setSupportAssessment] = useState<SupportAssessment | null>(null);
  const [regimePreview, setRegimePreview] = useState<RegimePreview | null>(null);
  const [factCount, setFactCount] = useState(0);
  const [isBusy, setIsBusy] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const appendMessages = (nextMessages: ChatMessage[]) => {
    setMessages((previous) => [...previous, ...nextMessages]);
  };

  const appendAgentMessage = (content: string, cards?: ChatCard[]) => {
    appendMessages([
      {
        id: newId("agent"),
        role: "agent",
        content,
        cards,
        createdAt: new Date().toISOString(),
      },
    ]);
  };

  const appendErrorMessage = (content: string) => {
    appendMessages([
      {
        id: newId("error"),
        role: "error",
        content,
        createdAt: new Date().toISOString(),
      },
    ]);
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

  const refreshSnapshot = async (): Promise<PageContextPayload | null> => {
    try {
      const response = await sendRuntimeMessage<RuntimeResponse<PageContextPayload>>({ type: "snapshot_active_page", payload: {} });
      if (!response.ok || !response.payload) {
        return null;
      }
      setPageContext(response.payload);
      return response.payload;
    } catch {
      return null;
    }
  };

  const refreshBackendState = async (threadId: string) => {
    const [actionsResult, supportResult, documentsResult, factsResult, filingResult] = await Promise.allSettled([
      fetchThreadActions(threadId),
      fetchSupportAssessment(threadId),
      fetchThreadDocuments(threadId),
      fetchTaxFacts(threadId),
      fetchFilingState(threadId),
    ]);

    if (actionsResult.status === "fulfilled") {
      setFillPlan(actionsResult.value.fill_plan);
      setApprovals(normalizeApprovalItems(actionsResult.value));
    }
    if (supportResult.status === "fulfilled") {
      setSupportAssessment(supportResult.value);
    }
    if (documentsResult.status === "fulfilled") {
      setDocuments(documentsResult.value.documents.map(mapDocument));
    }
    if (factsResult.status === "fulfilled") {
      setFactCount(countLeafFacts(factsResult.value.facts));
    }
    if (filingResult.status === "fulfilled") {
      setConsents(filingResult.value.consents ?? []);
    }
  };

  const loadChatForThread = async (threadId: string) => {
    const serverMessages = await fetchChatMessages(threadId).catch(() => null);
    if (serverMessages?.messages.length) {
      setMessages(serverMessages.messages.map(mapServerMessage));
      return;
    }

    const storedMessages = await loadStoredMessages(threadId).catch(() => null);
    setMessages(storedMessages?.length ? storedMessages : [makeWelcomeMessage()]);
  };

  const autoGrantPilotConsents = async (threadId: string, catalog: ConsentCatalogItem[]) => {
    if (!PILOT_MODE || catalog.length === 0) {
      return;
    }
    const purposes = Array.from(new Set(catalog.map((item) => item.purpose)));
    const result = await grantOnboardingConsents({ threadId, purposes });
    setConsents(result.consents ?? []);
  };

  const bootstrapThread = async (userId: string, catalog: ConsentCatalogItem[]) => {
    const storedSession = await loadSidepanelSession();
    const ensured = await ensureThread(userId, storedSession?.threadId ?? null);
    const nextSession = { threadId: ensured.thread_id, userId: ensured.user_id };
    await saveSidepanelSession(nextSession);
    setSession(nextSession);
    await autoGrantPilotConsents(nextSession.threadId, catalog).catch(() => undefined);
    await Promise.all([refreshSnapshot(), refreshBackendState(nextSession.threadId), loadChatForThread(nextSession.threadId)]);
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
        setMessages([]);
        return;
      }

      setAuthSession(storedAuth);
      const [catalog, me] = await Promise.all([fetchConsentCatalog(), fetchCurrentIdentity()]);
      setConsentCatalog(catalog.items ?? []);
      setIdentity(me);
      await bootstrapThread(me.user_id, catalog.items ?? []);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "unknown error";
      const isAuthFailure =
        error instanceof BackendError
          ? error.isAuthFailure()
          : message === "Authentication required" || message === "Session expired" || message === "Session refresh failed";
      if (isAuthFailure) {
        await clearAuthSession();
        await clearSidepanelSession();
        setAuthSession(null);
        setIdentity(null);
        setSession(null);
        setMessages([]);
        setAuthError("Your session ended. Please sign in again.");
      } else {
        appendErrorMessage(`Could not reach backend: ${message}. Retry shortly.`);
      }
    } finally {
      setIsBusy(false);
    }
  };

  useEffect(() => {
    const listener = (msg: { type?: string; payload?: any }) => {
      if (msg.type === "page_detected" || msg.type === "page_context") {
        setPageContext(msg.payload as PageContextPayload);
      }
      if (msg.type === "trust_status") {
        setTrustStatus(msg.payload as TrustStatus);
      }
      if (msg.type === "backend_message" && msg.payload?.type === "chat_response") {
        const payload = msg.payload.payload as ChatApiMessage | undefined;
        if (payload) {
          appendMessages([mapServerMessage(payload)]);
        }
      }
    };

    chrome.runtime.onMessage.addListener(listener);
    void initialize();
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  useEffect(() => {
    if (!session?.threadId || messages.length === 0) return;
    void saveStoredMessages(session.threadId, messages);
  }, [messages, session?.threadId]);

  const indexedCount = useMemo(
    () => documents.filter((document) => document.status === "indexed").length,
    [documents],
  );
  const parsedCount = useMemo(
    () => documents.filter((document) => ["parsed", "indexed"].includes(document.status)).length,
    [documents],
  );

  const contextualCards = useMemo<ChatCard[]>(() => {
    const cards: ChatCard[] = [];
    const pendingApprovals = approvals.filter((approval) => approval.status === "pending");

    if (fillPlan) {
      cards.push({
        id: "fill-plan",
        kind: "action",
        title: "Portal fill plan ready",
        body: "Review approvals in chat before the agent touches the official portal.",
        meta: [
          { label: "Actions", value: String(fillPlan.total_actions) },
          { label: "Pages", value: String(fillPlan.pages.length) },
        ],
        actions: [{ id: "prepare-fill", label: "Refresh plan", variant: "secondary" }],
      });
    }

    pendingApprovals.slice(0, 3).forEach((approval) => {
      cards.push({
        id: `approval-${approval.approvalId}`,
        kind: "approval",
        title: approval.description,
        body: "Pilot mode still asks before executing material portal actions.",
        meta: [
          { label: "Kind", value: approval.kind },
          { label: "Actions", value: String(approval.actionIds.length) },
        ],
        actions: [
          { id: `approve:${approval.approvalId}`, label: "Approve", variant: "primary" },
          { id: `reject:${approval.approvalId}`, label: "Reject", variant: "secondary" },
        ],
      });
    });

    if (supportAssessment && (!supportAssessment.can_autofill || !supportAssessment.can_submit)) {
      cards.push({
        id: "support-assessment",
        kind: "error",
        title: "Review needed",
        body: supportAssessment.reasons[0]?.title ?? "The filing thread has a support blocker.",
        meta: [
          { label: "Mode", value: supportAssessment.mode },
          { label: "Blockers", value: String(supportAssessment.blocking_issues.length) },
        ],
      });
    }

    if (regimePreview) {
      cards.push({
        id: "regime-preview",
        kind: "summary",
        title: `Recommended regime: ${regimePreview.recommended_regime}`,
        body: regimePreview.rationale[0] ?? "Regime comparison has been calculated from available facts.",
        meta: [
          { label: "Old regime tax", value: `INR ${Math.round(regimePreview.old_regime.net_tax_liability).toLocaleString("en-IN")}` },
          { label: "New regime tax", value: `INR ${Math.round(regimePreview.new_regime.net_tax_liability).toLocaleString("en-IN")}` },
        ],
      });
    }

    return cards;
  }, [approvals, fillPlan, regimePreview, supportAssessment]);

  const handleLogin = async () => {
    const email = authEmail.trim();
    if (!email || !authPassword) {
      setAuthError("Enter your email and password to sign in.");
      return;
    }

    setIsBusy(true);
    setAuthError(null);
    try {
      const nextAuth = await loginToBackend({
        email,
        password: authPassword,
        deviceId: await getOrCreateDeviceId(),
        deviceName: defaultDeviceName(),
      });
      await saveAuthSession(nextAuth);
      setAuthSession(nextAuth);
      setAuthPassword("");
      chrome.runtime.sendMessage({ type: "auth_session_updated" });
      await initialize();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Sign-in failed.";
      setAuthPassword("");
      setAuthError(message);
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
      setMessages([]);
      setDocuments([]);
      setFillPlan(null);
      setApprovals([]);
      setSettingsOpen(false);
    } finally {
      setIsBusy(false);
    }
  };

  const handleNewConversation = async () => {
    if (!identity) return;
    setIsBusy(true);
    try {
      await clearSidepanelSession();
      setMessages([makeWelcomeMessage()]);
      // force_new=true to create a fresh thread instead of reusing an existing one
      const ensured = await ensureThread(identity.user_id, null, true);
      const nextSession = { threadId: ensured.thread_id, userId: ensured.user_id };
      await saveSidepanelSession(nextSession);
      setSession(nextSession);
      await autoGrantPilotConsents(nextSession.threadId, consentCatalog).catch(() => undefined);
      await Promise.all([refreshSnapshot(), refreshBackendState(nextSession.threadId), loadChatForThread(nextSession.threadId)]);
      setSettingsOpen(false);
    } catch (error: unknown) {
      appendErrorMessage(`Could not start a new conversation: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleSwitchThread = async (targetThreadId: string) => {
    if (!identity) return;
    if (targetThreadId === session?.threadId) return;
    setIsBusy(true);
    try {
      const ensured = await ensureThread(identity.user_id, targetThreadId);
      const nextSession = { threadId: ensured.thread_id, userId: ensured.user_id };
      await saveSidepanelSession(nextSession);
      setSession(nextSession);
      setDocuments([]);
      setFillPlan(null);
      setApprovals([]);
      setSupportAssessment(null);
      setRegimePreview(null);
      setFactCount(0);
      await Promise.all([
        refreshBackendState(nextSession.threadId),
        loadChatForThread(nextSession.threadId),
      ]);
      setSettingsOpen(false);
      appendAgentMessage(`Switched to thread **${nextSession.threadId.slice(0, 8)}**. Documents and filing state have been refreshed.`);
    } catch (error: unknown) {
      appendErrorMessage(`Could not switch thread: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleSend = async (text: string) => {
    if (!session) {
      appendErrorMessage("Sign in before sending a message.");
      return;
    }
    const userMessage: ChatMessage = {
      id: newId("user"),
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
      status: "sending",
    };
    appendMessages([userMessage]);
    setIsTyping(true);
    try {
      const result = await sendChatMessage({
        threadId: session.threadId,
        message: text,
        context: {
          page: pageContext?.page ?? "unknown",
          portal_state: pageContext?.portalState ?? null,
          pilot_mode: PILOT_MODE,
        },
      });
      setMessages((previous) =>
        previous.map((message) => (message.id === userMessage.id ? { ...message, status: "delivered" } : message))
      );
      appendMessages([mapServerMessage(result.agent_message)]);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      setMessages((previous) =>
        previous.map((message) => (message.id === userMessage.id ? { ...message, status: "error" } : message))
      );
      appendErrorMessage(error instanceof Error ? error.message : "The agent could not answer.");
    } finally {
      setIsTyping(false);
    }
  };

  const handleFilesSelected = async (files: File[]) => {
    if (!session) {
      appendErrorMessage("Sign in before uploading documents.");
      return;
    }
    for (const file of files) {
      appendAgentMessage(`Uploading **${file.name}** and sending it through parsing and indexing.`);
      setIsBusy(true);
      try {
        const uploaded = await uploadDocumentFile({ threadId: session.threadId, file });
        const status = String(uploaded.status ?? "queued");
        appendAgentMessage("", [
          {
            id: `uploaded-${String(uploaded.document_id ?? file.name)}`,
            kind: "document",
            title: file.name,
            body: "Document received. The parser extracts facts first, then the embedding stage indexes searchable chunks.",
            meta: [
              { label: "Status", value: status },
              { label: "Type", value: String(uploaded.document_type ?? "unknown") },
            ],
            actions: [{ id: "search-documents", label: "Search documents", variant: "secondary" }],
          },
        ]);
        await refreshBackendState(session.threadId);
      } catch (error: unknown) {
        appendErrorMessage(`Upload failed for ${file.name}: ${error instanceof Error ? error.message : "unknown error"}`);
      } finally {
        setIsBusy(false);
      }
    }
  };

  const handlePreparePage = async () => {
    if (!session) return;
    if (!trustStatus?.canOperate) {
      appendErrorMessage(trustStatus?.message ?? "Open the official portal before preparing a fill plan.");
      return;
    }
    setIsBusy(true);
    try {
      const snapshot = (await refreshSnapshot()) ?? pageContext;
      const proposal = await createProposal({
        threadId: session.threadId,
        pageType: snapshot?.page ?? pageContext?.page ?? "unknown",
        portalState: snapshot?.portalState ?? pageContext?.portalState ?? null,
      });
      setFillPlan(proposal.fill_plan);
      appendAgentMessage(`Prepared ${proposal.fill_plan?.total_actions ?? 0} portal action(s). Review approval cards before execution.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendErrorMessage(`Fill-plan preparation failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleProposalDecision = async (input: {
    proposalId: string;
    approvalKey: string;
    approved: boolean;
    reason?: string;
  }): Promise<{ approval_status: string; approved_actions: string[] }> => {
    if (!session) {
      throw new Error("No active chat session.");
    }
    // Re-use the existing /api/actions/decision endpoint. The approval_key we created with
    // the proposal is the approval identifier the backend looks up.
    const result = await decideApproval({
      threadId: session.threadId,
      approvalId: input.approvalKey,
      approved: input.approved,
      rejectionReason: input.approved ? undefined : input.reason ?? "user_declined",
    });
    // Pull fresh state so the document strip / fact panel reflect the approval.
    await refreshBackendState(session.threadId);
    return result;
  };

  const handleApproval = async (approvalId: string, approved: boolean) => {
    if (!session) return;
    setIsBusy(true);
    try {
      await decideApproval({
        threadId: session.threadId,
        approvalId,
        approved,
        rejectionReason: approved ? undefined : "Rejected from chat sidepanel",
      });
      appendAgentMessage(`${approved ? "Approved" : "Rejected"} that request.`);
      await refreshBackendState(session.threadId);
    } catch (error: unknown) {
      appendErrorMessage(`Approval update failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCompareRegimes = async () => {
    if (!session) return;
    setIsBusy(true);
    try {
      const preview = await fetchRegimePreview(session.threadId);
      setRegimePreview(preview);
      appendAgentMessage(`Recommended regime: **${preview.recommended_regime}**.`);
    } catch (error: unknown) {
      appendErrorMessage(`Regime comparison needs extracted tax facts first: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleSearchDocuments = async (query = "What tax filing information is available in my uploaded documents?") => {
    if (!session) return;
    setIsBusy(true);
    try {
      const result = await searchDocuments({ threadId: session.threadId, query, topK: 5 });
      if (result.results.length === 0) {
        appendAgentMessage("I did not find indexed document matches yet. Upload Form 16, AIS, TIS, or proofs and I will index them.");
      } else {
        appendAgentMessage(`Found ${result.results.length} document match(es) using ${result.mode}.`, [
          {
            id: `search-${Date.now()}`,
            kind: "evidence",
            title: result.results[0].file_name,
            body: result.results[0].chunk_text,
            meta: [
              { label: "Score", value: result.results[0].score.toFixed(3) },
              { label: "Type", value: result.results[0].document_type },
            ],
          },
        ]);
      }
    } catch (error: unknown) {
      appendErrorMessage(`Document search failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleAction = (actionId: string) => {
    if (actionId === "start-filing") {
      void handleSend("File my income tax return for the current year.");
      return;
    }
    if (actionId === "upload-documents") {
      appendAgentMessage("Use the + button or drag files into the chat. I will parse and index the uploaded PDFs, CSVs, JSON, and images.");
      return;
    }
    if (actionId === "refund-status") {
      void handleSend("Check my refund status.");
      return;
    }
    if (actionId === "compare-regimes") {
      void handleCompareRegimes();
      return;
    }
    if (actionId === "prepare-fill") {
      void handlePreparePage();
      return;
    }
    if (actionId === "search-documents" || actionId.startsWith("search-document:")) {
      void handleSearchDocuments();
      return;
    }
    if (actionId.startsWith("approve:")) {
      void handleApproval(actionId.slice("approve:".length), true);
      return;
    }
    if (actionId.startsWith("reject:")) {
      void handleApproval(actionId.slice("reject:".length), false);
    }
  };

  if (!authSession) {
    return (
      <WelcomeScreen
        authError={authError}
        authEmail={authEmail}
        authPassword={authPassword}
        isBusy={isBusy}
        trustMessage={trustStatus?.message}
        onEmailChange={setAuthEmail}
        onPasswordChange={setAuthPassword}
        onLogin={() => void handleLogin()}
      />
    );
  }

  return (
    <main className="sidepanel-shell">
      <header className="sidepanel-header">
        <div className="brand-lockup">
          <span className="app-mark">IT</span>
          <div>
            <h1>IncomeTax Agent</h1>
            <p>{identity?.email ?? authSession.email}</p>
          </div>
        </div>
        <div className="header-actions">
          <span className={`status-dot ${trustStatus?.status ?? "missing"}`} title={trustStatus?.message ?? "Portal trust unknown"} />
          <button className="icon-button" type="button" aria-label="Settings" onClick={() => setSettingsOpen(true)}>
            ...
          </button>
        </div>
      </header>
      <ChatPane
        messages={messages}
        contextualCards={contextualCards}
        documents={documents}
        isBusy={isBusy}
        isTyping={isTyping}
        onSend={handleSend}
        onFilesSelected={handleFilesSelected}
        onAction={handleAction}
        onProposalDecision={handleProposalDecision}
      />
      <SettingsDrawer
        open={settingsOpen}
        email={identity?.email ?? authSession.email}
        threadId={session?.threadId}
        trustMessage={trustStatus?.message}
        documentCount={documents.length}
        parsedCount={parsedCount}
        indexedCount={indexedCount}
        factCount={factCount}
        onSearchDocuments={() => {
          setSettingsOpen(false);
          void handleSearchDocuments();
        }}
        isBusy={isBusy}
        onClose={() => setSettingsOpen(false)}
        onNewConversation={() => void handleNewConversation()}
        onSwitchThread={(targetThreadId) => void handleSwitchThread(targetThreadId)}
        onSignOut={() => void handleLogout()}
      />
    </main>
  );
}
