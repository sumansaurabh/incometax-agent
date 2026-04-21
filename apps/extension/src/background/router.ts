import { runApprovedActionBatch, snapshotPageContext } from "./action-runner";
import { BackendConnector } from "./connector";

const connector = new BackendConnector();

type TrustStatus = {
  status: "verified" | "lookalike" | "unsupported" | "missing";
  host: string | null;
  url: string | null;
  canOperate: boolean;
  message: string;
};

function classifyTrust(url: string | undefined): TrustStatus {
  if (!url) {
    return {
      status: "missing",
      host: null,
      url: null,
      canOperate: false,
      message: "Open the official Income Tax portal to enable guided filing.",
    };
  }

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return {
      status: "unsupported",
      host: null,
      url,
      canOperate: false,
      message: "Unable to verify the active tab URL. Automation is suspended.",
    };
  }
  const host = parsed.host.toLowerCase();
  if (host === "www.incometax.gov.in" || host === "incometax.gov.in") {
    return {
      status: "verified",
      host,
      url,
      canOperate: true,
      message: "Verified official e-Filing portal.",
    };
  }
  if (host.includes("incometax") || host.includes("gov.in")) {
    return {
      status: "lookalike",
      host,
      url,
      canOperate: false,
      message: "Potential lookalike domain detected. Automation is suspended.",
    };
  }
  return {
    status: "unsupported",
    host,
    url,
    canOperate: false,
    message: "Automation is available only on the official e-Filing portal.",
  };
}

async function getActiveTab(): Promise<chrome.tabs.Tab> {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const activeTab = tabs[0];
  if (!activeTab) {
    throw new Error("No active portal tab found");
  }
  return activeTab;
}

async function getActiveTrustStatus(): Promise<TrustStatus> {
  const activeTab = await getActiveTab().catch(() => null);
  return classifyTrust(activeTab?.url);
}

async function getTrustedActiveTabId(): Promise<number> {
  const activeTab = await getActiveTab();
  const trust = classifyTrust(activeTab.url);
  if (!trust.canOperate || typeof activeTab.id !== "number") {
    throw new Error(trust.message);
  }
  return activeTab.id;
}

async function emitActiveTrustStatus(): Promise<void> {
  chrome.runtime.sendMessage({
    type: "trust_status",
    payload: await getActiveTrustStatus(),
  });
}

export function initRouter(): void {
  const forwardBackendMessage = (message: { type: string; payload?: unknown }) => {
    if (message.type === "run_actions") {
      void (async () => {
        const tabId = await getTrustedActiveTabId();
        const result = await runApprovedActionBatch((message.payload as { actions?: unknown[] })?.actions ?? [], tabId);
        connector.send({ type: "action_batch_result", payload: result });
      })().catch((error: unknown) => {
        connector.send({
          type: "action_batch_result",
          payload: {
            ok: false,
            error: error instanceof Error ? error.message : "unknown_error",
          },
        });
      });
      return;
    }

    chrome.runtime.sendMessage({
      type: "backend_message",
      payload: message
    });
  };

  void connector.connect(forwardBackendMessage);

  chrome.tabs.onActivated.addListener(() => {
    void emitActiveTrustStatus();
  });
  chrome.tabs.onUpdated.addListener((_tabId, _changeInfo, tab) => {
    if (tab.active) {
      void emitActiveTrustStatus();
    }
  });

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "chat_message") {
      connector.send({ type: "chat_message", payload: msg.payload });
    }

    if (msg?.type === "page_detected") {
      const trust = classifyTrust(msg.payload?.url);
      chrome.runtime.sendMessage({
        type: "page_context",
        payload: msg.payload,
      });
      chrome.runtime.sendMessage({ type: "trust_status", payload: trust });
    }

    if (msg?.type === "run_action_batch") {
      void (async () => {
        const tabId = msg.payload?.tabId ?? await getTrustedActiveTabId();
        const result = await runApprovedActionBatch(msg.payload?.actions ?? [], tabId);
        sendResponse(result);
      })().catch((error: unknown) => {
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "unknown_error",
        });
      });
      return true;
    }

    if (msg?.type === "snapshot_active_page") {
      void (async () => {
        const tabId = msg.payload?.tabId ?? await getTrustedActiveTabId();
        const result = await snapshotPageContext(tabId);
        sendResponse(result);
      })().catch((error: unknown) => {
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "unknown_error",
        });
      });
      return true;
    }

    if (msg?.type === "navigate_active_tab") {
      void (async () => {
        const nextTrust = classifyTrust(msg.payload?.url);
        if (!nextTrust.canOperate) {
          throw new Error(nextTrust.message);
        }
        const tabId = msg.payload?.tabId ?? await getTrustedActiveTabId();
        const updated = await chrome.tabs.update(tabId, { url: msg.payload?.url });
        sendResponse({ ok: true, payload: { tabId: updated.id, url: updated.url } });
      })().catch((error: unknown) => {
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "unknown_error",
        });
      });
      return true;
    }

    if (msg?.type === "get_active_tab_trust") {
      void getActiveTrustStatus()
        .then((trust) => sendResponse({ ok: true, payload: trust }))
        .catch((error: unknown) => sendResponse({ ok: false, error: error instanceof Error ? error.message : "unknown_error" }));
      return true;
    }

    if (msg?.type === "auth_session_updated") {
      void connector.reconnect(forwardBackendMessage);
      void emitActiveTrustStatus();
      sendResponse({ ok: true });
      return false;
    }

    if (msg?.type === "auth_session_cleared") {
      connector.disconnect();
      void emitActiveTrustStatus();
      sendResponse({ ok: true });
      return false;
    }

    return false;
  });
}
