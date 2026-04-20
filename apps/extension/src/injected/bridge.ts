window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (event.data?.type !== "ITX_BRIDGE") return;
  window.postMessage({ type: "ITX_BRIDGE_ACK", payload: event.data.payload }, "*");
});
