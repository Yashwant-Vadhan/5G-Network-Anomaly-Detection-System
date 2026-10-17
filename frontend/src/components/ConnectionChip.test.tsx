import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ConnectionChip, formatAge, STATE_CONFIG } from './ConnectionChip';
import { ConnectionState } from '../types/contracts';

describe('ConnectionChip Component (T17-002)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders all 6 connection states with non-colour indicators (icons and labels)', () => {
    const states: ConnectionState[] = [
      'LIVE',
      'STALE',
      'RECONNECTING',
      'WAITING',
      'DISCONNECTED',
      'REPLAY-SOURCE',
    ];

    for (const st of states) {
      const { unmount } = render(
        <ConnectionChip state={st} lastSampleTime="2024-05-01T10:00:00Z" />
      );

      const cfg = STATE_CONFIG[st];
      const chip = screen.getByTestId('connection-chip');
      expect(chip).toBeInTheDocument();

      // State label and icon must be present (not colour-only)
      expect(screen.getByText(cfg.label)).toBeInTheDocument();
      expect(screen.getByText(cfg.icon)).toBeInTheDocument();

      unmount();
    }
  });

  it('formats sample age accurately', () => {
    const now = new Date('2024-05-01T10:00:00Z').getTime();

    expect(formatAge(null, now)).toBe('no data');
    expect(formatAge(undefined, now)).toBe('no data');
    expect(formatAge('invalid-date', now)).toBe('no data');

    // 1 second ago -> just now
    expect(formatAge(new Date('2024-05-01T09:59:59Z'), now)).toBe('just now');

    // 15 seconds ago -> 15s ago
    expect(formatAge(new Date('2024-05-01T09:59:45Z'), now)).toBe('15s ago');

    // 5 minutes ago -> 5m ago
    expect(formatAge(new Date('2024-05-01T09:55:00Z'), now)).toBe('5m ago');

    // 2 hours ago -> 2h ago
    expect(formatAge(new Date('2024-05-01T08:00:00Z'), now)).toBe('2h ago');
  });

  it('announces connection status changes in aria-live region', () => {
    const { rerender } = render(<ConnectionChip state="LIVE" />);

    const liveRegion = screen.getByTestId('live-announcement');
    expect(liveRegion).toHaveAttribute('aria-live', 'polite');
    expect(liveRegion).toHaveTextContent(/status changed to Live/i);

    // Change state after 35 seconds
    act(() => {
      vi.advanceTimersByTime(35000);
    });

    rerender(<ConnectionChip state="STALE" />);
    expect(liveRegion).toHaveTextContent(/status changed to Stale/i);
  });

  it('suppresses announcements when link is flapping within 30 seconds', () => {
    const { rerender } = render(
      <ConnectionChip state="LIVE" flappingWindowMs={30000} />
    );

    const liveRegion = screen.getByTestId('live-announcement');
    expect(liveRegion).toHaveTextContent(/status changed to Live/i);

    // State changes 5 seconds later (flapping)
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    rerender(<ConnectionChip state="RECONNECTING" flappingWindowMs={30000} />);

    // Flapping transition is suppressed — announcement text remains Live
    expect(liveRegion).toHaveTextContent(/status changed to Live/i);

    // Another rapid change 5 seconds later
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    rerender(<ConnectionChip state="LIVE" flappingWindowMs={30000} />);
    expect(liveRegion).toHaveTextContent(/status changed to Live/i);

    // Advance past the 30-second window (25s more -> 35s total elapsed)
    act(() => {
      vi.advanceTimersByTime(25000);
    });
    rerender(<ConnectionChip state="STALE" flappingWindowMs={30000} />);

    // Now announcement triggers because 30 seconds elapsed since the last announcement!
    expect(liveRegion).toHaveTextContent(/status changed to Stale/i);
  });

  it('announces alert messages when triggered', () => {
    const { rerender } = render(
      <ConnectionChip state="LIVE" lastAlertMessage={null} />
    );

    const liveRegion = screen.getByTestId('live-announcement');

    rerender(
      <ConnectionChip
        state="LIVE"
        lastAlertMessage="COVERAGE_HOLE detected with HIGH severity"
      />
    );

    expect(liveRegion).toHaveTextContent(
      'Alert notification: COVERAGE_HOLE detected with HIGH severity'
    );
  });
});
