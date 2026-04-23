import "./styles.css";

import { buildCADashboardModel, DashboardOperationsSnapshot, ClientReviewRow } from "./ca-dashboard";

type AuthResponse = {
  user_id: string;
  email: string;
  device_id: string;
  session_id: string;
  access_token: string;
  refresh_token: string;
  access_expires_at: string;
  refresh_expires_at: string;
};

type DashboardApiResponse = {
  generated_at: string;
  user: { user_id: string; email: string };
  clients: Array<{
    thread_id: string;
    pan?: string;
    name?: string;
    itr_type?: string;
    assessment_year?: string;
    can_submit?: boolean;
    can_autofill?: boolean;
    blocking_issues: string[];
    mismatch_count?: number;
    pending_approval_count?: number;
    pending_signoff_count?: number;
    access_role?: string;
    support_mode?: string;
    last_execution?: { success?: boolean; ended_at?: string | null } | null;
  }>;
  analytics: DashboardOperationsSnapshot;
};

type VerdictEvidenceAction = {
  id: string;
  label: string;
  kind: string;
  requires_approval?: boolean;
  value?: number | string | null;
  prompts_for_note?: boolean;
};

type VerdictEvidenceItem = {
  id: string;
  code: string;
  summary: string;
  severity: string;
  status: string;
  resolvable: boolean;
  actions: VerdictEvidenceAction[];
  resolution?: {
    status: string;
    actor_email?: string | null;
    at?: string | null;
    note?: string | null;
    action_kind?: string | null;
    accepted_value?: number | string | null;
  } | null;
};

type VerdictCardData = {
  verdict: {
    code: string;
    title: string;
    detail: string;
    severity: string;
    mode_impact: string;
    is_mode_trigger: boolean;
  };
  evidence: VerdictEvidenceItem[];
  actions: VerdictEvidenceAction[];
  trail: Array<{ actor?: string | null; verb?: string | null; at?: string | null; note?: string | null }>;
};

type VerdictsResponse = {
  thread_id: string;
  mode: string;
  mode_trigger?: string | null;
  can_autofill: boolean;
  can_submit: boolean;
  checklist: string[];
  verdicts: VerdictCardData[];
};

type ReplayPipelineResponse = {
  totals: {
    snapshots_considered: number;
    runs_created: number;
    successful_runs: number;
    failed_runs: number;
    success_rate: number;
  };
};

type DocumentUploadInit = {
  document_id: string;
  version_no: number;
  upload_url: string;
  status: string;
  expires: number;
  signature: string;
};

type ThreadDocument = {
  document_id: string;
  file_name: string;
  document_type: string;
  status: string;
  latest_version_no?: number;
  uploaded_at?: string | null;
  parsed_at?: string | null;
};

type DocumentSearchResponse = {
  mode: string;
  results: Array<{
    document_id: string;
    file_name: string;
    document_type: string;
    chunk_text: string;
    score: number;
  }>;
};

type Session = {
  accessToken: string;
  refreshToken: string;
  deviceId: string;
  email: string;
};

const sessionKey = "itx-ca-dashboard-session";
const deviceKey = "itx-ca-dashboard-device";
const BACKEND_URL = import.meta.env.VITE_ITX_BACKEND_BASE_URL || "http://localhost:8000";

