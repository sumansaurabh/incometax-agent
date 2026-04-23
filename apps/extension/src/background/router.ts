import { captureVisibleViewport, runApprovedActionBatch, snapshotPageContext, ViewportCapture } from "./action-runner";
import { BackendConnector } from "./connector";

const connector = new BackendConnector();
const SIDEPANEL_PATH = "public/sidepanel.html";

type TrustStatus = {
  status: "verified" | "lookalike" | "unsupported" | "missing";
  host: string | null;
  url: string | null;
  canOperate: boolean;
  message: string;
};

function postRuntimeMessage(message: { type: string; payload?: unknown }): void {
  chrome.runtime.sendMessage(message, () => {
    const error = chrome.runtime.lastError;
    if (!error) {
      return;
    }
    if (error.message?.includes("Receiving end does not exist")) {
      return;
    }
    console.warn("runtime message delivery failed", message.type, error.message);
  });
}

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
  if (host === "incometax.gov.in" || host.endsWith(".incometax.gov.in")) {
    return {
      status: "verified",
      host,
      url,
      canOperate: true,
      message: "E-Filing portal domain.",
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

async function syncSidePanelForTab(tab: chrome.tabs.Tab | null | undefined): Promise<TrustStatus> {
  const trust = classifyTrust(tab?.url);
  if (!tab || typeof tab.id !== "number") {
    return trust;
  }
  try {
    await chrome.sidePanel.setOptions({
      tabId: tab.id,
      path: SIDEPANEL_PATH,
      enabled: trust.canOperate,
    });
  } catch (error) {
    console.warn("side panel tab sync failed", error);
  }
  return trust;
}

async function syncActiveSidePanel(): Promise<TrustStatus> {
  const activeTab = await getActiveTab().catch(() => null);
  return syncSidePanelForTab(activeTab);
}

async function syncAllTabs(): Promise<void> {
  const tabs = await chrome.tabs.query({}).catch(() => []);
  await Promise.all(tabs.map((tab) => syncSidePanelForTab(tab)));
}

async function configurePanelBehavior(): Promise<void> {
  try {
    // Do NOT auto-open on action click — we only want the panel visible on the
    // trusted e-Filing portal. `action.onClicked` below opens it explicitly
    // and only when the active tab passes the trust check.
    await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });
  } catch (error) {
    console.warn("side panel behavior setup failed", error);
  }
}

async function openSidePanelForTab(tab: chrome.tabs.Tab | null | undefined): Promise<void> {
  const trust = await syncSidePanelForTab(tab);
  if (!tab || typeof tab.id !== "number" || !trust.canOperate) {
    throw new Error(trust.message);
  }
  await chrome.sidePanel.open({ tabId: tab.id });
}

async function getTrustedActiveTabId(): Promise<number> {
  const activeTab = await getActiveTab();
  const trust = classifyTrust(activeTab.url);
  if (!trust.canOperate || typeof activeTab.id !== "number") {
    throw new Error(trust.message);
  }
  return activeTab.id;
}

async function captureTrustedActiveViewport(): Promise<ViewportCapture> {
  const activeTab = await getActiveTab();
  const trust = classifyTrust(activeTab.url);
  if (!trust.canOperate) {
    throw new Error(`trust_denied:${trust.status}`);
  }
  const windowId = typeof activeTab.windowId === "number" ? activeTab.windowId : chrome.windows.WINDOW_ID_CURRENT;
  return captureVisibleViewport(windowId, activeTab);
}

async function emitActiveTrustStatus(): Promise<void> {
  postRuntimeMessage({
    type: "trust_status",
    payload: await syncActiveSidePanel(),
  });
}

