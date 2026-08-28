/**
 * WebSocket service for real-time event streaming from the backend.
 */
export type EventHandler = (event: PlatformEvent) => void;

export interface PlatformEvent {
  type: string;
  data: Record<string, unknown>;
  task_id?: string;
  timestamp: number;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Set<EventHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private _connected = false;

  get connected(): boolean {
    return this._connected;
  }

  connect(url?: string) {
    const wsUrl = url || `ws://${window.location.hostname}:8000/api/ws`;
    
    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this._connected = true;
        this.reconnectDelay = 1000;
        console.log('[WS] Connected');
        this.emit({ type: 'ws.connected', data: {}, timestamp: Date.now() / 1000 });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as PlatformEvent;
          this.emit(data);
        } catch (e) {
          console.warn('[WS] Failed to parse message:', event.data);
        }
      };

      this.ws.onclose = () => {
        this._connected = false;
        console.log('[WS] Disconnected');
        this.emit({ type: 'ws.disconnected', data: {}, timestamp: Date.now() / 1000 });
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };
    } catch (e) {
      console.error('[WS] Connection failed:', e);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      console.log('[WS] Reconnecting...');
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
  }

  subscribe(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  private emit(event: PlatformEvent) {
    this.handlers.forEach(handler => {
      try {
        handler(event);
      } catch (e) {
        console.error('[WS] Handler error:', e);
      }
    });
  }

  send(data: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
    this._connected = false;
  }
}

export const wsService = new WebSocketService();
