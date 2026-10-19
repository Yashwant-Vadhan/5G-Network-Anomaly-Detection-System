import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  CreateLiveSessionResponse,
  ScoredSample,
  ConnectionState,
} from '../types/contracts';

export interface PairingPanelProps {
  apiBaseUrl?: string;
  connectionState?: ConnectionState;
  samples?: ScoredSample[];
  onSessionStarted?: (session: CreateLiveSessionResponse) => void;
  onSessionEnded?: () => void;
  fetchFn?: typeof fetch;
}

export const C1_COLUMNS = [
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
] as const;

export function buildC1Csv(samples: ScoredSample[]): string {
  const header = C1_COLUMNS.join(',');
  const rows = samples.map(s => {
    return C1_COLUMNS.map(col => {
      const val = (s as unknown as Record<string, unknown>)[col];
      if (val === null || val === undefined || val === '') {
        return 'NA';
      }
      if (
        typeof val === 'string' &&
        (val.includes(',') || val.includes('"') || val.includes('\n'))
      ) {
        return `"${val.replace(/"/g, '""')}"`;
      }
      return String(val);
    }).join(',');
  });

  return [header, ...rows].join('\n');
}

export function downloadCsvFile(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// Deterministic pseudo-QR generator SVG for pairing codes
function SimpleQrCode({ text }: { text: string }) {
  const size = 15;
  const cells: boolean[][] = useMemo(() => {
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = (hash << 5) - hash + text.charCodeAt(i);
      hash |= 0;
    }
    const grid: boolean[][] = [];
    for (let r = 0; r < size; r++) {
      const row: boolean[] = [];
      for (let c = 0; c < size; c++) {
        // Corners: standard QR finder patterns
        const isTopLeft = r < 5 && c < 5;
        const isTopRight = r < 5 && c >= size - 5;
        const isBottomLeft = r >= size - 5 && c < 5;
        if (isTopLeft || isTopRight || isBottomLeft) {
          const cornerR = isBottomLeft ? r - (size - 5) : r;
          const cornerC = isTopRight ? c - (size - 5) : c;
          const isBorder = cornerR === 0 || cornerR === 4 || cornerC === 0 || cornerC === 4;
          const isCenter = cornerR >= 1 && cornerR <= 3 && cornerC >= 1 && cornerC <= 3;
          row.push(isBorder || isCenter);
        } else {
          const bit = Math.abs((hash * (r + 1) * (c + 1) + (r ^ c)) % 100);
          row.push(bit > 45);
        }
      }
      grid.push(row);
    }
    return grid;
  }, [text]);

  const cellSize = 10;
  const svgDimension = size * cellSize;

  return (
    <svg
      role="img"
      aria-label={`Pairing QR code for ${text}`}
      viewBox={`0 0 ${svgDimension} ${svgDimension}`}
      style={{
        width: '140px',
        height: '140px',
        background: '#ffffff',
        padding: '8px',
        borderRadius: '6px',
        border: '1px solid var(--color-border)',
      }}
    >
      <desc>{`Pairing QR code for code ${text}`}</desc>
      {cells.map((row, r) =>
        row.map((active, c) =>
          active ? (
            <rect
              key={`${r}-${c}`}
              x={c * cellSize}
              y={r * cellSize}
              width={cellSize}
              height={cellSize}
              fill="#0F172A"
            />
          ) : null
        )
      )}
    </svg>
  );
}

