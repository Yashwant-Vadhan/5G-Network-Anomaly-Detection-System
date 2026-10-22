/**
 * Unit tests for LiveClient connection state machine and resync (T17-001).
 *
 * Acceptance Criteria:
 * - Reconnect resyncs without duplicates
 * - Ticket never appears in a URL
 * - Unit tests with a fake socket
 */

import { describe, expect, it, vi } from 'vitest';
import { LiveClient, WebSocketLike, fetchViewerTicket } from './liveClient';
import { ScoredSample, SnapshotEvent } from '../types/contracts';

class FakeWebSocket implements WebSocketLike {
  public readyState: number = 0;
  public sentMessages: string[] = [];
  public closedCode?: number;
  public closedReason?: string;

  public onopen: ((event: unknown) => void) | null = null;
  public onclose: ((event: { code: number; reason: string }) => void) | null = null;
  public onmessage: ((event: { data: string }) => void) | null = null;
  public onerror: ((event: unknown) => void) | null = null;

  constructor(public url: string) {
    setTimeout(() => {
      this.readyState = 1;
      this.onopen?.({});
    }, 10);
  }

  public send(data: string): void {
    this.sentMessages.push(data);
  }

  public close(code: number = 1000, reason: string = ''): void {
    this.readyState = 3;
    this.closedCode = code;
    this.closedReason = reason;
    this.onclose?.({ code, reason });
  }

