import { ensureFreshAuthSession } from "../shared/auth-session";
import { BACKEND_WS_URL } from "../shared/backend-config";

export type ConnectorMessage = {
  type: string;
  payload?: unknown;
};

export class BackendConnector {
  private ws: WebSocket | null = null;

  async connect(onMessage: (msg: ConnectorMessage) => void): Promise<void> {
    const session = await ensureFreshAuthSession().catch(() => null);
    if (!session) {
      return;
    }
    const params = new URLSearchParams({
      access_token: session.accessToken,
      device_id: session.deviceId,
    });
    this.ws = new WebSocket(`${BACKEND_WS_URL}?${params.toString()}`);
    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as ConnectorMessage;
        onMessage(parsed);
      } catch {
        onMessage({ type: "raw", payload: event.data });
      }
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  async reconnect(onMessage: (msg: ConnectorMessage) => void): Promise<void> {
    this.disconnect();
    await this.connect(onMessage);
  }

  send(message: ConnectorMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify(message));
  }
}
