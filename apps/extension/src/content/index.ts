import { executeActionBatch } from "./actions";
import { detectPage } from "./page-detector";

function buildPageContext(): {
  page: string;
  title: string;
  url: string;
  fields: unknown;
  validationErrors: unknown;
} {
  const context = detectPage(document);
  return {
    page: context.page,
    title: document.title,
    url: window.location.href,
    fields: context.fields,
    validationErrors: context.validationErrors,
  };
}

chrome.runtime.sendMessage({
  type: "page_detected",
  payload: buildPageContext(),
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "execute_action_batch") {
    void executeActionBatch(message.payload?.actions ?? [])
      .then((result) => {
        sendResponse({
          ok: true,
          payload: {
            ...result,
            pageContext: buildPageContext(),
          },
        });
      })
      .catch((error: unknown) => {
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "unknown_error",
        });
      });
    return true;
  }

  if (message?.type === "snapshot_page_context") {
    sendResponse({ ok: true, payload: buildPageContext() });
  }

  return false;
});