function loadSession(): Session | null {
  const raw = window.localStorage.getItem(sessionKey);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

function saveSession(session: Session): void {
  window.localStorage.setItem(sessionKey, JSON.stringify(session));
}

function clearSession(): void {
  window.localStorage.removeItem(sessionKey);
}

function getOrCreateDeviceId(): string {
  const existing = window.localStorage.getItem(deviceKey);
  if (existing) {
    return existing;
  }
  const next = window.crypto.randomUUID();
  window.localStorage.setItem(deviceKey, next);
  return next;
}

async function apiRequest<T>(session: Session, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      "X-ITX-Device-ID": session.deviceId,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string; error?: string } | null;
    throw new Error(translateErrorCode(payload?.detail ?? payload?.error) ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function apiRequestUrl<T>(session: Session, urlOrPath: string, init?: RequestInit): Promise<T> {
  const url = urlOrPath.startsWith("http") ? urlOrPath : `${BACKEND_URL}${urlOrPath}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      "X-ITX-Device-ID": session.deviceId,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string; error?: string } | null;
    throw new Error(translateErrorCode(payload?.detail ?? payload?.error) ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function translateErrorCode(code?: string): string | undefined {
  if (!code) return undefined;
  const map: Record<string, string> = {
    invalid_credentials: "Incorrect email or password.",
    invalid_email: "Enter a valid email address.",
    password_too_short: "Password must be at least 8 characters.",
    password_too_long: "Password is too long (max 128 characters).",
    password_required: "Password is required.",
    email_already_registered: "An account with this email already exists. Sign in instead.",
    device_id_required: "Browser device could not be identified. Please reload the page.",
    authorization_required: "Please sign in to continue.",
    session_not_found: "Your session has ended. Sign in again.",
    session_revoked: "This session was revoked. Sign in again.",
    access_token_expired: "Your session expired. Sign in again.",
    refresh_token_expired: "Your session expired. Sign in again.",
    device_mismatch: "This session is bound to a different browser.",
    invalid_token: "Session is invalid. Sign in again.",
  };
  return map[code];
}

async function callAuthEndpoint(path: "/api/auth/signup" | "/api/auth/login", body: Record<string, unknown>): Promise<Session> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await response.json().catch(() => null)) as (AuthResponse & { detail?: string; error?: string }) | null;
  if (!response.ok || !payload || !("access_token" in payload)) {
    const code = payload?.detail ?? payload?.error;
    throw new Error(translateErrorCode(code) ?? code ?? `Request failed: ${response.status}`);
  }
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    deviceId: payload.device_id,
    email: payload.email,
  };
}

async function signup(email: string, password: string): Promise<Session> {
  return callAuthEndpoint("/api/auth/signup", {
    email,
    password,
    device_id: getOrCreateDeviceId(),
    device_name: "CA Dashboard Browser",
  });
}

async function signin(email: string, password: string): Promise<Session> {
  return callAuthEndpoint("/api/auth/login", {
    email,
    password,
    device_id: getOrCreateDeviceId(),
    device_name: "CA Dashboard Browser",
  });
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderAuth(mode: "signin" | "signup", message = "", error = ""): string {
  const isSignup = mode === "signup";
  const title = isSignup ? "Create your account" : "Sign in";
  const cta = isSignup ? "Create account" : "Sign in";
  const toggleText = isSignup ? "Already have an account? Sign in." : "Need an account? Create one.";
  const toggleMode = isSignup ? "signin" : "signup";

  return `
    <div class="shell">
      <section class="hero">
        <div class="panel">
          <h1>CA control room for assisted filing.</h1>
          <p>Review queue health, replay drift, submission blockers, and client readiness from one surface.</p>
          ${message ? `<p class="flash-info">${escapeHtml(message)}</p>` : ""}
          ${error ? `<p class="flash-error">${escapeHtml(error)}</p>` : ""}
        </div>
        <div class="panel">
          <h2>${escapeHtml(title)}</h2>
          <form class="login-form" id="auth-form" data-mode="${mode}">
            <label>
              Email
              <input name="email" type="email" autocomplete="email" placeholder="you@firm.com" required />
            </label>
            <label>
              Password
              <input name="password" type="password" autocomplete="${isSignup ? "new-password" : "current-password"}" minlength="8" required />
            </label>
            ${isSignup ? `
            <label>
              Confirm password
              <input name="confirmPassword" type="password" autocomplete="new-password" minlength="8" required />
            </label>` : ""}
            <button type="submit">${escapeHtml(cta)}</button>
            <button type="button" class="secondary" data-toggle-mode="${toggleMode}">${escapeHtml(toggleText)}</button>
          </form>
        </div>
      </section>
    </div>
  `;
}

function toClientRows(items: DashboardApiResponse["clients"]): ClientReviewRow[] {
  return items.map((item) => ({
    threadId: item.thread_id,
    pan: item.pan,
    name: item.name,
    itrType: item.itr_type,
    assessmentYear: item.assessment_year,
    canSubmit: item.can_submit,
    canAutofill: item.can_autofill,
    blockingIssues: item.blocking_issues || [],
    mismatchCount: item.mismatch_count,
    pendingApprovalCount: item.pending_approval_count,
    pendingSignoffCount: item.pending_signoff_count,
    accessRole: item.access_role,
    supportMode: item.support_mode,
    lastExecution: item.last_execution,
  }));
}

function renderDashboard(session: Session, response: DashboardApiResponse, replayRun: ReplayPipelineResponse | null, flash = ""): string {
  const model = buildCADashboardModel(toClientRows(response.clients), response.analytics);
  const clientRows = model.clients
    .map(
      (client) => `
        <tr class="client-row" data-thread-id="${escapeHtml(client.threadId)}" tabindex="0" role="button">
          <td>${escapeHtml(client.name)}</td>
          <td><code>${escapeHtml(client.threadId.slice(0, 8))}</code></td>
          <td><span class="pill ${client.risk}">${escapeHtml(client.risk)}</span></td>
          <td>${escapeHtml(client.status)}</td>
          <td>${escapeHtml(client.recommendedAction)}</td>
        </tr>
      `,
    )
    .join("");

  const alerts = model.operations.alerts.length
    ? `<ul class="alerts">${model.operations.alerts.map((alert) => `<li>${escapeHtml(alert)}</li>`).join("")}</ul>`
    : `<div class="empty">No active platform alerts are being raised from the current replay, drift, and health signals.</div>`;

  const clientsForSelect = response.clients;
  const defaultThreadId = clientsForSelect[0]?.thread_id ?? "";
  const groupOrder: Array<{ mode: string; label: string }> = [
    { mode: "ca-handoff", label: "CA handoff" },
    { mode: "guided-checklist", label: "Guided review" },
    { mode: "supported", label: "Ready to submit" },
    { mode: "", label: "Other" },
  ];
  const groupedOptions = groupOrder
    .map(({ mode, label }) => {
      const items = clientsForSelect.filter((client) => (client.support_mode ?? "") === mode);
      if (items.length === 0) return "";
      const options = items
        .map((client) => {
          const name = client.name || client.pan || "Unnamed";
          const suffix = client.mismatch_count ? ` · ${client.mismatch_count} mismatch${client.mismatch_count === 1 ? "" : "es"}` : "";
          const selected = client.thread_id === defaultThreadId ? " selected" : "";
          return `<option value="${escapeHtml(client.thread_id)}"${selected}>${escapeHtml(name)} · ${escapeHtml(client.thread_id.slice(0, 8))}${escapeHtml(suffix)}</option>`;
        })
        .join("");
      return `<optgroup label="${escapeHtml(label)}">${options}</optgroup>`;
    })
    .join("");

  return `
    <div class="shell">
      <section class="hero">
        <div class="panel">
          <h1>CA operations dashboard</h1>
          <p>Signed in as ${escapeHtml(session.email)}. This surface combines reviewer queue data with replay, drift, and tracing signals from the backend.</p>
          <div class="meta">
            <span class="pill low">Tracing: ${escapeHtml(model.operations.tracingBackend)}</span>
            <span class="pill ${model.operations.driftEvents > 0 ? "medium" : "low"}">Drift events: ${model.operations.driftEvents}</span>
            <span class="pill ${model.operations.replaySuccessRate < 0.95 ? "high" : "low"}">Replay success: ${(model.operations.replaySuccessRate * 100).toFixed(1)}%</span>
          </div>
        </div>
        <div class="panel controls">
          ${flash ? `<p class="flash-info">${escapeHtml(flash)}</p>` : ""}
          <button id="refresh-dashboard">Refresh dashboard</button>
          <button id="run-replay-pipeline">Run replay pipeline</button>
          <button class="secondary" id="sign-out">Sign out</button>
          <p>AI provider: ${escapeHtml(model.operations.aiProvider)}</p>
          ${replayRun ? `<p>Last replay run: ${replayRun.totals.runs_created} runs, ${(replayRun.totals.success_rate * 100).toFixed(1)}% success.</p>` : ""}
        </div>
      </section>

      <section class="grid stats">
        <div class="stat"><p>Total clients</p><strong>${model.overview.totalClients}</strong></div>
        <div class="stat"><p>Ready to submit</p><strong>${model.overview.readyToSubmit}</strong></div>
        <div class="stat"><p>Guided review</p><strong>${model.overview.guidedReview}</strong></div>
        <div class="stat"><p>CA handoff</p><strong>${model.overview.caHandoff}</strong></div>
      </section>

      <section class="panel document-workspace">
        <div>
          <h2>Document intake and search</h2>
          <p>Upload tax PDFs, CSVs, JSON, images, or text files for a thread.</p>
        </div>
        <form class="document-form" id="document-upload-form">
          <label>
            Thread
            ${clientsForSelect.length > 0 ? `
              <select name="threadId" id="thread-select" required>
                ${groupedOptions}
              </select>
            ` : `
              <input name="threadId" value="${escapeHtml(defaultThreadId)}" placeholder="thread-id" required />
            `}
          </label>
          <label>
            Files
            <input name="files" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.csv,.json,.txt,application/pdf,image/png,image/jpeg,text/csv,application/json,text/plain" required />
          </label>
          <button type="submit">Upload</button>
          <button type="button" class="secondary" id="refresh-documents">Refresh</button>
          <button type="button" class="secondary" id="open-verdicts">View verdicts</button>
        </form>
        <form class="document-form" id="document-search-form">
          <label>
            Search
            <input name="query" placeholder="What is the total salary income?" required />
          </label>
          <button type="submit">Search indexed documents</button>
        </form>
        <div id="document-results" class="document-results empty">Select a client thread and upload or search documents.</div>
      </section>

      <section class="workspace">
        <div class="panel">
          <h2>Client queue</h2>
          <p class="hint">Click a row to open its verdict detail.</p>
          <table class="table clickable-rows">
            <thead>
              <tr>
                <th>Client</th>
                <th>Thread</th>
                <th>Risk</th>
                <th>Status</th>
                <th>Recommended action</th>
              </tr>
            </thead>
            <tbody id="client-queue-body">
              ${clientRows || `<tr><td colspan="5"><div class="empty">No accessible clients are available for this operator yet.</div></td></tr>`}
            </tbody>
          </table>
        </div>

        <div class="grid">
          <div class="panel">
            <h2>Queues</h2>
            <p>Pending approvals: <strong>${model.queues.pendingApprovals}</strong></p>
            <p>Pending sign-offs: <strong>${model.queues.pendingSignoffs}</strong></p>
            <p>Mismatches to review:
              <button type="button" class="link-button" id="mismatch-queue-button">
                <strong>${model.queues.mismatchReview}</strong>
              </button>
            </p>
          </div>
          <div class="panel">
            <h2>Ops alerts</h2>
            ${alerts}
          </div>
        </div>
      </section>

      <aside id="verdict-drawer" class="verdict-drawer" hidden>
        <div class="verdict-drawer-inner">
          <header class="verdict-drawer-header">
            <h2>Thread verdicts</h2>
            <button type="button" class="secondary" id="verdict-drawer-close">Close</button>
          </header>
          <div id="verdict-drawer-body" class="verdict-drawer-body">
            <p class="empty">Select a client row to load verdicts.</p>
          </div>
        </div>
      </aside>
    </div>
  `;
}

function severityPillClass(sev: string | undefined): string {
  const value = String(sev ?? "").toLowerCase();
  if (value === "high" || value === "error") return "high";
  if (value === "medium" || value === "warning") return "medium";
  return "low";
}

function renderVerdictDrawerContents(data: VerdictsResponse): string {
  if (!data.verdicts.length) {
    return `<p class="empty">No open verdicts for thread <code>${escapeHtml(data.thread_id.slice(0, 8))}</code>. Mode: <strong>${escapeHtml(data.mode)}</strong>.</p>`;
  }
  const cards = data.verdicts
    .map((card) => {
      const evidence = card.evidence
        .map((item) => {
          const actions = item.resolvable
            ? `<div class="verdict-actions">${item.actions
                .map(
                  (action) =>
                    `<button type="button" class="verdict-action" data-resolve-code="${escapeHtml(item.code)}" data-resolve-item="${escapeHtml(item.id)}" data-resolve-kind="${escapeHtml(action.kind)}"${action.value !== undefined && action.value !== null ? ` data-resolve-value="${escapeHtml(String(action.value))}"` : ""}${action.prompts_for_note ? ` data-resolve-prompt="1"` : ""}>${escapeHtml(action.label)}${action.requires_approval ? " *" : ""}</button>`,
                )
                .join("")}</div>`
            : "";
          const resolution = item.resolution
            ? (() => {
                const parts: string[] = [item.resolution.actor_email ?? "system", item.resolution.status];
                if (item.resolution.action_kind && item.resolution.action_kind !== "resolve") {
                  parts.push(item.resolution.action_kind.replaceAll("_", " "));
                }
                if (item.resolution.accepted_value !== undefined && item.resolution.accepted_value !== null && item.resolution.accepted_value !== "") {
                  parts.push(`accepted = ${String(item.resolution.accepted_value)}`);
                }
                if (item.resolution.at) parts.push(new Date(item.resolution.at).toLocaleString());
                if (item.resolution.note) parts.push(`note: ${item.resolution.note}`);
                return `<div class="verdict-resolution-note">${escapeHtml(parts.join(" · "))}</div>`;
              })()
            : "";
          return `<li class="verdict-evidence-item status-${escapeHtml(item.status)}">
            <div class="verdict-evidence-summary">
              <span class="pill ${severityPillClass(item.severity)}">${escapeHtml(item.severity)}</span>
              <span>${escapeHtml(item.summary)}</span>
              <span class="verdict-status-chip">${escapeHtml(item.status)}</span>
            </div>
            ${actions}
            ${resolution}
          </li>`;
        })
        .join("");
      const evidenceBlock = card.evidence.length
        ? `<ul class="verdict-evidence-list">${evidence}</ul>`
        : `<p class="empty">No structured evidence attached.</p>`;
      const trail = card.trail.length
        ? `<details class="verdict-trail"><summary>Audit trail (${card.trail.length})</summary><ol>${card.trail
            .map(
              (entry) =>
                `<li>${escapeHtml(entry.actor ?? "system")} · ${escapeHtml(entry.verb ?? "event")}${entry.at ? ` · ${new Date(entry.at).toLocaleString()}` : ""}${entry.note ? ` — ${escapeHtml(entry.note)}` : ""}</li>`,
            )
            .join("")}</ol></details>`
        : "";
      return `<article class="verdict-card verdict-sev-${severityPillClass(card.verdict.severity)}">
        <header class="verdict-card-header">
          <span class="pill ${severityPillClass(card.verdict.severity)}">${escapeHtml(card.verdict.severity)}</span>
          <strong>${escapeHtml(card.verdict.title)}</strong>
          ${card.verdict.is_mode_trigger ? `<span class="pill medium">triggers ${escapeHtml(card.verdict.mode_impact)}</span>` : ""}
        </header>
        <p>${escapeHtml(card.verdict.detail)}</p>
        ${evidenceBlock}
        ${trail}
      </article>`;
    })
    .join("");
  const checklist = data.checklist.length
    ? `<div class="verdict-checklist"><h3>Checklist</h3><ul>${data.checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`
    : "";
  return `<div class="verdict-drawer-meta">
      <p>Thread <code>${escapeHtml(data.thread_id.slice(0, 8))}</code> · Mode <strong>${escapeHtml(data.mode)}</strong>${data.mode_trigger ? ` · Triggered by <code>${escapeHtml(data.mode_trigger)}</code>` : ""}</p>
    </div>
    ${cards}
    ${checklist}`;
}

async function fetchThreadVerdicts(session: Session, threadId: string): Promise<VerdictsResponse> {
  return apiRequest<VerdictsResponse>(session, `/api/ca/threads/${encodeURIComponent(threadId)}/verdicts`);
}

async function resolveDashboardVerdictItem(
  session: Session,
  threadId: string,
  code: string,
  itemId: string,
  status: "open" | "acknowledged" | "resolved",
  actionKind: string,
  extras: { acceptedValue?: number | string | null; note?: string | null } = {},
): Promise<void> {
  const body: Record<string, unknown> = { status, action_kind: actionKind };
  if (extras.acceptedValue !== undefined && extras.acceptedValue !== null && extras.acceptedValue !== "") {
    const numeric = Number(extras.acceptedValue);
    body.accepted_value = Number.isFinite(numeric) ? numeric : extras.acceptedValue;
  }
  if (extras.note) body.note = extras.note;
  await apiRequest(session, `/api/ca/threads/${encodeURIComponent(threadId)}/verdicts/${encodeURIComponent(code)}/items/${encodeURIComponent(itemId)}/resolve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

async function fetchDashboardData(session: Session): Promise<DashboardApiResponse> {
  return apiRequest<DashboardApiResponse>(session, "/api/ca/dashboard");
}

async function runReplayPipeline(session: Session): Promise<ReplayPipelineResponse> {
  return apiRequest<ReplayPipelineResponse>(session, "/api/replay/pipeline", {
    method: "POST",
    body: JSON.stringify({ limit: 25 }),
  });
}

function inferDocumentType(fileName: string): string {
  const normalized = fileName.toLowerCase();
  const compact = normalized.replace(/[^a-z0-9]/g, "");
  if (compact.includes("form16b")) return "form16b";
  if (compact.includes("form16a")) return "form16a";
  if (compact.includes("form16")) return "form16";
  if (normalized.includes("ais")) return normalized.endsWith(".json") ? "ais_json" : "ais_csv";
  if (normalized.includes("tis")) return "tis";
  if (normalized.includes("bank")) return "bank_statement";
  if (normalized.includes("rent")) return "rent_receipt";
  if (normalized.includes("home") || normalized.includes("loan")) return "home_loan_cert";
  if (normalized.includes("insurance")) return "health_insurance";
  return "unknown";
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.onload = () => {
      const value = String(reader.result ?? "");
      resolve(value.includes(",") ? value.split(",")[1] : value);
    };
    reader.readAsDataURL(file);
  });
}

async function uploadDashboardDocument(session: Session, threadId: string, file: File): Promise<void> {
  const init = await apiRequest<DocumentUploadInit>(session, "/api/documents/signed-upload", {
    method: "POST",
    body: JSON.stringify({
      thread_id: threadId,
      file_name: file.name,
      mime_type: file.type || "application/octet-stream",
      doc_type: inferDocumentType(file.name),
    }),
  });
  await apiRequestUrl(session, init.upload_url, {
    method: "PUT",
    body: JSON.stringify({
      thread_id: threadId,
      doc_type: inferDocumentType(file.name),
      process_immediately: true,
      content_base64: await readFileAsBase64(file),
    }),
  });
}

async function listDashboardDocuments(session: Session, threadId: string): Promise<ThreadDocument[]> {
  const response = await apiRequest<{ documents: ThreadDocument[] }>(session, `/api/documents/thread/${encodeURIComponent(threadId)}`);
  return response.documents;
}

async function searchDashboardDocuments(session: Session, threadId: string, query: string): Promise<DocumentSearchResponse> {
  return apiRequest<DocumentSearchResponse>(session, "/api/documents/search", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId, query, top_k: 5 }),
  });
}

