/**
 * Live Data Source and Connection State Machine (T17-001, Contracts C8, C10).
 *
 * Implements:
 * - State machine: LIVE | STALE | RECONNECTING | WAITING | DISCONNECTED | REPLAY-SOURCE
 * - First-frame auth ticket transmission (never passed via URL)
 * - REST resync on reconnect and 'dropped' events without duplicate samples
 * - Exponential backoff reconnection
 * - Mockable socket factory for unit testing
 */

import {
  ConnectionState,
  EventRecord,
  LiveEventClosed,
  LiveEventOpen,
  LiveEventUpdate,
  LiveSampleEvent,
  ScoredSample,
  SnapshotEvent,
} from '../types/contracts';

export interface WebSocketLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((event: unknown) => void) | null;
  onclose: ((event: { code: number; reason: string }) => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: ((event: unknown) => void) | null;
}

export interface LiveClientConfig {
  wsUrl: string;
  httpBaseUrl: string;
  getTicket?: () => Promise<string> | string;
  ticket?: string;
  staleTimeoutMs?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  webSocketFactory?: (url: string) => WebSocketLike;
  fetchFn?: typeof fetch;
}

export type LiveClientListener = {
  onStateChange?: (state: ConnectionState) => void;
  onSample?: (sample: ScoredSample) => void;
  onSnapshot?: (snapshot: SnapshotEvent) => void;
  onEvent?: (event: EventRecord, action: 'OPEN' | 'UPDATE' | 'CLOSED') => void;
  onAlert?: (alert: Record<string, unknown>) => void;
  onError?: (err: Error) => void;
};

export class LiveClient {
  private config: LiveClientConfig;
  private state: ConnectionState = 'DISCONNECTED';
  private ws: WebSocketLike | null = null;
  private currentSessionId: string | null = null;
  private lastSeq: number = 0;
  private samples: ScoredSample[] = [];
  private sampleSeqs: Set<number> = new Set();
  private events: Map<string, EventRecord> = new Map();
  private staleTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoffMs: number;
  private isExplicitlyClosed: boolean = false;
  private listeners: Set<LiveClientListener> = new Set();

  constructor(config: LiveClientConfig) {
    if (config.wsUrl.includes('ticket=')) {
      throw new Error(
        'Security Guardrail: Ticket must never appear in the WebSocket URL'
      );
    }
    this.config = {
      staleTimeoutMs: 15000,
      initialBackoffMs: 1000,
      maxBackoffMs: 16000,
      fetchFn: typeof fetch !== 'undefined' ? fetch : undefined,
      ...config,
    };
    this.backoffMs = this.config.initialBackoffMs ?? 1000;
  }

  public getState(): ConnectionState {
    return this.state;
  }

  public getSessionId(): string | null {
    return this.currentSessionId;
  }

  public getSamples(): ScoredSample[] {
    return [...this.samples];
  }

  public getEvents(): EventRecord[] {
    return Array.from(this.events.values());
  }

