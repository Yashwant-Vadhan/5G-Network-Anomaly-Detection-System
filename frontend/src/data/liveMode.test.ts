/**
 * Live Mode Tests with a Mock WebSocket Server (T17-009).
 *
 * Verifies:
 * - Every connection state (WAITING, LIVE, STALE, RECONNECTING, DISCONNECTED, REPLAY-SOURCE)
 * - Provisional -> Final event transitions (event_open -> event_update -> event_closed)
 * - Alert reception and ACK API dispatch
 * - Dropped frame handling triggering REST resync without duplicate samples
 * - Auth failure handling (code 4401) with clear user-facing error message
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { LiveClient, WebSocketLike } from './liveClient';
import {
  EventRecord,
  ScoredSample,
  SnapshotEvent,
  LiveEventOpen,
  LiveEventUpdate,
  LiveEventClosed,
} from '../types/contracts';

/**
 * In-memory Mock WebSocket implementation for deterministic integration tests.
 */
class MockClientSocket implements WebSocketLike {
  public readyState: number = 0; // 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
  public sentMessages: string[] = [];
  public closedCode?: number;
  public closedReason?: string;

  public onopen: ((event: unknown) => void) | null = null;
  public onclose: ((event: { code: number; reason: string }) => void) | null = null;
  public onmessage: ((event: { data: string }) => void) | null = null;
  public onerror: ((event: unknown) => void) | null = null;

  constructor(public url: string, private server: MockWebSocketServer) {
    this.server.registerClient(this);
  }

  public send(data: string): void {
    this.sentMessages.push(data);
    this.server.handleClientMessage(this, data);
  }

  public close(code: number = 1000, reason: string = ''): void {
    this.readyState = 3;
    this.closedCode = code;
    this.closedReason = reason;
    this.server.removeClient(this);
    this.onclose?.({ code, reason });
  }

  // Server-to-client simulation helpers
  public simulateOpen(): void {
    this.readyState = 1;
    this.onopen?.({});
  }

  public simulateMessage(data: unknown): void {
    const raw = typeof data === 'string' ? data : JSON.stringify(data);
    this.onmessage?.({ data: raw });
  }

  public simulateClose(code: number = 1000, reason: string = ''): void {
    this.readyState = 3;
    this.closedCode = code;
    this.closedReason = reason;
    this.server.removeClient(this);
    this.onclose?.({ code, reason });
  }

  public simulateError(err: unknown): void {
    this.onerror?.(err);
  }
}

/**
 * Mock WebSocket Server controlling connected client sockets.
 */
class MockWebSocketServer {
  public clients: Set<MockClientSocket> = new Set();
  public onMessageHook?: (client: MockClientSocket, msg: Record<string, unknown>) => void;

  public registerClient(client: MockClientSocket): void {
    this.clients.add(client);
  }

  public removeClient(client: MockClientSocket): void {
    this.clients.delete(client);
  }

  public handleClientMessage(client: MockClientSocket, raw: string): void {
    try {
      const parsed = JSON.parse(raw);
      this.onMessageHook?.(client, parsed);
    } catch {
      // Ignore unparseable frames
    }
  }

  public broadcast(payload: unknown): void {
    for (const client of this.clients) {
      if (client.readyState === 1) {
        client.simulateMessage(payload);
      }
    }
  }

  public closeAll(code: number = 1000, reason: string = ''): void {
    for (const client of Array.from(this.clients)) {
      client.simulateClose(code, reason);
    }
  }
}