export function initRouter(): void {
  void configurePanelBehavior();
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

    if (message.type === "capture_viewport_request") {
      const requestId = (message.payload as { request_id?: string } | undefined)?.request_id ?? "";
      void (async () => {
        const capture = await captureTrustedActiveViewport();
        connector.send({
          type: "capture_viewport_result",
          payload: {
            request_id: requestId,
            ok: true,
            media_type: capture.mediaType,
            data_base64: capture.dataBase64,
            size_bytes: capture.sizeBytes,
            viewport: capture.viewport,
            captured_at: capture.capturedAt,
          },
        });
      })().catch((error: unknown) => {
        connector.send({
          type: "capture_viewport_result",
          payload: {
            request_id: requestId,
            ok: false,
            error: error instanceof Error ? error.message : "unknown_error",
          },
        });
      });
      return;
    }

    postRuntimeMessage({
      type: "backend_message",
      payload: message
    });
  };

  void connector.connect(forwardBackendMessage);
  void syncAllTabs().then(() => emitActiveTrustStatus());

  chrome.runtime.onInstalled.addListener(() => {
    void configurePanelBehavior();
    void syncAllTabs().then(() => emitActiveTrustStatus());
  });

  chrome.runtime.onStartup.addListener(() => {
    void configurePanelBehavior();
    void syncAllTabs().then(() => emitActiveTrustStatus());
  });

  chrome.action.onClicked.addListener((tab) => {
    void openSidePanelForTab(tab).catch((error: unknown) => {
      const trust = classifyTrust(tab.url);
      postRuntimeMessage({ type: "trust_status", payload: trust });
      console.warn("side panel open failed", error instanceof Error ? error.message : error);
    });
  });

  chrome.tabs.onActivated.addListener(({ tabId }) => {
    void (async () => {
      const tab = await chrome.tabs.get(tabId).catch(() => null);
      const trust = await syncSidePanelForTab(tab);
      postRuntimeMessage({ type: "trust_status", payload: trust });
    })();
  });
  chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
    // Re-evaluate on URL changes for every tab, not just the active one —
    // otherwise a background tab that navigates to a non-portal URL keeps the
    // panel enabled and it reappears when the user switches to it.
    if (changeInfo.url || changeInfo.status === "complete") {
      void syncSidePanelForTab(tab);
    }
    if (tab.active) {
      void emitActiveTrustStatus();
    }
  });

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg?.type === "chat_message") {
      connector.send({ type: "chat_message", payload: msg.payload });
    }

    if (msg?.type === "page_detected") {
      const trust = classifyTrust(msg.payload?.url);
      void syncSidePanelForTab(sender.tab);
      postRuntimeMessage({
        type: "page_context",
        payload: msg.payload,
      });
      postRuntimeMessage({ type: "trust_status", payload: trust });
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

    if (msg?.type === "capture_viewport") {
      void (async () => {
        const capture = await captureTrustedActiveViewport();
        sendResponse({
          ok: true,
          payload: {
            media_type: capture.mediaType,
            data_base64: capture.dataBase64,
            size_bytes: capture.sizeBytes,
            viewport: capture.viewport,
            captured_at: capture.capturedAt,
          },
        });
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

    if (msg?.type === "open_side_panel") {
      // `chrome.sidePanel.open` requires an active user gesture. The gesture
      // propagates through `runtime.onMessage` from a content-script click,
      // but ANY await before calling open() loses it. Call it synchronously
      // using sender.tab — the content script only runs on the trusted
      // portal host per manifest, so we already know the tab is trusted.
      const tabId = sender.tab?.id;
      const windowId = sender.tab?.windowId;
      if (typeof tabId !== "number") {
        sendResponse({ ok: false, error: "missing_tab_context" });
        return false;
      }

      chrome.sidePanel.setOptions({ tabId, path: SIDEPANEL_PATH, enabled: true }).catch(() => undefined);
      const openArgs: chrome.sidePanel.OpenOptions =
        typeof windowId === "number" ? { tabId, windowId } : { tabId };
      chrome.sidePanel.open(openArgs).then(
        () => sendResponse({ ok: true }),
        (error: unknown) => {
          console.warn("side panel open failed", error);
          sendResponse({
            ok: false,
            error: error instanceof Error ? error.message : "unknown_error",
          });
        }
      );
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