async function reprocessDashboardDocument(session: Session, documentId: string): Promise<void> {
  await apiRequest(session, `/api/documents/${encodeURIComponent(documentId)}/reprocess`, {
    method: "POST",
    body: JSON.stringify({ process_immediately: true }),
  });
}

function renderDocumentList(documents: ThreadDocument[]): string {
  if (!documents.length) {
    return `<div class="empty">No documents uploaded for this thread yet.</div>`;
  }
  return `
    <table class="table compact">
      <thead><tr><th>File</th><th>Type</th><th>Status</th><th>Version</th><th>Action</th></tr></thead>
      <tbody>
        ${documents
          .map(
            (document) => `
              <tr>
                <td>${escapeHtml(document.file_name)}</td>
                <td>${escapeHtml(document.document_type)}</td>
                <td><span class="pill ${document.status === "indexed" ? "low" : "medium"}">${escapeHtml(document.status)}</span></td>
                <td>${escapeHtml(String(document.latest_version_no ?? 1))}</td>
                <td><button type="button" class="secondary compact-button" data-reprocess-document="${escapeHtml(document.document_id)}">Reprocess</button></td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderDocumentSearch(response: DocumentSearchResponse): string {
  if (!response.results.length) {
    return `<div class="empty">No matches found. If this is a new upload, wait for parsing and indexing to finish.</div>`;
  }
  return `
    <div class="search-results">
      <p>Search mode: <strong>${escapeHtml(response.mode)}</strong></p>
      ${response.results
        .map(
          (result) => `
            <article class="search-result">
              <h3>${escapeHtml(result.file_name)} <span>${escapeHtml(result.document_type)}</span></h3>
              <p>${escapeHtml(result.chunk_text.slice(0, 700))}</p>
              <small>Score: ${result.score.toFixed(3)}</small>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

type AuthViewState = { mode: "signin" | "signup"; message?: string; error?: string };

function renderAuthView(state: AuthViewState): void {
  const app = document.querySelector<HTMLDivElement>("#app");
  if (!app) return;

  app.innerHTML = renderAuth(state.mode, state.message ?? "", state.error ?? "");

  const form = document.querySelector<HTMLFormElement>("#auth-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const email = String(data.get("email") || "").trim();
    const password = String(data.get("password") || "");
    const confirm = String(data.get("confirmPassword") || "");

    if (state.mode === "signup" && password !== confirm) {
      renderAuthView({ mode: "signup", error: "Passwords do not match." });
      return;
    }

    const submitButton = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    try {
      const session = state.mode === "signup" ? await signup(email, password) : await signin(email, password);
      saveSession(session);
      await bootstrap(state.mode === "signup" ? "Account created. Welcome!" : "Signed in successfully.");
    } catch (error) {
      renderAuthView({
        mode: state.mode,
        error: error instanceof Error ? error.message : "Authentication failed.",
      });
    }
  });

  document.querySelectorAll<HTMLButtonElement>("[data-toggle-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextMode = button.getAttribute("data-toggle-mode") === "signup" ? "signup" : "signin";
      renderAuthView({ mode: nextMode });
    });
  });
}

