import { executeActionBatch } from "./actions";
import { readField } from "./actions/read";
import { detectPage } from "./page-detector";

function buildPageContext(): {
  page: string;
  title: string;
  url: string;
  fields: unknown;
  validationErrors: unknown;
  portalState: {
    page: string;
    fields: Record<string, { value: string | null; fieldKey: string; label: string; required: boolean }>;
    validationErrors: unknown;
  };
} {
  const context = detectPage(document);
  const portalFields = Object.fromEntries(
    context.fields
      .filter((field) => Boolean(field.selectorHint))
      .map((field) => [
        field.selectorHint as string,
        {
          value: readField(field.selectorHint as string),
          fieldKey: field.key,
          label: field.label,
          required: field.required,
        },
      ])
  );

  return {
    page: context.page,
    title: document.title,
    url: window.location.href,
    fields: context.fields,
    validationErrors: context.validationErrors,
    portalState: {
      page: context.page,
      fields: portalFields,
      validationErrors: context.validationErrors,
    },
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
