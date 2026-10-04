"use client";

/** WebSocket client for run streams: replays the persisted event log first,
 *  then follows live; auto-reconnects with backoff while the run is active.
 *  Tries same-origin /ws first (Next rewrite), then port-swapped sandbox host.
 */
import type { WSEvent } from "./types";

type Handlers = {
  onEvent: (ev: WSEvent) => void;
  onState?: (state: "connecting" | "open" | "closed" | "error") => void;
  shouldContinue?: () => boolean; // keep reconnecting while true
};

export class RunSocket {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private closedByUser = false;
  private cursor: number;
  private usedFallback = false;

  constructor(private runId: string, after: number, private h: Handlers) {
    this.cursor = after;
  }

  private urls(): string[] {
    if (process.env.NEXT_PUBLIC_WS_URL) return [`${process.env.NEXT_PUBLIC_WS_URL}/runs/${this.runId}?after=${this.cursor}`];
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const urls = [`${proto}://${window.location.host}/ws/runs/${this.runId}?after=${this.cursor}`];
    const m = window.location.hostname.match(/^\d+-(.+)$/);
    if (m) urls.push(`${proto}://8000-${m[1]}/ws/runs/${this.runId}?after=${this.cursor}`);
    return urls;
  }

  connect() {
    this.h.onState?.("connecting");
    const url = this.urls()[this.usedFallback ? 1 : 0] || this.urls()[0];
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      this.scheduleReconnect(true);
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      this.h.onState?.("open");
    };
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as WSEvent;
        if (typeof ev.seq === "number") this.cursor = Math.max(this.cursor, ev.seq);
        if (ev.type !== "ping") this.h.onEvent(ev);
      } catch { /* ignore malformed frames */ }
    };
    ws.onerror = () => {
      this.h.onState?.("error");
    };
    ws.onclose = () => {
      this.h.onState?.("closed");
      if (!this.closedByUser && (this.h.shouldContinue?.() ?? true)) this.scheduleReconnect();
    };
  }

  private scheduleReconnect(swapHost = false) {
    if (swapHost && !this.usedFallback) {
      this.usedFallback = true;
      setTimeout(() => this.connect(), 100);
      return;
    }
    const delay = Math.min(8000, 500 * 2 ** this.attempt++);
    setTimeout(() => {
      if (!this.closedByUser) this.connect();
    }, delay);
    // alternate hosts on repeated failures
    if (this.attempt > 2 && this.urls().length > 1) {
      this.usedFallback = !this.usedFallback;
      this.attempt = 0;
    }
  }

  close() {
    this.closedByUser = true;
    this.ws?.close();
  }
}
