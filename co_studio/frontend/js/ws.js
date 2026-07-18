// ============================================================
// ws.js — reconnecting WebSocket wrappers
//   /ws/status              → {"type":"status","agents":[AgentSummary]}
//   /ws/agents/{slug}/logs  → {"source":"stdout"|"logger","line":str}
// ============================================================

function wsUrl(path) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}${path}`;
}

export class ReconnectingSocket {
  /**
   * @param {string} path e.g. "/ws/status"
   * @param {{onMessage?:Function,onOpen?:Function,onClose?:Function}} handlers
   */
  constructor(path, handlers = {}, { heartbeatMs = 0 } = {}) {
    this.path = path;
    this.handlers = handlers;
    this.heartbeatMs = heartbeatMs;   // >0 ⇒ treat "no frame for this long" as dead
    this.closed = false;
    this.attempt = 0;
    this.timer = null;
    this.hbTimer = null;
    this.ws = null;
    this._connect();
  }

  _connect() {
    if (this.closed) return;
    let ws;
    try {
      ws = new WebSocket(wsUrl(this.path));
    } catch {
      this._scheduleRetry();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      this._resetHeartbeat();
      this.handlers.onOpen?.();
    };
    ws.onmessage = (ev) => {
      this._resetHeartbeat();   // any frame proves the backend is alive
      let data;
      try {
        data = JSON.parse(ev.data);
      } catch {
        return; // ignore non-JSON frames
      }
      this.handlers.onMessage?.(data);
    };
    ws.onclose = () => {
      clearTimeout(this.hbTimer);
      if (this.closed) return;
      this.handlers.onClose?.();
      this._scheduleRetry();
    };
    ws.onerror = () => {
      try { ws.close(); } catch { /* noop */ }
    };
  }

  _scheduleRetry() {
    if (this.closed) return;
    const delay = Math.min(10_000, 1000 * 2 ** Math.min(this.attempt, 4));
    this.attempt += 1;
    this.timer = setTimeout(() => this._connect(), delay);
  }

  _resetHeartbeat() {
    if (!this.heartbeatMs) return;
    clearTimeout(this.hbTimer);
    // The server pushes a status frame every ~5s. No frame for heartbeatMs ⇒ the backend
    // is gone even if the socket still looks open (hung/orphaned process). Force a close so
    // onclose fires the disconnect handler and reconnection begins.
    this.hbTimer = setTimeout(() => {
      try { this.ws?.close(); } catch { /* onclose handles retry */ }
    }, this.heartbeatMs);
  }

  close() {
    this.closed = true;
    clearTimeout(this.timer);
    clearTimeout(this.hbTimer);
    if (this.ws) {
      this.ws.onclose = null;
      try { this.ws.close(); } catch { /* noop */ }
    }
  }
}

/** Global agent-state stream. onAgents(list) on every push (state changes + 5s heartbeat). */
export function statusSocket(onAgents, onConnChange) {
  return new ReconnectingSocket('/ws/status', {
    onMessage: (d) => {
      if (d && d.type === 'status' && Array.isArray(d.agents)) onAgents(d.agents);
    },
    onOpen: () => onConnChange?.(true),
    onClose: () => onConnChange?.(false),
  }, { heartbeatMs: 12_000 });   // server heartbeats every ~5s; 12s of silence ⇒ disconnected
}

/** Per-agent live log stream. onLine({source, line}) per log line. */
export function logSocket(slug, onLine, onConnChange) {
  return new ReconnectingSocket(`/ws/agents/${encodeURIComponent(slug)}/logs`, {
    onMessage: (d) => {
      if (d && typeof d.line === 'string') onLine(d);
    },
    onOpen: () => onConnChange?.(true),
    onClose: () => onConnChange?.(false),
  });
}
