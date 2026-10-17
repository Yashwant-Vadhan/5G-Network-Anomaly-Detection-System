/**
 * Connection Chip & Live Announcements Component (T17-002).
 *
 * Implements:
 * - Connection chip displaying state icon, word, and sample age
 * - Chip text is not colour-only (includes distinct icon, text, and status description)
 * - Accessible aria-live="polite" announcement region
 * - Flapping-link protection: announces state transitions at most once per 30 seconds
 * - Optional alert announcements for incoming alerts
 */

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { ConnectionState } from '../types/contracts';

export interface ConnectionChipProps {
  state: ConnectionState;
  lastSampleTime?: string | Date | null;
  lastAlertMessage?: string | null;
  flappingWindowMs?: number; // Default 30,000 ms (30 s)
}

interface StateMetadata {
  icon: string;
  label: string;
  description: string;
  color: string;
  bg: string;
}

export const STATE_CONFIG: Record<ConnectionState, StateMetadata> = {
  LIVE: {
    icon: '🟢',
    label: 'Live',
    description: 'Connected and streaming telemetry',
    color: '#16a34a',
    bg: 'rgba(22, 163, 74, 0.15)',
  },
  STALE: {
    icon: '🟡',
    label: 'Stale',
    description: 'No telemetry received recently',
    color: '#d97706',
    bg: 'rgba(217, 119, 6, 0.15)',
  },
  RECONNECTING: {
    icon: '🔄',
    label: 'Reconnecting',
    description: 'Connection lost, attempting reconnection',
    color: '#2563eb',
    bg: 'rgba(37, 99, 235, 0.15)',
  },
  WAITING: {
    icon: '⏳',
    label: 'Waiting',
    description: 'Connected, awaiting initial phone stream',
    color: '#9333ea',
    bg: 'rgba(147, 51, 234, 0.15)',
  },
  DISCONNECTED: {
    icon: '⚪',
    label: 'Disconnected',
    description: 'No active connection',
    color: '#64748b',
    bg: 'rgba(100, 116, 139, 0.15)',
  },
  'REPLAY-SOURCE': {
    icon: '📼',
    label: 'Replay / Demo',
    description: 'Playback from offline demo dataset',
    color: 'var(--color-primary, #0284c7)',
    bg: 'rgba(2, 132, 199, 0.15)',
  },
};

export function formatAge(lastTime?: string | Date | null, nowMs: number = Date.now()): string {
  if (!lastTime) return 'no data';
  const t = typeof lastTime === 'string' ? new Date(lastTime).getTime() : lastTime.getTime();
  if (isNaN(t)) return 'no data';

  const diffSec = Math.max(0, Math.floor((nowMs - t) / 1000));
  if (diffSec < 2) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  return `${diffHr}h ago`;
}

export const ConnectionChip: React.FC<ConnectionChipProps> = ({
  state,
  lastSampleTime,
  lastAlertMessage,
  flappingWindowMs = 30000,
}) => {
  const [announcement, setAnnouncement] = useState<string>('');
  const lastStateChangeRef = useRef<number>(0);
  const prevStateRef = useRef<ConnectionState | null>(null);

  const [currentTimeMs, setCurrentTimeMs] = useState<number>(() => Date.now());

  // Periodically refresh sample age string
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTimeMs(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const ageText = useMemo(() => {
    return formatAge(lastSampleTime, currentTimeMs);
  }, [lastSampleTime, currentTimeMs]);

  const cfg = STATE_CONFIG[state] || STATE_CONFIG.DISCONNECTED;

  // Flapping link protection: announces state transition at most once per 30s
  useEffect(() => {
    const now = Date.now();
    const isInitial = prevStateRef.current === null;
    const isStateChanged = prevStateRef.current !== state;
    prevStateRef.current = state;

    if (!isStateChanged) return;

    if (!isInitial) {
      const timeSinceLastAnnouncement = now - lastStateChangeRef.current;
      if (lastStateChangeRef.current > 0 && timeSinceLastAnnouncement < flappingWindowMs) {
        // Flapping state change suppressed
        return;
      }
    }

    lastStateChangeRef.current = now;
    setAnnouncement(`Connection status changed to ${cfg.label}: ${cfg.description}`);
  }, [state, cfg.label, cfg.description, flappingWindowMs]);

  // Alert announcements
  useEffect(() => {
    if (lastAlertMessage) {
      setAnnouncement(`Alert notification: ${lastAlertMessage}`);
    }
  }, [lastAlertMessage]);

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center' }}>
      {/* Screen-reader aria-live announcement region */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        data-testid="live-announcement"
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: 0,
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0, 0, 0, 0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        {announcement}
      </div>

      {/* Visual Connection Chip */}
      <div
        data-testid="connection-chip"
        role="group"
        aria-label={`Connection state: ${cfg.label}, sample age: ${ageText}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: '3px 10px',
          borderRadius: '9999px',
          background: cfg.bg,
          border: `1px solid ${cfg.color}`,
          color: cfg.color,
          fontSize: '12px',
          fontWeight: 600,
        }}
      >
        <span aria-hidden="true">{cfg.icon}</span>
        <span>{cfg.label}</span>
        <span
          style={{
            color: 'var(--color-text-muted)',
            fontWeight: 400,
            fontSize: '11px',
            marginLeft: '2px',
          }}
        >
          ({ageText})
        </span>
      </div>
    </div>
  );
};
