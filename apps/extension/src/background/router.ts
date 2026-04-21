import { runApprovedActionBatch, snapshotPageContext } from "./action-runner";
import { BackendConnector } from "./connector";

const connector = new BackendConnector();

async function getActiveTabId(): Promise<number> {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const activeTabId = tabs[0]?.id;
  if (typeof activeTabId !== "number") {
    throw new Error("No active portal tab found");
  }
  return activeTabId;
}

export function initRouter(): void {
  connector.connect((message) => {
    if (message.type === "run_actions") {
      void (async () => {
        const tabId = await getActiveTabId();
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
  });

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "chat_message") {
      connector.send({ type: "chat_message", payload: msg.payload });
    }

    if (msg?.type === "page_detected") {
      chrome.runtime.sendMessage({
        type: "page_context",
        payload: msg.payload,
      });
    }

    if (msg?.type === "run_action_batch") {
      void (async () => {
        const tabId = msg.payload?.tabId ?? await getActiveTabId();
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
        const tabId = msg.payload?.tabId ?? await getActiveTabId();
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
        const tabId = msg.payload?.tabId ?? await getActiveTabId();
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

    return false;
  });
}
