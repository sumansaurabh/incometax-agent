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
