import { executeActionBatch } from "./actions";
import { readField } from "./actions/read";
import { detectPage } from "./page-detector";

const LAUNCHER_ID = "itx-sidepanel-launcher";

function ensureLauncherButton(): void {
  const existing = document.getElementById(LAUNCHER_ID);
  if (existing) {
    return;
  }

  const button = document.createElement("button");
  const icon = document.createElement("img");
  button.id = LAUNCHER_ID;
  button.type = "button";
  button.setAttribute("aria-label", "Open IncomeTax Agent");
  button.title = "Open IncomeTax Agent";
  icon.src = chrome.runtime.getURL("public/icons/icon48.png");
  icon.alt = "";
  icon.setAttribute("aria-hidden", "true");
  Object.assign(button.style, {
    position: "fixed",
    top: "50%",
    right: "18px",
    width: "58px",
    height: "58px",
    borderRadius: "18px",
    border: "1px solid rgba(18, 59, 143, 0.16)",
    background: "rgba(255, 255, 255, 0.96)",
    boxShadow: "0 18px 36px rgba(15, 23, 42, 0.18)",
    cursor: "pointer",
    zIndex: "2147483647",
    padding: "0",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transform: "translateY(-50%)",
    backdropFilter: "blur(10px)",
  } satisfies Partial<CSSStyleDeclaration>);
  Object.assign(icon.style, {
    width: "32px",
    height: "32px",
    display: "block",
  } satisfies Partial<CSSStyleDeclaration>);

  button.appendChild(icon);

  button.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "open_side_panel", payload: {} }, () => {
      if (chrome.runtime.lastError) {
        console.warn("side panel launcher failed", chrome.runtime.lastError.message);
      }
    });
  });

  document.body.appendChild(button);
}

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

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => ensureLauncherButton(), { once: true });
} else {
  ensureLauncherButton();
}

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