export const PairingPanel: React.FC<PairingPanelProps> = ({
  apiBaseUrl = '',
  connectionState = 'DISCONNECTED',
  samples = [],
  onSessionStarted,
  onSessionEnded,
  fetchFn = typeof fetch !== 'undefined' ? fetch : undefined,
}) => {
  const [session, setSession] = useState<CreateLiveSessionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [isExpired, setIsExpired] = useState(false);

  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Countdown timer for pairing code expiration
  useEffect(() => {
    if (!session?.expires_at) return;

    const expiryMs = new Date(session.expires_at).getTime();

    const updateTimer = () => {
      const now = Date.now();
      const diffSec = Math.max(0, Math.floor((expiryMs - now) / 1000));
      setSecondsRemaining(diffSec);

      if (diffSec <= 0) {
        setIsExpired(true);
        if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
      }
    };

    updateTimer();
    countdownTimerRef.current = setInterval(updateTimer, 1000);

    return () => {
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    };
  }, [session?.expires_at]);

  const handleStartSession = async () => {
    if (!fetchFn) {
      setError('Network client unavailable');
      return;
    }

    setLoading(true);
    setError(null);
    setIsExpired(false);

    try {
      const res = await fetchFn(`${apiBaseUrl}/api/v1/live-sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        throw new Error(`Failed to create session (${res.status} ${res.statusText})`);
      }

      const data: CreateLiveSessionResponse = await res.json();
      setSession(data);
      onSessionStarted?.(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleEndSession = async () => {
    if (!session || !fetchFn) return;

    setLoading(true);
    try {
      await fetchFn(`${apiBaseUrl}/api/v1/live-sessions/${session.session_id}`, {
        method: 'DELETE',
      });
    } catch {
      // Best-effort session closure
    } finally {
      setSession(null);
      setSecondsRemaining(null);
      setIsExpired(false);
      setLoading(false);
      onSessionEnded?.();
    }
  };

  const handleDownloadCsv = () => {
    const csvData = buildC1Csv(samples);
    const filename = `live_capture_${session?.session_id || 'session'}.csv`;
    downloadCsvFile(csvData, filename);
  };

  const isConnected = connectionState === 'LIVE' || connectionState === 'STALE';

  return (
    <section
      role="region"
      aria-label="Live phone pairing controls"
      data-testid="pairing-panel"
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
        padding: '20px 24px',
        marginBottom: '20px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text)' }}>
            Phone Pairing & Telemetry Ingest
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
            Pair mobile Android collector to stream live 5G measurements (Contract C10).
          </p>
        </div>

        {session && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={handleDownloadCsv}
              data-testid="download-csv-btn"
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              📥 Download CSV ({samples.length} rows)
            </button>
            <button
              onClick={handleEndSession}
              disabled={loading}
              data-testid="end-session-btn"
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #ef4444',
                background: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              🛑 End Session
            </button>
          </div>
        )}
      </div>

      {/* Consent & Privacy Notice (Guardrail G28 / G29) */}
      <div
        style={{
          padding: '10px 14px',
          background: 'var(--color-bg)',
          border: '1px solid var(--color-border)',
          borderRadius: '6px',
          fontSize: '12px',
          color: 'var(--color-text-muted)',
          marginBottom: '16px',
          lineHeight: 1.4,
        }}
      >
        <strong>Privacy & Consent Notice (G28/G29):</strong> Telemetry sessions are strictly
        ephemeral and stored in server memory only during active operation. Cell identifiers are
        protected and precise GPS coordinates are never collected. Disconnecting the session
        permanently purges all in-memory live stream state.
      </div>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          style={{
            padding: '10px 14px',
            borderRadius: '6px',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            color: '#ef4444',
            fontSize: '13px',
            marginBottom: '16px',
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {!session ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handleStartSession}
            disabled={loading}
            data-testid="start-session-btn"
            style={{
              padding: '8px 18px',
              borderRadius: '6px',
              border: 'none',
              background: 'var(--color-primary)',
              color: '#ffffff',
              fontSize: '13px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Creating Session...' : '🔗 Start Live Session'}
          </button>
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
            Generates an 8-character single-use pairing code and QR code.
          </span>
        </div>
      ) : (
        <div
          style={{
            display: 'flex',
            gap: '24px',
            alignItems: 'center',
            flexWrap: 'wrap',
            padding: '16px',
            background: 'var(--color-bg)',
            border: '1px solid var(--color-border)',
            borderRadius: '6px',
          }}
        >
          {/* QR Code Graphic */}
          <SimpleQrCode text={session.pairing_code} />

          {/* Code, Countdown & Status */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              ENTER PAIRING CODE IN ANDROID COLLECTOR:
            </div>
            <div
              data-testid="pairing-code-display"
              style={{
                fontSize: '28px',
                fontWeight: 800,
                letterSpacing: '4px',
                fontFamily: 'var(--font-mono, monospace)',
                color: isExpired ? '#ef4444' : 'var(--color-primary)',
              }}
            >
              {session.pairing_code}
            </div>

            {/* Countdown / Expiration */}
            <div style={{ fontSize: '13px', color: 'var(--color-text)' }}>
              {isExpired ? (
                <div
                  role="alert"
                  data-testid="expired-notice"
                  style={{ color: '#ef4444', fontWeight: 600 }}
                >
                  ⚠️ Pairing code has expired.{' '}
                  <button
                    onClick={handleStartSession}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--color-primary)',
                      textDecoration: 'underline',
                      cursor: 'pointer',
                      fontWeight: 700,
                    }}
                  >
                    Click here to retry and generate a new code.
                  </button>
                </div>
              ) : (
                <span role="timer" aria-live="polite">
                  Code expires in:{' '}
                  <strong>
                    {Math.floor((secondsRemaining ?? 0) / 60)}:
                    {String((secondsRemaining ?? 0) % 60).padStart(2, '0')}
                  </strong>
                </span>
              )}
            </div>

            {/* Phone Connection State */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Status:</span>
              <span
                data-testid="pairing-status-badge"
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: isConnected ? 'rgba(22, 163, 74, 0.15)' : 'rgba(217, 119, 6, 0.15)',
                  color: isConnected ? '#16a34a' : '#d97706',
                  border: isConnected ? '1px solid #16a34a' : '1px solid #d97706',
                }}
              >
                {isConnected ? '🟢 Phone Connected' : '⏳ Waiting for phone connection...'}
              </span>
              <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                Session: <code>{session.session_id}</code>
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
