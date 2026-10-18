import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { HashRouter } from 'react-router-dom';
import App, { sanitizeErrorMessage } from './App';
import { PAGES } from './constants/pages';
import { DemoBundle } from './types/contracts';

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2026-10-12T10:00:00Z',
  model_version: '1.0.0',
  source: 'sample',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: 'a1b2c3d4e5f60718',
    cell_lookup: {},
  },
  quality: { clean_rows: 3, dropped: 0, total_raw: 3 },
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'redmi-1',
      device: 'Redmi 13 5G',
      operator: 'Airtel',
      start: '2026-10-09 11:00:00',
      end: '2026-10-09 11:05:00',
      n: 24,
    },
    {
      session_id: 'samsung-1',
      device: 'Samsung Galaxy S21',
      operator: 'Jio',
      start: '2026-10-09 10:15:00',
      end: '2026-10-09 10:15:06',
      n: 3,
    },
  ],
  samples: {
    columns: ['timestamp', 'session_id', 'ss_rsrp'],
    rows: [
      ['2026-10-09 11:00:00', 'redmi-1', -85.0],
      ['2026-10-09 10:15:00', 'samsung-1', -95.0],
    ],
  },
  transitions: [],
  events: [],
};

describe('App Shell & Navigation (T16-006 / T16-007)', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('renders unified brand header with mode label and no deploy chrome', () => {
    render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );
    expect(screen.getByText('5G-NADS')).toBeInTheDocument();
    expect(screen.getByText('Static Demo (Mode 1)')).toBeInTheDocument();
    const header = screen.getByRole('banner');
    expect(within(header).queryByText(/deploy/i)).not.toBeInTheDocument();
  });

  it('renders all page navigation links', () => {
    render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );
    const nav = screen.getByRole('navigation', { name: /primary navigation/i });
    PAGES.forEach(page => {
      expect(within(nav).getByText(page.label)).toBeInTheDocument();
    });
  });

  it('renders research prototype notice in footer per G31', () => {
    render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );
    expect(screen.getByText(/Academic research prototype/i)).toBeInTheDocument();
    expect(screen.getByText(/App: v2.1.0/i)).toBeInTheDocument();
  });

  it('toggles and persists theme in localStorage', () => {
    render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );
    const themeBtn = screen.getByLabelText(/Toggle light and dark theme/i);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    fireEvent.click(themeBtn);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('nads_theme')).toBe('dark');

    fireEvent.click(themeBtn);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('nads_theme')).toBe('light');
  });

  it('supports keyboard navigation to every route', () => {
    render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );
    const nav = screen.getByRole('navigation', { name: /primary navigation/i });
    const links = within(nav).getAllByRole('link');
    expect(links).toHaveLength(PAGES.length);

    links.forEach((link, idx) => {
      link.focus();
      expect(link).toHaveFocus();
      expect(link).toHaveAttribute('href', `#${PAGES[idx].path}`);
    });
  });

  it('renders filters area with device, operator, and session controls (T16-008)', () => {
    render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );
    expect(screen.getByLabelText(/filters and session controls/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Filter by device/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Filter by operator/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Select session/i)).toBeInTheDocument();
    expect(screen.getByText(/Active Subset:/i)).toBeInTheDocument();
  });

  describe('Mode switch and labels (T17-010)', () => {
    it('switches between Recorded demo data and Live with always visible mode label', () => {
      render(
        <HashRouter>
          <App initialBundle={mockBundle} />
        </HashRouter>
      );
      const modeLabel = screen.getByTestId('mode-label');
      expect(modeLabel).toBeInTheDocument();
      expect(modeLabel).toHaveTextContent('Recorded demo data');
      expect(screen.getByText('Static Demo (Mode 1)')).toBeInTheDocument();

      const switchBtn = screen.getByTestId('mode-switch-btn');
      expect(switchBtn).toHaveTextContent('Switch to Live');

      fireEvent.click(switchBtn);
      expect(modeLabel).toBeInTheDocument();
      expect(modeLabel).toHaveTextContent('Live');
      expect(switchBtn).toHaveTextContent('Switch to Demo');
      expect(screen.getByTestId('pair-phone-btn')).toBeInTheDocument();

      fireEvent.click(switchBtn);
      expect(modeLabel).toBeInTheDocument();
      expect(modeLabel).toHaveTextContent('Recorded demo data');
      expect(switchBtn).toHaveTextContent('Switch to Live');
    });
  });

  describe('Empty and error states in Live mode (T17-010)', () => {
    it('displays unreachable server state with fix text and no stack traces', () => {
      render(
        <HashRouter>
          <App
            initialBundle={mockBundle}
            initialMode="live"
            initialConnectionState="DISCONNECTED"
          />
        </HashRouter>
      );
      const unreachableCard = screen.getByTestId('server-unreachable-card');
      expect(unreachableCard).toBeInTheDocument();
      expect(
        within(unreachableCard).getByText('Streaming Server Unreachable')
      ).toBeInTheDocument();
      expect(
        within(unreachableCard).getByText(/python -m streaming.server/i)
      ).toBeInTheDocument();
      expect(within(unreachableCard).queryByText(/Traceback/i)).not.toBeInTheDocument();

      const retryBtn = screen.getByTestId('retry-connection-btn');
      fireEvent.click(retryBtn);
      expect(screen.queryByTestId('server-unreachable-card')).not.toBeInTheDocument();
      expect(screen.getByTestId('no-session-card')).toBeInTheDocument();
    });

    it('displays no session state with fix instructions and pairing button', () => {
      render(
        <HashRouter>
          <App
            initialBundle={mockBundle}
            initialMode="live"
            initialConnectionState="WAITING"
          />
        </HashRouter>
      );
      const noSessionCard = screen.getByTestId('no-session-card');
      expect(noSessionCard).toBeInTheDocument();
      expect(
        within(noSessionCard).getByRole('button', { name: /Open Pairing Panel/i })
      ).toBeInTheDocument();
      expect(within(noSessionCard).getByText(/6-digit PIN/i)).toBeInTheDocument();

      const openPairingBtn = screen.getByTestId('open-pairing-btn');
      fireEvent.click(openPairingBtn);
      expect(screen.getByTestId('pairing-panel')).toBeInTheDocument();
      expect(screen.getByText('Phone Pairing & Telemetry Ingest')).toBeInTheDocument();
    });
  });

  describe('Error Sanitization (T17-010)', () => {
    it('sanitizes python tracebacks to prevent stack traces from showing', () => {
      const rawTrace = [
        'Traceback (most recent call last):',
        '  File "streaming/server.py", line 142, in process_frame',
        '    raise ValueError("unexpected payload")',
        'ValueError: unexpected payload',
      ].join('\n');

      const sanitized = sanitizeErrorMessage(rawTrace);
      expect(sanitized).toBe('A server processing error occurred. Check backend logs.');
      expect(sanitized).not.toContain('Traceback');
      expect(sanitized).not.toContain('streaming/server.py');
      expect(sanitized).not.toContain('line 142');
    });

    it('preserves clean user-facing error messages', () => {
      expect(sanitizeErrorMessage('Network connection lost')).toBe('Network connection lost');
      expect(sanitizeErrorMessage('')).toBe('');
      expect(sanitizeErrorMessage(null)).toBe('');
    });
  });
});