  public subscribe(listener: LiveClientListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public async connect(): Promise<void> {
    this.isExplicitlyClosed = false;
    this.clearTimers();
    this.setState('WAITING');

    let ticketToUse = this.config.ticket;
    if (!ticketToUse && this.config.getTicket) {
      try {
        ticketToUse = await this.config.getTicket();
      } catch (err) {
        this.emitError(err instanceof Error ? err : new Error(String(err)));
        this.scheduleReconnect();
        return;
      }
    }

    const wsFactory =
      this.config.webSocketFactory ??
      ((url: string) => new WebSocket(url) as unknown as WebSocketLike);

    try {
      this.ws = wsFactory(this.config.wsUrl);
    } catch (err) {
      this.emitError(err instanceof Error ? err : new Error(String(err)));
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      // First frame auth required by Contract C10 / T18-003
      if (ticketToUse && this.ws) {
        this.ws.send(JSON.stringify({ type: 'auth', ticket: ticketToUse }));
      }
      this.backoffMs = this.config.initialBackoffMs ?? 1000;
      this.resetStaleTimer();
    };

    this.ws.onmessage = (event: { data: string }) => {
      this.handleMessage(event.data);
    };

    this.ws.onclose = () => {
      this.clearStaleTimer();
      if (!this.isExplicitlyClosed) {
        this.scheduleReconnect();
      } else {
        this.setState('DISCONNECTED');
      }
    };

    this.ws.onerror = (err: unknown) => {
      this.emitError(new Error(`WebSocket error: ${JSON.stringify(err)}`));
    };
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    this.clearTimers();
    if (this.ws) {
      this.ws.close(1000, 'User disconnect');
      this.ws = null;
    }
    this.setState('DISCONNECTED');
  }

  public setReplayMode(): void {
    this.disconnect();
    this.setState('REPLAY-SOURCE');
  }

  public async resync(sessionId: string): Promise<void> {
    const fetcher = this.config.fetchFn;
    if (!fetcher) return;

    try {
      const url = `${this.config.httpBaseUrl}/api/v1/sessions/${encodeURIComponent(
        sessionId
      )}/samples?since_seq=${this.lastSeq}&limit=1000`;
      const res = await fetcher(url);
      if (!res.ok) return;

      const data = await res.json();
      const newSamples: ScoredSample[] = data.samples || [];

      for (const sample of newSamples) {
        this.addSampleWithoutDuplicates(sample);
      }
    } catch (err) {
      this.emitError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  private handleMessage(raw: string): void {
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }

    this.resetStaleTimer();

    const type = msg.type as string;

    if (type === 'snapshot') {
      const snap = msg as unknown as SnapshotEvent;
      this.currentSessionId = snap.session_id;
      if (snap.latest_sample) {
        this.addSampleWithoutDuplicates(snap.latest_sample);
      }
      for (const ev of snap.open_events || []) {
        this.events.set(ev.event_id, ev);
      }
      this.setState('LIVE');
      for (const l of this.listeners) l.onSnapshot?.(snap);
    } else if (type === 'sample') {
      const ev = msg as unknown as LiveSampleEvent;
      this.currentSessionId = ev.session_id;
      this.addSampleWithoutDuplicates(ev.sample);
      this.setState('LIVE');
      for (const l of this.listeners) l.onSample?.(ev.sample);
    } else if (type === 'event_open') {
      const ev = msg as unknown as LiveEventOpen;
      this.events.set(ev.event.event_id, ev.event);
      for (const l of this.listeners) l.onEvent?.(ev.event, 'OPEN');
    } else if (type === 'event_update') {
      const ev = msg as unknown as LiveEventUpdate;
      this.events.set(ev.event.event_id, ev.event);
      for (const l of this.listeners) l.onEvent?.(ev.event, 'UPDATE');
    } else if (type === 'event_closed') {
      const ev = msg as unknown as LiveEventClosed;
      this.events.set(ev.event.event_id, ev.event);
      for (const l of this.listeners) l.onEvent?.(ev.event, 'CLOSED');
    } else if (type === 'dropped') {
      if (this.currentSessionId) {
        this.resync(this.currentSessionId);
      }
    } else if (type === 'alert') {
      const alert = (msg.alert as Record<string, unknown>) || msg;
      for (const l of this.listeners) l.onAlert?.(alert);
    } else if (type === 'heartbeat') {
      if (this.state === 'STALE') {
        this.setState('LIVE');
      }
    }
  }

  private addSampleWithoutDuplicates(sample: ScoredSample): void {
    if (sample.seq !== undefined && sample.seq !== null) {
      if (this.sampleSeqs.has(sample.seq)) return;
      this.sampleSeqs.add(sample.seq);
      if (sample.seq > this.lastSeq) {
        this.lastSeq = sample.seq;
      }
    }
    this.samples.push(sample);
  }

  private setState(newState: ConnectionState): void {
    if (this.state !== newState) {
      this.state = newState;
      for (const l of this.listeners) l.onStateChange?.(newState);
    }
  }

  private scheduleReconnect(): void {
    this.setState('RECONNECTING');
    this.clearTimers();

    this.reconnectTimer = setTimeout(async () => {
      if (!this.isExplicitlyClosed) {
        await this.connect();
        if (this.currentSessionId) {
          await this.resync(this.currentSessionId);
        }
      }
    }, this.backoffMs);

    const maxBackoff = this.config.maxBackoffMs ?? 16000;
    this.backoffMs = Math.min(this.backoffMs * 2, maxBackoff);
  }

  private resetStaleTimer(): void {
    this.clearStaleTimer();
    const timeout = this.config.staleTimeoutMs ?? 15000;
    this.staleTimer = setTimeout(() => {
      if (this.state === 'LIVE') {
        this.setState('STALE');
      }
    }, timeout);
  }

  private clearStaleTimer(): void {
    if (this.staleTimer) {
      clearTimeout(this.staleTimer);
      this.staleTimer = null;
    }
  }

  private clearTimers(): void {
    this.clearStaleTimer();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private emitError(err: Error): void {
    for (const l of this.listeners) l.onError?.(err);
  }
}
