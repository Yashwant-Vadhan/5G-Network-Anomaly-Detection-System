import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { HashRouter } from 'react-router-dom';
import App from './App';
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
    expect(screen.queryByText(/deploy/i)).not.toBeInTheDocument();
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
});
