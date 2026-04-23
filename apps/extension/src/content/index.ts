import { executeActionBatch } from "./actions";
import { PageObserver, PageSnapshot } from "./observer";

const LAUNCHER_ID = "itx-sidepanel-launcher";
const LAUNCHER_BASE_TRANSFORM = "translateY(-50%)";
const LAUNCHER_ACTIVE_TRANSFORM = "translateY(-50%) translateX(-6px)";

function ensureLauncherButton(): void {
  const existing = document.getElementById(LAUNCHER_ID);
  if (existing) {
    return;
  }

  const button = document.createElement("button");
  const icon = document.createElement("img");
  const iconFrame = document.createElement("span");
  const label = document.createElement("span");
  button.id = LAUNCHER_ID;
  button.type = "button";
  button.setAttribute("aria-label", "Open IncomeTax Agent");
  button.title = "Open IncomeTax Agent";
  icon.src = chrome.runtime.getURL("public/icons/icon48.png");
  icon.alt = "";
  icon.setAttribute("aria-hidden", "true");
  label.textContent = "IncomeTax Agent";
  Object.assign(button.style, {
    position: "fixed",
    top: "50%",
    right: "0",
    width: "46px",
    minHeight: "148px",
    borderRadius: "18px 0 0 18px",
    border: "1px solid rgba(18, 59, 143, 0.16)",
    borderRight: "none",
    background: "linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(238, 244, 255, 0.96) 100%)",
    boxShadow: "0 16px 34px rgba(15, 23, 42, 0.16)",
    cursor: "pointer",
    zIndex: "2147483647",
    padding: "12px 6px 14px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    transform: LAUNCHER_BASE_TRANSFORM,
    transition: "transform 160ms ease, box-shadow 160ms ease, background 160ms ease",
    backdropFilter: "blur(12px)",
  } satisfies Partial<CSSStyleDeclaration>);
  Object.assign(iconFrame.style, {
    width: "30px",
    height: "30px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "10px",
    background: "linear-gradient(135deg, #123b8f 0%, #1b61d1 100%)",
    boxShadow: "0 8px 18px rgba(18, 59, 143, 0.24)",
    flexShrink: "0",
  } satisfies Partial<CSSStyleDeclaration>);
  Object.assign(icon.style, {
    width: "18px",
    height: "18px",
    display: "block",
  } satisfies Partial<CSSStyleDeclaration>);
  Object.assign(label.style, {
    writingMode: "vertical-rl",
    transform: "rotate(180deg)",
    color: "#123b8f",
    fontSize: "11px",
    fontWeight: "700",
    letterSpacing: "0.08em",
    lineHeight: "1",
    textTransform: "uppercase",
    fontFamily: '"Avenir Next", "Helvetica Neue", sans-serif',
    userSelect: "none",
  } satisfies Partial<CSSStyleDeclaration>);

  const activateLauncher = () => {
    button.style.transform = LAUNCHER_ACTIVE_TRANSFORM;
    button.style.boxShadow = "0 20px 40px rgba(15, 23, 42, 0.22)";
    button.style.background = "linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, rgba(226, 237, 255, 0.98) 100%)";
  };

  const deactivateLauncher = () => {
    button.style.transform = LAUNCHER_BASE_TRANSFORM;
    button.style.boxShadow = "0 16px 34px rgba(15, 23, 42, 0.16)";
    button.style.background = "linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(238, 244, 255, 0.96) 100%)";
  };

  button.addEventListener("mouseenter", activateLauncher);
  button.addEventListener("mouseleave", deactivateLauncher);
  button.addEventListener("focus", activateLauncher);
  button.addEventListener("blur", deactivateLauncher);

  iconFrame.appendChild(icon);
  button.appendChild(iconFrame);
  button.appendChild(label);

  button.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "open_side_panel", payload: {} }, () => {
      if (chrome.runtime.lastError) {
        console.warn("side panel launcher failed", chrome.runtime.lastError.message);
      }
    });
  });

  document.body.appendChild(button);
}

const observer = new PageObserver();
observer.start();

function currentSnapshot(): PageSnapshot {
  return observer.snapshot();
}

function postSnapshot(snapshot: PageSnapshot): void {
  chrome.runtime.sendMessage(
    {
      type: "page_detected",
      payload: snapshot,
    },
    () => {
      // Swallow runtime errors — the service worker may be idle; the next snapshot retries.
      void chrome.runtime.lastError;
    }
  );
}

observer.subscribe((snapshot) => postSnapshot(snapshot));
postSnapshot(currentSnapshot());

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
            pageContext: currentSnapshot(),
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
    sendResponse({ ok: true, payload: currentSnapshot() });
  }

  return false;
});
