/**
 * Unit tests for LiveClient connection state machine and resync (T17-001).
 *
 * Acceptance Criteria:
 * - Reconnect resyncs without duplicates
 * - Ticket never appears in a URL
 * - Unit tests with a fake socket
 */

import { describe, expect, it, vi } from 'vitest';
import { LiveClient, WebSocketLike } from './liveClient';
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

    const mockFetch = vi.fn().mockImplementation(async (_url: string) => {
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
});