  public triggerMessage(data: unknown): void {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  public triggerError(err: unknown): void {
    this.onerror?.(err);
  }
}

describe('LiveClient Connection State Machine & Auth (T17-001)', () => {
  it('throws an error if ticket appears in the WebSocket URL (G20/G26)', () => {
    expect(() => {
      new LiveClient({
        wsUrl: 'ws://localhost:8000/api/v1/live?ticket=SECRET_123',
        httpBaseUrl: 'http://localhost:8000',
      });
    }).toThrow('Security Guardrail: Ticket must never appear in the WebSocket URL');
  });

  it('sends first-frame auth with ticket over fake socket upon connect', async () => {
    let createdSocket: FakeWebSocket | null = null;
    const client = new LiveClient({
      wsUrl: 'ws://localhost:8000/api/v1/live',
      httpBaseUrl: 'http://localhost:8000',
      ticket: 'valid-single-use-ticket-777',
      webSocketFactory: (url: string) => {
        createdSocket = new FakeWebSocket(url);
        return createdSocket;
      },
    });

    await client.connect();
    expect(client.getState()).toBe('WAITING');

    // Wait for fake socket open
    await new Promise((r) => setTimeout(r, 25));

    expect(createdSocket).not.toBeNull();
    expect(createdSocket!.sentMessages.length).toBe(1);
    const firstFrame = JSON.parse(createdSocket!.sentMessages[0]);
    expect(firstFrame).toEqual({
      type: 'auth',
      ticket: 'valid-single-use-ticket-777',
    });
  });

  it('transitions from WAITING -> LIVE upon snapshot and processes samples', async () => {
    let socket: FakeWebSocket | null = null;
    const stateTransitions: string[] = [];

    const client = new LiveClient({
      wsUrl: 'ws://localhost:8000/api/v1/live',
      httpBaseUrl: 'http://localhost:8000',
      webSocketFactory: (url) => {
        socket = new FakeWebSocket(url);
        return socket;
      },
    });

    client.subscribe({
      onStateChange: (state) => stateTransitions.push(state),
    });

    await client.connect();
    await new Promise((r) => setTimeout(r, 20));

    const snapshot: SnapshotEvent = {
      type: 'snapshot',
      schema_version: 2,
      server_time: '2026-10-17T15:30:00Z',
      session_id: 'sess-live-01',
      device: 'Pixel 7',
      state: 'LIVE',
      open_events: [],
      last_alerts: [],
      latest_sample: {
        timestamp: '2026-10-17T15:30:00Z',
        device: 'Pixel 7',
        session_id: 'sess-live-01',
        seq: 1,
        is_valid: true,
        model_eligible: true,
        csi_available: false,
        is_synthetic: false,
        dup_ts: false,
        baseline_flag: false,
        if_flag: false,
        anomaly_type: 'NORMAL',
        severity: 'NONE',
        is_anom: false,
        sample_idx: 1,
        received_at: '2026-10-17T15:30:00Z',
        scored_at: '2026-10-17T15:30:00Z',
        published_at: '2026-10-17T15:30:00Z',
      },
    };

    socket!.triggerMessage(snapshot);

    expect(client.getState()).toBe('LIVE');
    expect(client.getSessionId()).toBe('sess-live-01');
    expect(client.getSamples().length).toBe(1);
    expect(client.getSamples()[0].seq).toBe(1);
  });

  it('resyncs via REST without duplicate samples on reconnect or dropped', async () => {
    let socket: FakeWebSocket | null = null;

    const mockSamples: ScoredSample[] = [
      {
        timestamp: '2026-10-17T15:30:01Z',
        device: 'Pixel 7',
        session_id: 'sess-resync-01',
        seq: 1,
        sample_idx: 1,
        is_valid: true,
        model_eligible: true,
        csi_available: false,
        is_synthetic: false,
        dup_ts: false,
        baseline_flag: false,
        if_flag: false,
        anomaly_type: 'NORMAL',
        severity: 'NONE',
        is_anom: false,
        received_at: '2026-10-17T15:30:01Z',
        scored_at: '2026-10-17T15:30:01Z',
        published_at: '2026-10-17T15:30:01Z',
      },
      {
        timestamp: '2026-10-17T15:30:02Z',
        device: 'Pixel 7',
        session_id: 'sess-resync-01',
        seq: 2,
        sample_idx: 2,
        is_valid: true,
        model_eligible: true,
        csi_available: false,
        is_synthetic: false,
        dup_ts: false,
        baseline_flag: false,
        if_flag: false,
        anomaly_type: 'NORMAL',
        severity: 'NONE',
        is_anom: false,
        received_at: '2026-10-17T15:30:02Z',
        scored_at: '2026-10-17T15:30:02Z',
        published_at: '2026-10-17T15:30:02Z',
      },
      {
        timestamp: '2026-10-17T15:30:03Z',
        device: 'Pixel 7',
        session_id: 'sess-resync-01',
        seq: 3,
        sample_idx: 3,
        is_valid: true,
        model_eligible: true,
        csi_available: false,
        is_synthetic: false,
        dup_ts: false,
        baseline_flag: false,
        if_flag: false,
        anomaly_type: 'NORMAL',
        severity: 'NONE',
        is_anom: false,
        received_at: '2026-10-17T15:30:03Z',
        scored_at: '2026-10-17T15:30:03Z',
        published_at: '2026-10-17T15:30:03Z',
      },
    ];

    const mockFetch = vi.fn().mockImplementation(async () => {
      return {
        ok: true,
        json: async () => ({ samples: mockSamples }),
      };
    });

    const client = new LiveClient({
      wsUrl: 'ws://localhost:8000/api/v1/live',
      httpBaseUrl: 'http://localhost:8000',
      fetchFn: mockFetch as unknown as typeof fetch,
      webSocketFactory: (url) => {
        socket = new FakeWebSocket(url);
        return socket;
      },
    });

    await client.connect();
    await new Promise((r) => setTimeout(r, 20));

    // Deliver sample seq=1 over WebSocket
    socket!.triggerMessage({
      type: 'sample',
      schema_version: 2,
      server_time: '2026-10-17T15:30:01Z',
      session_id: 'sess-resync-01',
      sample: mockSamples[0],
    });

    expect(client.getSamples().length).toBe(1);

    // Dropped event triggers resync
    socket!.triggerMessage({
      type: 'dropped',
      schema_version: 2,
      server_time: '2026-10-17T15:30:03Z',
      count: 2,
    });

    // Wait for async resync
    await new Promise((r) => setTimeout(r, 50));

    expect(mockFetch).toHaveBeenCalled();
    // Total samples should be exactly 3 without duplicate for seq=1!
    const samples = client.getSamples();
    expect(samples.length).toBe(3);
    const seqs = samples.map((s) => s.seq);
    expect(seqs).toEqual([1, 2, 3]);
  });

  it('enters STALE state when timeout expires without samples', async () => {
    vi.useFakeTimers();
    let socket: FakeWebSocket | null = null;

    const client = new LiveClient({
      wsUrl: 'ws://localhost:8000/api/v1/live',
      httpBaseUrl: 'http://localhost:8000',
      staleTimeoutMs: 5000,
      webSocketFactory: (url) => {
        socket = new FakeWebSocket(url);
        return socket;
      },
    });

    await client.connect();
    await vi.advanceTimersByTimeAsync(20);

    socket!.triggerMessage({
      type: 'sample',
      schema_version: 2,
      server_time: '2026-10-17T15:30:00Z',
      session_id: 'sess-stale-01',
      sample: {
        timestamp: '2026-10-17T15:30:00Z',
        device: 'Pixel 7',
        session_id: 'sess-stale-01',
        seq: 1,
        is_valid: true,
        model_eligible: true,
        csi_available: false,
        is_synthetic: false,
        dup_ts: false,
        baseline_flag: false,
        if_flag: false,
        anomaly_type: 'NORMAL',
        severity: 'NONE',
        is_anom: false,
        sample_idx: 1,
        received_at: '2026-10-17T15:30:00Z',
        scored_at: '2026-10-17T15:30:00Z',
        published_at: '2026-10-17T15:30:00Z',
      },
    });

    expect(client.getState()).toBe('LIVE');

    // Advance beyond staleTimeoutMs
    await vi.advanceTimersByTimeAsync(6000);
    expect(client.getState()).toBe('STALE');

    // Heartbeat restores to LIVE
    socket!.triggerMessage({
      type: 'heartbeat',
      schema_version: 2,
      server_time: '2026-10-17T15:30:06Z',
    });
    expect(client.getState()).toBe('LIVE');

    vi.useRealTimers();
  });

  describe('Viewer Ticket Fetching & Reconnection Freshness (C10 / T18-003)', () => {
    it('fetches single-use ticket with credentials include and cleans URL', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ticket: 'valid-test-ticket-xyz',
          expires_at: '2026-10-21T18:00:30Z',
        }),
      });

      const ticket = await fetchViewerTicket(
        'http://localhost:8000/',
        'live-session-1234',
        mockFetch as unknown as typeof fetch
      );

      expect(ticket).toBe('valid-test-ticket-xyz');
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/live-sessions/live-session-1234/ticket',
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            Accept: 'application/json',
          },
        }
      );
    });

    it('rejects with error when session ID is missing or empty without calling fetch', async () => {
      const mockFetch = vi.fn();

      await expect(
        fetchViewerTicket('http://localhost:8000', '', mockFetch as unknown as typeof fetch)
      ).rejects.toThrow('Session ID is required to fetch a viewer ticket');

      await expect(
        fetchViewerTicket('http://localhost:8000', '   ', mockFetch as unknown as typeof fetch)
      ).rejects.toThrow('Session ID is required to fetch a viewer ticket');

      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('handles HTTP error status on ticket request failure', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized viewer',
      });

      await expect(
        fetchViewerTicket(
          'http://localhost:8000',
          'live-session-unauth',
          mockFetch as unknown as typeof fetch
        )
      ).rejects.toThrow('Failed to obtain viewer ticket: HTTP 401 Unauthorized viewer');
    });

    it('handles malformed ticket JSON response', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      });

      await expect(
        fetchViewerTicket(
          'http://localhost:8000',
          'live-session-malformed',
          mockFetch as unknown as typeof fetch
        )
      ).rejects.toThrow('Malformed viewer ticket response');
    });

    it('obtains a fresh single-use ticket on reconnection without caching or URL leaks', async () => {
      const createdSockets: FakeWebSocket[] = [];
      const issuedTickets = ['ticket-one-111', 'ticket-two-222'];
      let ticketCallCount = 0;

      const mockGetTicket = vi.fn().mockImplementation(async () => {
        const ticket = issuedTickets[ticketCallCount++] || 'ticket-fallback';
        return ticket;
      });

      const client = new LiveClient({
        wsUrl: 'ws://localhost:8000/api/v1/live',
        httpBaseUrl: 'http://localhost:8000',
        initialBackoffMs: 20,
        maxBackoffMs: 50,
        getTicket: mockGetTicket,
        webSocketFactory: (url: string) => {
          const s = new FakeWebSocket(url);
          createdSockets.push(s);
          return s;
        },
      });

      await client.connect();
      expect(client.getState()).toBe('WAITING');
      await new Promise((r) => setTimeout(r, 25));

      expect(createdSockets.length).toBe(1);
      expect(mockGetTicket).toHaveBeenCalledTimes(1);
      const firstSocket = createdSockets[0];
      expect(firstSocket.sentMessages.length).toBe(1);
      expect(JSON.parse(firstSocket.sentMessages[0])).toEqual({
        type: 'auth',
        ticket: 'ticket-one-111',
      });
      expect(firstSocket.url).toBe('ws://localhost:8000/api/v1/live');
      expect(firstSocket.url).not.toContain('ticket');

      // Simulate network disconnection (triggers scheduleReconnect with backoff)
      firstSocket.close(1006, 'Abnormal closure');

      // Wait for backoff reconnect and fake socket readyState open
      await new Promise((r) => setTimeout(r, 80));

      expect(createdSockets.length).toBe(2);
      expect(mockGetTicket).toHaveBeenCalledTimes(2);
      const secondSocket = createdSockets[1];
      expect(secondSocket.sentMessages.length).toBe(1);
      expect(JSON.parse(secondSocket.sentMessages[0])).toEqual({
        type: 'auth',
        ticket: 'ticket-two-222',
      });
      expect(secondSocket.url).toBe('ws://localhost:8000/api/v1/live');
      expect(secondSocket.url).not.toContain('ticket');

      // Ensure ticket 1 and ticket 2 are completely distinct
      expect(JSON.parse(firstSocket.sentMessages[0]).ticket).not.toBe(
        JSON.parse(secondSocket.sentMessages[0]).ticket
      );
    });
  });
});

