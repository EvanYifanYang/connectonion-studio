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
  constructor(path, handlers = {}) {
    this.path = path;
    this.handlers = handlers;
    this.closed = false;
    this.attempt = 0;
    this.timer = null;
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
      this.handlers.onOpen?.();
    };
    ws.onmessage = (ev) => {
      let data;
      try {
        data = JSON.parse(ev.data);
      } catch {
        return; // ignore non-JSON frames
      }
      this.handlers.onMessage?.(data);
    };
    ws.onclose = () => {
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

  close() {
    this.closed = true;
    clearTimeout(this.timer);
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
  });
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
