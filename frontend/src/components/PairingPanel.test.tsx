import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import {
  PairingPanel,
  buildC1Csv,
  C1_COLUMNS,
} from './PairingPanel';
import { ScoredSample, CreateLiveSessionResponse } from '../types/contracts';

describe('PairingPanel Component (T17-008)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  const mockSession: CreateLiveSessionResponse = {
    session_id: 'live-test-sess-1234',
    pairing_code: 'ABCD9876',
    expires_at: new Date(Date.now() + 180 * 1000).toISOString(),
    ws_endpoint: '/ws/v1/telemetry/live-test-sess-1234',
  };

  const sampleTelemetries: ScoredSample[] = [
    {
      timestamp: '2026-10-18T10:00:00Z',
      device: 'Redmi 13 5G',
      manufacturer: 'Xiaomi',
      android: 14,
      operator: 'Jio',
      network_type: 'NR',
      deployment_mode: 'SA',
      display_override: '5G',
      registered: true,
      ss_rsrp: -85.2,
      ss_rsrq: -11.0,
      ss_sinr: 15.4,
      csi_rsrp: -86.1,
      csi_rsrq: -12.1,
      csi_sinr: 14.8,
      pci: 421,
      nci: 12345678,
      nrarfcn: 632000,
      anomaly_score: 0.12,
      is_anomaly: false,
    },
    {
      timestamp: '2026-10-18T10:00:01Z',
      device: 'Redmi 13 5G',
      manufacturer: 'Xiaomi',
      android: 14,
      operator: 'Jio',
      network_type: 'NR',
      deployment_mode: 'SA',
      display_override: '5G',
      registered: true,
      ss_rsrp: -115.0,
      ss_rsrq: -18.5,
      ss_sinr: -2.3,
      csi_rsrp: -116.2,
      csi_rsrq: -19.1,
      csi_sinr: -3.0,
      pci: 421,
      nci: 12345678,
      nrarfcn: 632000,
      anomaly_score: 0.88,
      is_anomaly: true,
    },
  ];

  it('renders initial state with Start Live Session button and privacy notice', () => {
    render(<PairingPanel />);

    expect(screen.getByTestId('start-session-btn')).toBeInTheDocument();
    expect(screen.getByText(/Privacy & Consent Notice \(G28\/G29\):/i)).toBeInTheDocument();
    expect(screen.queryByTestId('pairing-code-display')).not.toBeInTheDocument();
  });

  it('starts session, renders pairing code, QR graphic, and countdown', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockSession,
    });

    render(<PairingPanel fetchFn={mockFetch as unknown as typeof fetch} />);

    const startBtn = screen.getByTestId('start-session-btn');
    await act(async () => {
      fireEvent.click(startBtn);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/v1/live-sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    // Pairing code display
    const codeDisplay = screen.getByTestId('pairing-code-display');
    expect(codeDisplay).toBeInTheDocument();
    expect(codeDisplay).toHaveTextContent('ABCD9876');

    // QR code image element
    const qrSvg = screen.getByRole('img', { name: /Pairing QR code for ABCD9876/i });
    expect(qrSvg).toBeInTheDocument();

    // Timer is active
    expect(screen.getByRole('timer')).toHaveTextContent(/Code expires in: (2:59|3:00)/i);
  });

  it('Acceptance Criteria 1: shows expired state and retry instruction/action when code expires', async () => {
    const now = Date.now();
    const shortExpirySession: CreateLiveSessionResponse = {
      session_id: 'sess-expiring',
      pairing_code: 'EXPIRE01',
      expires_at: new Date(now + 10 * 1000).toISOString(), // 10s
      ws_endpoint: '/ws/v1/telemetry/sess-expiring',
    };

    let fetchCallCount = 0;
    const mockFetch = vi.fn().mockImplementation(() => {
      fetchCallCount++;
      return Promise.resolve({
        ok: true,
        json: async () =>
          fetchCallCount === 1
            ? shortExpirySession
            : {
                ...shortExpirySession,
                pairing_code: 'NEWCODE2',
                expires_at: new Date(Date.now() + 180 * 1000).toISOString(),
              },
      });
    });

    render(<PairingPanel fetchFn={mockFetch as unknown as typeof fetch} />);

    // Start session
    await act(async () => {
      fireEvent.click(screen.getByTestId('start-session-btn'));
    });

    expect(screen.getByTestId('pairing-code-display')).toHaveTextContent('EXPIRE01');

    // Advance timers by 11 seconds to trigger expiry
    act(() => {
      vi.advanceTimersByTime(11000);
    });

    // Verify expired notice is visible with instructions to retry
    const expiredNotice = screen.getByTestId('expired-notice');
    expect(expiredNotice).toBeInTheDocument();
    expect(expiredNotice).toHaveTextContent(/Pairing code has expired/i);
    expect(expiredNotice).toHaveTextContent(/Click here to retry and generate a new code/i);

    // Clicking retry regenerates code
    const retryBtn = screen.getByText(/Click here to retry and generate a new code/i);
    await act(async () => {
      fireEvent.click(retryBtn);
    });

    expect(fetchCallCount).toBe(2);
    expect(screen.getByTestId('pairing-code-display')).toHaveTextContent('NEWCODE2');
    expect(screen.queryByTestId('expired-notice')).not.toBeInTheDocument();
  });

  it('displays connection badge reflecting phone connection state', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockSession,
    });

    const { rerender } = render(
      <PairingPanel
        connectionState="DISCONNECTED"
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId('start-session-btn'));
    });

    // Initially waiting for phone
    const badge = screen.getByTestId('pairing-status-badge');
    expect(badge).toHaveTextContent(/Waiting for phone/i);

    // Phone connects (state becomes LIVE)
    rerender(
      <PairingPanel
        connectionState="LIVE"
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    expect(screen.getByTestId('pairing-status-badge')).toHaveTextContent(/Phone Connected/i);
  });

  it('ends session and calls DELETE /api/v1/live-sessions/{id}', async () => {
    const mockFetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (opts?.method === 'DELETE') {
        return Promise.resolve({ ok: true });
      }
      return Promise.resolve({
        ok: true,
        json: async () => mockSession,
      });
    });

    const onSessionEnded = vi.fn();

    render(
      <PairingPanel
        fetchFn={mockFetch as unknown as typeof fetch}
        onSessionEnded={onSessionEnded}
      />
    );

    // Start session
    await act(async () => {
      fireEvent.click(screen.getByTestId('start-session-btn'));
    });

    // End session
    const endBtn = screen.getByTestId('end-session-btn');
    await act(async () => {
      fireEvent.click(endBtn);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/live-sessions/live-test-sess-1234',
      { method: 'DELETE' }
    );
    expect(onSessionEnded).toHaveBeenCalledTimes(1);

    // UI resets to unstarted
    expect(screen.getByTestId('start-session-btn')).toBeInTheDocument();
    expect(screen.queryByTestId('pairing-code-display')).not.toBeInTheDocument();
  });

  describe('Acceptance Criteria 2: CSV equals samples received (header + row count)', () => {
    it('buildC1Csv generates exact 18 Contract C1 columns in header', () => {
      const csv = buildC1Csv([]);
      const lines = csv.trim().split('\n');

      expect(lines.length).toBe(1);
      const headers = lines[0].split(',');
      expect(headers).toEqual([...C1_COLUMNS]);
      expect(headers).toEqual([
        'timestamp',
        'device',
        'manufacturer',
        'android',
        'operator',
        'network_type',
        'deployment_mode',
        'display_override',
        'registered',
        'ss_rsrp',
        'ss_rsrq',
        'ss_sinr',
        'csi_rsrp',
        'csi_rsrq',
        'csi_sinr',
        'pci',
        'nci',
        'nrarfcn',
      ]);
    });

    it('buildC1Csv row count strictly equals sample count received', () => {
      const csv = buildC1Csv(sampleTelemetries);
      const lines = csv.trim().split('\n');

      // 1 header + 2 sample rows = 3 lines total
      expect(lines.length).toBe(1 + sampleTelemetries.length);

      // Verify row values
      const row1Cols = lines[1].split(',');
      expect(row1Cols[0]).toBe('2026-10-18T10:00:00Z');
      expect(row1Cols[1]).toBe('Redmi 13 5G');
      expect(row1Cols[9]).toBe('-85.2'); // ss_rsrp
      expect(row1Cols[15]).toBe('421'); // pci
      expect(row1Cols[16]).toBe('12345678'); // nci

      const row2Cols = lines[2].split(',');
      expect(row2Cols[0]).toBe('2026-10-18T10:00:01Z');
      expect(row2Cols[9]).toBe('-115'); // ss_rsrp
    });

    it('buildC1Csv replaces null/undefined values with NA and escapes commas', () => {
      const partialSample: ScoredSample = {
        timestamp: '2026-10-18T10:00:02Z',
        device: 'Test, Device with comma',
        manufacturer: undefined,
        android: null,
        operator: 'Airtel',
      };

      const csv = buildC1Csv([partialSample]);
      const lines = csv.trim().split('\n');
      expect(lines.length).toBe(2);

      const rowCols = lines[1].split(',');
      expect(rowCols[0]).toBe('2026-10-18T10:00:02Z');
      // Escaped with quotes due to comma
      expect(rowCols[1]).toBe('"Test');
      expect(rowCols[2]).toBe(' Device with comma"');
      // Null and undefined columns mapped to NA
      expect(rowCols[3]).toBe('NA'); // manufacturer
      expect(rowCols[4]).toBe('NA'); // android
    });
  });
});
