type ActionBatchResponse = {
  ok: boolean;
  payload?: unknown;
  error?: string;
};

function sendToTab<T>(tabId: number, message: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response: T) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(response);
    });
  });
}

export async function runApprovedAction(action: unknown, tabId: number): Promise<ActionBatchResponse> {
  return sendToTab<ActionBatchResponse>(tabId, {
    type: "execute_action_batch",
    payload: { actions: [action] },
  });
}

export async function runApprovedActionBatch(actions: unknown[], tabId: number): Promise<ActionBatchResponse> {
  return sendToTab<ActionBatchResponse>(tabId, {
    type: "execute_action_batch",
    payload: { actions },
  });
}

export async function snapshotPageContext(tabId: number): Promise<ActionBatchResponse> {
  return sendToTab<ActionBatchResponse>(tabId, {
    type: "snapshot_page_context",
  });
}

export type ViewportCapture = {
  mediaType: "image/jpeg";
  dataUrl: string;
  dataBase64: string;
  sizeBytes: number;
  viewport: { width: number; height: number };
  capturedAt: string;
};

/**
 * Capture the visible viewport of the given tab as a JPEG.
 *
 * JPEG at quality 70 keeps payload size well below the 5 MB Chrome limit on the returned
 * data URL and well under Anthropic's image-size budget while remaining legible. No
 * debugger attach, so no scary banner appears on the user's trusted portal tab.
 */
export async function captureVisibleViewport(windowId: number, tab: chrome.tabs.Tab): Promise<ViewportCapture> {
  const dataUrl = await chrome.tabs.captureVisibleTab(windowId, { format: "jpeg", quality: 70 });
  if (!dataUrl) {
    throw new Error("captureVisibleTab returned an empty data URL");
  }
  const [prefix, base64 = ""] = dataUrl.split(",");
  if (!prefix?.startsWith("data:image/jpeg")) {
    throw new Error("unexpected screenshot format");
  }
  // base64 length → byte count. 4 base64 chars = 3 bytes (minus padding).
  const padding = base64.endsWith("==") ? 2 : base64.endsWith("=") ? 1 : 0;
  const sizeBytes = Math.max(0, Math.floor((base64.length * 3) / 4) - padding);

  return {
    mediaType: "image/jpeg",
    dataUrl,
    dataBase64: base64,
    sizeBytes,
    viewport: {
      width: tab.width ?? 0,
      height: tab.height ?? 0,
    },
    capturedAt: new Date().toISOString(),
  };
}