describe('Live Mode Tests with Mock Server (T17-009)', () => {
  let server: MockWebSocketServer;
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    server = new MockWebSocketServer();
    mockFetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function createClient(options?: {
    ticket?: string;
    staleTimeoutMs?: number;
    initialBackoffMs?: number;
  }): { client: LiveClient; getLatestSocket: () => MockClientSocket } {
    let latestSocket: MockClientSocket;
    const client = new LiveClient({
      wsUrl: 'ws://localhost:8000/api/v1/live',
      httpBaseUrl: 'http://localhost:8000',
      ticket: options?.ticket ?? 'valid-ticket-001',
      staleTimeoutMs: options?.staleTimeoutMs ?? 5000,
      initialBackoffMs: options?.initialBackoffMs ?? 1000,
      fetchFn: mockFetch as unknown as typeof fetch,
      webSocketFactory: (url: string) => {
        latestSocket = new MockClientSocket(url, server);
        return latestSocket;
      },
    });

    return { client, getLatestSocket: () => latestSocket };
  }

  describe('Acceptance Criteria 1: Every Connection State has a Test', () => {
    it('verifies DISCONNECTED state initially and upon explicit disconnect', async () => {
      const { client, getLatestSocket } = createClient();
      expect(client.getState()).toBe('DISCONNECTED');

      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();
      socket.simulateMessage({
        type: 'sample',
        session_id: 'sess-1',
        sample: { seq: 1, timestamp: '2026-10-18T10:00:00Z', device: 'Pixel 8' },
      });
      expect(client.getState()).toBe('LIVE');

      client.disconnect();
      expect(client.getState()).toBe('DISCONNECTED');
      expect(socket.closedCode).toBe(1000);
      expect(socket.closedReason).toBe('User disconnect');
    });

    it('verifies WAITING state when connect() is initiated before data arrives', async () => {
      const { client, getLatestSocket } = createClient();
      const stateChanges: string[] = [];
      client.subscribe({ onStateChange: s => stateChanges.push(s) });

      const connectPromise = client.connect();
      expect(client.getState()).toBe('WAITING');
      expect(stateChanges).toContain('WAITING');

      const socket = getLatestSocket();
      socket.simulateOpen();
      expect(client.getState()).toBe('WAITING');

      // First-frame auth ticket was sent by client
      expect(socket.sentMessages.length).toBe(1);
      expect(JSON.parse(socket.sentMessages[0])).toEqual({
        type: 'auth',
        ticket: 'valid-ticket-001',
      });

      await connectPromise;
    });

    it('verifies LIVE state transition on receiving sample and snapshot events', async () => {
      const { client, getLatestSocket } = createClient();
      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      const snapshot: SnapshotEvent = {
        type: 'snapshot',
        schema_version: 1,
        server_time: '2026-10-18T10:00:00Z',
        session_id: 'live-sess-100',
        device: 'Redmi 13 5G',
        state: 'LIVE',
        latest_sample: {
          seq: 10,
          timestamp: '2026-10-18T10:00:00Z',
          device: 'Redmi 13 5G',
          session_id: 'live-sess-100',
        } as unknown as ScoredSample,
        open_events: [],
        last_alerts: [],
      };

      socket.simulateMessage(snapshot);
      expect(client.getState()).toBe('LIVE');
      expect(client.getSessionId()).toBe('live-sess-100');
      expect(client.getSamples().length).toBe(1);
    });

    it('verifies STALE state after timeout and recovery to LIVE on heartbeat', async () => {
      const { client, getLatestSocket } = createClient({ staleTimeoutMs: 3000 });
      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      socket.simulateMessage({
        type: 'sample',
        session_id: 'live-sess-1',
        sample: { seq: 1, timestamp: '2026-10-18T10:00:00Z', device: 'Pixel 8' },
      });
      expect(client.getState()).toBe('LIVE');

      // Advance time by 3 seconds without frames -> transitions to STALE
      vi.advanceTimersByTime(3000);
      expect(client.getState()).toBe('STALE');

      // Heartbeat arrives from server -> recovers to LIVE
      socket.simulateMessage({ type: 'heartbeat', timestamp: '2026-10-18T10:00:03Z' });
      expect(client.getState()).toBe('LIVE');
    });

    it('verifies RECONNECTING state on unexpected socket closure with backoff', async () => {
      const { client, getLatestSocket } = createClient({ initialBackoffMs: 1000 });
      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      socket.simulateMessage({
        type: 'sample',
        session_id: 'live-sess-1',
        sample: { seq: 1, timestamp: '2026-10-18T10:00:00Z', device: 'Pixel 8' },
      });
      expect(client.getState()).toBe('LIVE');

      // Server drops connection abruptly
      socket.simulateClose(1006, 'Abnormal closure');
      expect(client.getState()).toBe('RECONNECTING');

      // Advance timers by backoff (1000ms) -> client attempts reconnect
      vi.advanceTimersByTime(1000);
      const newSocket = getLatestSocket();
      expect(newSocket).not.toBe(socket);
      newSocket.simulateOpen();
      newSocket.simulateMessage({
        type: 'sample',
        session_id: 'live-sess-1',
        sample: { seq: 2, timestamp: '2026-10-18T10:00:01Z', device: 'Pixel 8' },
      });
      expect(client.getState()).toBe('LIVE');
    });

    it('verifies REPLAY-SOURCE state transition via setReplayMode()', async () => {
      const { client, getLatestSocket } = createClient();
      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      client.setReplayMode();
      expect(client.getState()).toBe('REPLAY-SOURCE');
      expect(socket.closedCode).toBe(1000);
    });
  });

  describe('Acceptance Criteria 2: Auth Failure Shows a Clear Message', () => {
    it('handles 4401 code, halts reconnect loop, and sets clear error message', async () => {
      const { client, getLatestSocket } = createClient();
      const receivedErrors: Error[] = [];
      client.subscribe({ onError: err => receivedErrors.push(err) });

      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      // Server rejects first-frame ticket with 4401
      socket.simulateClose(4401, 'Unauthorized: Invalid or reused ticket');

      expect(client.getState()).toBe('DISCONNECTED');
      expect(receivedErrors.length).toBe(1);
      expect(receivedErrors[0].message).toBe('Unauthorized: Invalid or reused ticket');
      expect(client.getLastErrorMessage()).toBe('Unauthorized: Invalid or reused ticket');

      // Verify no reconnect timer is scheduled (does not loop on bad ticket)
      vi.advanceTimersByTime(10000);
      expect(client.getState()).toBe('DISCONNECTED');
    });

    it('handles expired ticket code 4401 with descriptive reason', async () => {
      const { client, getLatestSocket } = createClient();
      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      socket.simulateClose(4401, 'Unauthorized: Expired ticket');
      expect(client.getState()).toBe('DISCONNECTED');
      expect(client.getLastErrorMessage()).toBe('Unauthorized: Expired ticket');
    });
  });

  describe('Provisional -> Final Event Lifecycle Transitions', () => {
    it('processes event_open, event_update, and event_closed in sequence', async () => {
      const { client, getLatestSocket } = createClient();
      const eventTransitions: Array<{ event: EventRecord; action: string }> = [];
      client.subscribe({
        onEvent: (event, action) => eventTransitions.push({ event, action }),
      });

      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      // 1. event_open (PROVISIONAL)
      const openEvent: LiveEventOpen = {
        type: 'event_open',
        schema_version: 1,
        server_time: '2026-10-18T10:00:00Z',
        session_id: 'sess-evt-1',
        event: {
          event_id: 'evt-2001',
          session_id: 'sess-evt-1',
          anomaly_type: 'SIGNAL_DEGRADATION',
          max_severity: 'MEDIUM',
          start: '2026-10-18T10:00:00Z',
          end: '2026-10-18T10:00:00Z',
          sample_count: 1,
          ml: { max_baseline_z: 3.2 },
          signal: {},
          cell: {},
          network: {},
          diagnosis: {},
          recommendation: {},
          status: 'PROVISIONAL',
        },
      };
      socket.simulateMessage(openEvent);

      expect(eventTransitions.length).toBe(1);
      expect(eventTransitions[0].action).toBe('OPEN');
      expect(eventTransitions[0].event.status).toBe('PROVISIONAL');
      expect(client.getEvents().length).toBe(1);

      // 2. event_update (Higher z-score, still PROVISIONAL)
      const updateEvent: LiveEventUpdate = {
        type: 'event_update',
        schema_version: 1,
        server_time: '2026-10-18T10:00:03Z',
        session_id: 'sess-evt-1',
        event: {
          ...openEvent.event,
          end: '2026-10-18T10:00:03Z',
          sample_count: 2,
          max_severity: 'HIGH',
          ml: { max_baseline_z: 4.8 },
        },
      };
      socket.simulateMessage(updateEvent);

      expect(eventTransitions.length).toBe(2);
      expect(eventTransitions[1].action).toBe('UPDATE');
      expect(eventTransitions[1].event.max_severity).toBe('HIGH');
      expect(
        (client.getEvents()[0].ml as Record<string, unknown>).max_baseline_z
      ).toBe(4.8);

      // 3. event_closed (FINAL with diagnosis)
      const closedEvent: LiveEventClosed = {
        type: 'event_closed',
        schema_version: 1,
        server_time: '2026-10-18T10:00:06Z',
        session_id: 'sess-evt-1',
        event: {
          ...updateEvent.event,
          status: 'FINAL',
          diagnosis: {
            summary: 'Sudden RSRP drop below -115 dBm',
            primary_cause: 'Radio signal fading',
            recommendation: 'Check coverage',
          },
        },
      };
      socket.simulateMessage(closedEvent);

      expect(eventTransitions.length).toBe(3);
      expect(eventTransitions[2].action).toBe('CLOSED');
      expect(eventTransitions[2].event.status).toBe('FINAL');
      expect(client.getEvents()[0].status).toBe('FINAL');
    });
  });

  describe('Alert Reception and ACK API', () => {
    it('receives alert frame and dispatches HTTP ACK via ackAlert()', async () => {
      const { client, getLatestSocket } = createClient();
      const alerts: Array<Record<string, unknown>> = [];
      client.subscribe({ onAlert: a => alerts.push(a) });

      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      // Server pushes alert frame
      const alertPayload = {
        alert_id: 'alt-live-999',
        kind: 'NEW',
        severity: 'HIGH',
        anomaly_type: 'SIGNAL_DEGRADATION',
        event_status: 'PROVISIONAL',
        title: 'Severe RSRP degradation',
      };
      socket.simulateMessage({ type: 'alert', alert: alertPayload });

      expect(alerts.length).toBe(1);
      expect(alerts[0].alert_id).toBe('alt-live-999');

      // Acknowledge alert via client API
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...alertPayload, acknowledged_at: '2026-10-18T10:00:05Z' }),
      });

      const ackResult = await client.ackAlert('alt-live-999');
      expect(ackResult).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/alerts/alt-live-999/ack',
        { method: 'POST' }
      );
    });
  });

  describe('Dropped Frame Handling & REST Resync', () => {
    it('triggers resync upon dropped message and appends missing samples', async () => {
      const { client, getLatestSocket } = createClient();
      await client.connect();
      const socket = getLatestSocket();
      socket.simulateOpen();

      // Sample 1 received via WebSocket
      const sample1 = {
        seq: 1,
        timestamp: '2026-10-18T10:00:00Z',
        device: 'Pixel 8',
        session_id: 'sess-sync-1',
      } as unknown as ScoredSample;
      socket.simulateMessage({ type: 'sample', session_id: 'sess-sync-1', sample: sample1 });
      expect(client.getSamples().length).toBe(1);

      // Server sends dropped frame (backpressure buffer drop)
      const missingSamples: ScoredSample[] = [
        {
          seq: 1,
          timestamp: '2026-10-18T10:00:00Z',
          device: 'Pixel 8',
          session_id: 'sess-sync-1',
        } as unknown as ScoredSample,
        {
          seq: 2,
          timestamp: '2026-10-18T10:00:03Z',
          device: 'Pixel 8',
          session_id: 'sess-sync-1',
        } as unknown as ScoredSample,
        {
          seq: 3,
          timestamp: '2026-10-18T10:00:06Z',
          device: 'Pixel 8',
          session_id: 'sess-sync-1',
        } as unknown as ScoredSample,
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ samples: missingSamples }),
      });

      socket.simulateMessage({ type: 'dropped', reason: 'buffer_overflow' });

      // Allow promise microtasks to resolve
      await Promise.resolve();
      await Promise.resolve();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/sessions/sess-sync-1/samples?since_seq=1&limit=1000'
      );

      // Seq 1 was deduplicated, seq 2 & 3 added -> total 3 samples
      expect(client.getSamples().length).toBe(3);
      expect(client.getSamples().map(s => s.seq)).toEqual([1, 2, 3]);
    });
  });
});