async function bootstrap(message = ""): Promise<void> {
  const app = document.querySelector<HTMLDivElement>("#app");
  if (!app) {
    return;
  }

  const session = loadSession();
  if (!session) {
    renderAuthView({ mode: "signin", message });
    return;
  }

  try {
    const data = await fetchDashboardData(session);
    app.innerHTML = renderDashboard(session, data, null, message);
    wireDashboardActions(session);
  } catch (error) {
    clearSession();
    renderAuthView({
      mode: "signin",
      error: error instanceof Error ? error.message : "Dashboard bootstrap failed.",
    });
  }
}

function wireDashboardActions(session: Session): void {
  document.querySelector<HTMLButtonElement>("#refresh-dashboard")?.addEventListener("click", () => {
    void bootstrap("Dashboard refreshed.");
  });
  document.querySelector<HTMLButtonElement>("#run-replay-pipeline")?.addEventListener("click", async () => {
    try {
      const replayRun = await runReplayPipeline(session);
      const fresh = await fetchDashboardData(session);
      const app = document.querySelector<HTMLDivElement>("#app");
      if (app) {
        app.innerHTML = renderDashboard(session, fresh, replayRun, "Replay pipeline completed.");
        wireDashboardActions(session);
      }
    } catch (error) {
      void bootstrap(error instanceof Error ? error.message : "Replay pipeline failed.");
    }
  });
  document.querySelector<HTMLButtonElement>("#sign-out")?.addEventListener("click", () => {
    clearSession();
    renderAuthView({ mode: "signin", message: "Signed out." });
  });
  wireDocumentActions(session);
  wireVerdictDrawer(session);
}

