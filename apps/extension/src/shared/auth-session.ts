import { BACKEND_BASE_URL } from "./backend-config";

const AUTH_SESSION_KEY = "itx_auth_session";
const DEVICE_ID_KEY = "itx_device_id";

export type AuthSession = {
  userId: string;
  email: string;
  deviceId: string;
  sessionId: string;
  accessToken: string;
  refreshToken: string;
  accessExpiresAt: string;
  refreshExpiresAt: string;
};

type AuthRefreshResponse = {
  user_id: string;
  email: string;
  device_id: string;
  session_id: string;
  access_token: string;
  refresh_token: string;
  access_expires_at: string;
  refresh_expires_at: string;
};

function hydrateAuthSession(payload: AuthRefreshResponse): AuthSession {
  return {
    userId: payload.user_id,
    email: payload.email,
    deviceId: payload.device_id,
    sessionId: payload.session_id,
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    accessExpiresAt: payload.access_expires_at,
    refreshExpiresAt: payload.refresh_expires_at,
  };
}

function isExpiring(expiresAt: string, skewMs = 60_000): boolean {
  const expiry = Date.parse(expiresAt);
  if (Number.isNaN(expiry)) {
    return true;
  }
  return expiry <= Date.now() + skewMs;
}

export async function loadAuthSession(): Promise<AuthSession | null> {
  const data = await chrome.storage.local.get(AUTH_SESSION_KEY);
  return (data[AUTH_SESSION_KEY] as AuthSession | undefined) ?? null;
}

export async function saveAuthSession(session: AuthSession): Promise<void> {
  await chrome.storage.local.set({ [AUTH_SESSION_KEY]: session });
}

export async function clearAuthSession(): Promise<void> {
  await chrome.storage.local.remove(AUTH_SESSION_KEY);
}

export async function getOrCreateDeviceId(): Promise<string> {
  const stored = await chrome.storage.local.get(DEVICE_ID_KEY);
  const existing = stored[DEVICE_ID_KEY] as string | undefined;
  if (existing) {
    return existing;
  }
  const next = crypto.randomUUID();
  await chrome.storage.local.set({ [DEVICE_ID_KEY]: next });
  return next;
}

export function defaultDeviceName(): string {
  if (typeof navigator !== "undefined") {
    return `Chrome extension on ${navigator.platform || "unknown-platform"}`;
  }
  return "Chrome extension";
}

let inflightRefresh: Promise<AuthSession> | null = null;

async function refreshSession(current: AuthSession): Promise<AuthSession> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      refresh_token: current.refreshToken,
      device_id: current.deviceId,
    }),
  });
  if (!response.ok) {
    await clearAuthSession();
    throw new Error("Session refresh failed");
  }
  const payload = (await response.json()) as AuthRefreshResponse;
  const refreshed = hydrateAuthSession(payload);
  await saveAuthSession(refreshed);
  return refreshed;
}

export async function ensureFreshAuthSession(): Promise<AuthSession> {
  const current = await loadAuthSession();
  if (!current) {
    throw new Error("Authentication required");
  }
  if (!isExpiring(current.accessExpiresAt)) {
    return current;
  }
  if (isExpiring(current.refreshExpiresAt, 0)) {
    await clearAuthSession();
    throw new Error("Session expired");
  }

  // Ensure only one refresh is in flight at a time — the refresh token is
  // single-use on the backend, so parallel callers must share one result.
  if (!inflightRefresh) {
    inflightRefresh = refreshSession(current).finally(() => {
      inflightRefresh = null;
    });
  }
  return inflightRefresh;
}