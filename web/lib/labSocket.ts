/**
 * The client's connection to labd's event fan-out (§5.4.2, /api/ws).
 * Protocol: send {type:"hello", since}, then receive {type:"event", e}
 * for every event from `since` onward, or {type:"resync", since} if we
 * fell behind — at which point we just re-subscribe from that point.
 */

export interface LabEvent {
  seq: number;
  ts: string;
  kind: string;
  v: number;
  project: string | null;
  actor: string;
  corr: string | null;
  causation: number | null;
  payload: Record<string, unknown>;
  display?: Record<string, unknown> | null;
}

type EventHandler = (e: LabEvent) => void;
type StatusHandler = (status: "connecting" | "open" | "closed") => void;

export class LabSocket {
  private ws: WebSocket | null = null;
  private lastSeq = 0;
  private handlers: Set<EventHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private reconnectDelayMs = 1000;
  private readonly maxReconnectDelayMs = 15000;
  private closedByUser = false;

  constructor(private readonly url: string) {}

  onEvent(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  connect(sinceSeq = 0): void {
    this.closedByUser = false;
    this.lastSeq = sinceSeq;
    this.open();
  }

  close(): void {
    this.closedByUser = true;
    this.ws?.close();
  }

  private open(): void {
    this.emitStatus("connecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectDelayMs = 1000;
      this.emitStatus("open");
      ws.send(JSON.stringify({ type: "hello", since: this.lastSeq }));
    };

    ws.onmessage = (ev) => {
      let msg: { type: string; e?: LabEvent; since?: number };
      try {
        msg = JSON.parse(ev.data as string);
      } catch {
        return; // never let a bad frame crash the page
      }
      if (msg.type === "event" && msg.e) {
        this.lastSeq = Math.max(this.lastSeq, msg.e.seq);
        for (const h of this.handlers) h(msg.e);
      } else if (msg.type === "resync" && typeof msg.since === "number") {
        this.lastSeq = msg.since;
      }
    };

    ws.onclose = () => {
      this.emitStatus("closed");
      if (!this.closedByUser) this.scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose always follows onerror for a WebSocket — nothing to do here
    };
  }

  private scheduleReconnect(): void {
    setTimeout(() => {
      if (!this.closedByUser) this.open();
    }, this.reconnectDelayMs);
    this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, this.maxReconnectDelayMs);
  }

  private emitStatus(status: "connecting" | "open" | "closed"): void {
    for (const h of this.statusHandlers) h(status);
  }
}
