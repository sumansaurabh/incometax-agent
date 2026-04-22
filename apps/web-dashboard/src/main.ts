import "./styles.css";

import { buildCADashboardModel, DashboardOperationsSnapshot, ClientReviewRow } from "./ca-dashboard";

type LoginResponse = {
  access_token: string;
  refresh_token: string;
  device_id: string;
  email: string;
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

type ReplayPipelineResponse = {
  totals: {
    snapshots_considered: number;
    runs_created: number;
    successful_runs: number;
    failed_runs: number;
    success_rate: number;
  };
};

type Session = {
  backendUrl: string;
  accessToken: string;
  deviceId: string;
  email: string;
};

const storageKey = "itx-ca-dashboard-session";
const defaultBackendUrl = import.meta.env.VITE_ITX_BACKEND_BASE_URL || "http://localhost:8000";

function loadSession(): Session | null {
  const raw = window.localStorage.getItem(storageKey);
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
  window.localStorage.setItem(storageKey, JSON.stringify(session));
}

function clearSession(): void {
  window.localStorage.removeItem(storageKey);
}

async function apiRequest<T>(session: Session, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${session.backendUrl}${path}`, {
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
    throw new Error(payload?.detail ?? payload?.error ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function login(email: string, backendUrl: string): Promise<Session> {
  const deviceId = window.crypto.randomUUID();
  const response = await fetch(`${backendUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      device_id: deviceId,
      device_name: "CA Dashboard Browser",
    }),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Login failed: ${response.status}`);
  }
  const payload = (await response.json()) as LoginResponse;
  return {
    backendUrl,
    accessToken: payload.access_token,
    deviceId: payload.device_id,
    email: payload.email,
  };
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderLogin(message = ""): string {
  return `
    <div class="shell">
      <section class="hero">
        <div class="panel">
          <h1>CA control room for assisted filing.</h1>
          <p>Review queue health, replay drift, submission blockers, and client readiness from one surface.</p>
          ${message ? `<p><strong>${escapeHtml(message)}</strong></p>` : ""}
        </div>
        <div class="panel">
          <form class="login-form" id="login-form">
            <label>
              Backend URL
              <input name="backendUrl" value="${escapeHtml(defaultBackendUrl)}" />
            </label>
            <label>
              Operator email
              <input name="email" type="email" placeholder="ca@example.com" required />
            </label>
            <button type="submit">Sign in to dashboard</button>
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
        <tr>
          <td>${escapeHtml(client.name)}</td>
          <td>${escapeHtml(client.threadId)}</td>
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
          ${flash ? `<p><strong>${escapeHtml(flash)}</strong></p>` : ""}
          <button id="refresh-dashboard">Refresh dashboard</button>
          <button id="run-replay-pipeline">Run replay pipeline</button>
          <button class="secondary" id="sign-out">Sign out</button>
          <p>Backend: ${escapeHtml(session.backendUrl)}</p>
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

      <section class="workspace">
        <div class="panel">
          <h2>Client queue</h2>
          <table class="table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Thread</th>
                <th>Risk</th>
                <th>Status</th>
                <th>Recommended action</th>
              </tr>
            </thead>
            <tbody>
              ${clientRows || `<tr><td colspan="5"><div class="empty">No accessible clients are available for this operator yet.</div></td></tr>`}
            </tbody>
          </table>
        </div>

        <div class="grid">
          <div class="panel">
            <h2>Queues</h2>
            <p>Pending approvals: <strong>${model.queues.pendingApprovals}</strong></p>
            <p>Pending sign-offs: <strong>${model.queues.pendingSignoffs}</strong></p>
            <p>Mismatches to review: <strong>${model.queues.mismatchReview}</strong></p>
          </div>
          <div class="panel">
            <h2>Ops alerts</h2>
            ${alerts}
          </div>
        </div>
      </section>
    </div>
  `;
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

async function bootstrap(message = ""): Promise<void> {
  const app = document.querySelector<HTMLDivElement>("#app");
  if (!app) {
    return;
  }

  const session = loadSession();
  if (!session) {
    app.innerHTML = renderLogin(message);
    const loginForm = document.querySelector<HTMLFormElement>("#login-form");
    loginForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(loginForm);
      const email = String(form.get("email") || "").trim();
      const backendUrl = String(form.get("backendUrl") || defaultBackendUrl).trim();
      try {
        const nextSession = await login(email, backendUrl);
        saveSession(nextSession);
        await bootstrap("Signed in successfully.");
      } catch (error) {
        await bootstrap(error instanceof Error ? error.message : "Login failed.");
      }
    });
    return;
  }

  try {
    const data = await fetchDashboardData(session);
    app.innerHTML = renderDashboard(session, data, null, message);
    document.querySelector<HTMLButtonElement>("#refresh-dashboard")?.addEventListener("click", () => {
      void bootstrap("Dashboard refreshed.");
    });
    document.querySelector<HTMLButtonElement>("#run-replay-pipeline")?.addEventListener("click", async () => {
      try {
        const replayRun = await runReplayPipeline(session);
        const fresh = await fetchDashboardData(session);
        app.innerHTML = renderDashboard(session, fresh, replayRun, "Replay pipeline completed.");
        void wireDashboardActions(session);
      } catch (error) {
        void bootstrap(error instanceof Error ? error.message : "Replay pipeline failed.");
      }
    });
    document.querySelector<HTMLButtonElement>("#sign-out")?.addEventListener("click", () => {
      clearSession();
      void bootstrap("Signed out.");
    });
  } catch (error) {
    clearSession();
    await bootstrap(error instanceof Error ? error.message : "Dashboard bootstrap failed.");
  }
}

async function wireDashboardActions(session: Session): Promise<void> {
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
        void wireDashboardActions(session);
      }
    } catch (error) {
      void bootstrap(error instanceof Error ? error.message : "Replay pipeline failed.");
    }
  });
  document.querySelector<HTMLButtonElement>("#sign-out")?.addEventListener("click", () => {
    clearSession();
    void bootstrap("Signed out.");
  });
}

void bootstrap();