function wireVerdictDrawer(session: Session): void {
  const queueBody = document.querySelector<HTMLTableSectionElement>("#client-queue-body");
  queueBody?.addEventListener("click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target.closest<HTMLTableRowElement>(".client-row") : null;
    if (!target) return;
    const threadId = target.getAttribute("data-thread-id");
    if (!threadId) return;
    void openVerdictDrawer(session, threadId);
  });
  queueBody?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const target = event.target instanceof HTMLElement ? event.target.closest<HTMLTableRowElement>(".client-row") : null;
    if (!target) return;
    event.preventDefault();
    const threadId = target.getAttribute("data-thread-id");
    if (threadId) void openVerdictDrawer(session, threadId);
  });
  document.querySelector<HTMLButtonElement>("#open-verdicts")?.addEventListener("click", () => {
    const threadId = currentDocumentThreadId();
    if (!threadId) return;
    void openVerdictDrawer(session, threadId);
  });
  document.querySelector<HTMLButtonElement>("#mismatch-queue-button")?.addEventListener("click", () => {
    const threadId = currentDocumentThreadId();
    if (threadId) void openVerdictDrawer(session, threadId);
  });
  document.querySelector<HTMLButtonElement>("#verdict-drawer-close")?.addEventListener("click", closeVerdictDrawer);
  const body = document.querySelector<HTMLDivElement>("#verdict-drawer-body");
  body?.addEventListener("click", async (event) => {
    const target = event.target instanceof HTMLElement ? event.target.closest<HTMLButtonElement>("[data-resolve-item]") : null;
    if (!target) return;
    const threadId = body.getAttribute("data-thread-id");
    const code = target.getAttribute("data-resolve-code") || "";
    const itemId = target.getAttribute("data-resolve-item") || "";
    const kind = target.getAttribute("data-resolve-kind") || "resolve";
    const value = target.getAttribute("data-resolve-value");
    const promptsForNote = target.getAttribute("data-resolve-prompt") === "1";
    if (!threadId || !code || !itemId) return;

    let note: string | null = null;
    if (promptsForNote) {
      const entered = window.prompt("Add a note for this mismatch (visible in the audit trail):", "");
      if (entered === null) return;
      const trimmed = entered.trim();
      if (!trimmed) {
        alert("Note cannot be empty. Choose 'Mark reviewed' if no note is needed.");
        return;
      }
      note = trimmed;
    }

    let confirmationCopy = "";
    if (kind === "accept_ais") confirmationCopy = `Use AIS value ${value ?? ""} as the filing truth for this field?`;
    else if (kind === "accept_doc") confirmationCopy = `Use document value ${value ?? ""} as the filing truth for this field?`;
    if (confirmationCopy && !window.confirm(confirmationCopy)) return;

    const nextStatus: "open" | "acknowledged" | "resolved" = kind === "acknowledge" ? "acknowledged" : kind === "open" ? "open" : "resolved";
    target.disabled = true;
    try {
      await resolveDashboardVerdictItem(session, threadId, code, itemId, nextStatus, kind, { acceptedValue: value, note });
      await openVerdictDrawer(session, threadId);
    } catch (error) {
      target.disabled = false;
      alert(error instanceof Error ? error.message : "Resolution failed.");
    }
  });
}

