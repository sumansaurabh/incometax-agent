export type ConnectorMessage = {
  type: string;
  payload?: unknown;
};

const WS_URL = "ws://localhost:8000/ws";

export class BackendConnector {
  private ws: WebSocket | null = null;

  connect(onMessage: (msg: ConnectorMessage) => void): void {
    this.ws = new WebSocket(WS_URL);
    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as ConnectorMessage;
        onMessage(parsed);
      } catch {
        onMessage({ type: "raw", payload: event.data });
      }
    };
  }

  send(message: ConnectorMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify(message));
  }
}
