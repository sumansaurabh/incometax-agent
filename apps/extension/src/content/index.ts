import { detectPage } from "./page-detector";

const context = detectPage(document);

chrome.runtime.sendMessage({
  type: "page_detected",
  payload: {
    page: context.page,
    title: document.title,
    url: window.location.href,
    fields: context.fields,
    validationErrors: context.validationErrors
  }
});