function currentDocumentThreadId(): string {
  const select = document.querySelector<HTMLSelectElement>('#document-upload-form select[name="threadId"]');
  if (select) return select.value.trim();
  return String(document.querySelector<HTMLInputElement>('#document-upload-form input[name="threadId"]')?.value || "").trim();
}

async function openVerdictDrawer(session: Session, threadId: string): Promise<void> {
  const drawer = document.querySelector<HTMLElement>("#verdict-drawer");
  const body = document.querySelector<HTMLDivElement>("#verdict-drawer-body");
  if (!drawer || !body) return;
  drawer.hidden = false;
  document.body.classList.add("drawer-open");
  body.innerHTML = `<p class="empty">Loading verdicts for <code>${escapeHtml(threadId.slice(0, 8))}</code>…</p>`;
  try {
    const data = await fetchThreadVerdicts(session, threadId);
    body.innerHTML = renderVerdictDrawerContents(data);
    body.setAttribute("data-thread-id", threadId);
  } catch (error) {
    body.innerHTML = `<p class="flash-error">${escapeHtml(error instanceof Error ? error.message : "Failed to load verdicts.")}</p>`;
  }
}

function closeVerdictDrawer(): void {
  const drawer = document.querySelector<HTMLElement>("#verdict-drawer");
  if (drawer) drawer.hidden = true;
  document.body.classList.remove("drawer-open");
}

