import { BackendConnector } from "./connector";

const connector = new BackendConnector();

export function initRouter(): void {
  connector.connect((message) => {
    chrome.runtime.sendMessage({
      type: "backend_message",
      payload: message
    });
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "chat_message") {
      connector.send({ type: "chat_message", payload: msg.payload });
    }
  });
}
