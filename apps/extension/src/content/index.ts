import { detectPage } from "./page-detector";
import { getValidationErrors } from "./actions/validation";

const page = detectPage(document.title);

chrome.runtime.sendMessage({
  type: "page_detected",
  payload: {
    page,
    title: document.title,
    url: window.location.href,
    validationErrors: getValidationErrors()
  }
});