function setDocumentResults(html: string): void {
  const results = document.querySelector<HTMLDivElement>("#document-results");
  if (!results) return;
  results.classList.remove("empty");
  results.innerHTML = html;
}

function wireDocumentActions(session: Session): void {
  document.querySelector<HTMLFormElement>("#document-upload-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const data = new FormData(form);
    const threadId = String(data.get("threadId") || "").trim();
    const files = Array.from(form.querySelector<HTMLInputElement>('input[name="files"]')?.files ?? []) as File[];
    if (!threadId || files.length === 0) return;
    setDocumentResults(`<div class="empty">Uploading ${files.length} file(s)...</div>`);
    try {
      for (const file of files) {
        await uploadDashboardDocument(session, threadId, file);
      }
      setDocumentResults(renderDocumentList(await listDashboardDocuments(session, threadId)));
    } catch (error) {
      setDocumentResults(`<p class="flash-error">${escapeHtml(error instanceof Error ? error.message : "Upload failed.")}</p>`);
    }
  });

  document.querySelector<HTMLButtonElement>("#refresh-documents")?.addEventListener("click", async () => {
    const threadId = currentDocumentThreadId();
    if (!threadId) return;
    try {
      setDocumentResults(renderDocumentList(await listDashboardDocuments(session, threadId)));
    } catch (error) {
      setDocumentResults(`<p class="flash-error">${escapeHtml(error instanceof Error ? error.message : "Refresh failed.")}</p>`);
    }
  });

  document.querySelector<HTMLFormElement>("#document-search-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = String(new FormData(event.currentTarget as HTMLFormElement).get("query") || "").trim();
    const threadId = currentDocumentThreadId();
    if (!threadId || !query) return;
    setDocumentResults(`<div class="empty">Searching documents...</div>`);
    try {
      setDocumentResults(renderDocumentSearch(await searchDashboardDocuments(session, threadId, query)));
    } catch (error) {
      setDocumentResults(`<p class="flash-error">${escapeHtml(error instanceof Error ? error.message : "Search failed.")}</p>`);
    }
  });

  document.querySelector<HTMLDivElement>("#document-results")?.addEventListener("click", async (event) => {
    const target = event.target instanceof HTMLElement ? event.target.closest<HTMLButtonElement>("[data-reprocess-document]") : null;
    if (!target) return;
    const threadId = currentDocumentThreadId();
    const documentId = target.getAttribute("data-reprocess-document") || "";
    if (!threadId || !documentId) return;
    target.disabled = true;
    target.textContent = "Reprocessing...";
    try {
      await reprocessDashboardDocument(session, documentId);
      setDocumentResults(renderDocumentList(await listDashboardDocuments(session, threadId)));
    } catch (error) {
      setDocumentResults(`<p class="flash-error">${escapeHtml(error instanceof Error ? error.message : "Reprocess failed.")}</p>`);
    }
  });
}

void bootstrap();
