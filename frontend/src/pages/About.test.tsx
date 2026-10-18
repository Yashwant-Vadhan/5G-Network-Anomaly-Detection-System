import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DataProvider } from '../data/DataContext';
import { About } from './About';
import { DemoBundle } from '../types/contracts';

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2026-10-18T10:00:00Z',
  model_version: '2.0.0',
  source: 'processed',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: 'a1b2c3d4e5f60718',
    cell_lookup: {},
  },
  quality: {
    preprocess_log: {
      total_raw: 5532,
      clean_rows: 5528,
      dropped: 4,
    },
  },
  model_meta: {
    contamination: 0.05,
    model_name: 'if_v1',
  },
  sessions: [],
  samples: { columns: [], rows: [] },
  transitions: [],
  events: [],
};

describe('About Component (T16-015)', () => {
  it('renders page header and descriptive caption', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    expect(
      screen.getByRole('heading', { level: 1, name: /7\. About & Limitations/i })
    ).toBeDefined();
    expect(
      screen.getByText(/Research positioning, system non-claims, privacy architecture/i)
    ).toBeDefined();
  });

  it('renders research prototype statement per Guardrail G31', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Research prototype notice/i })).toBeDefined();
    expect(screen.getByText(/Research Prototype Statement \(G31\):/i)).toBeDefined();
    expect(screen.getByText(/exploratory academic research prototype/i)).toBeDefined();
  });

  it('renders dataset summary metrics', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Dataset summary/i })).toBeDefined();
    expect(screen.getByText('5,528')).toBeDefined();
    expect(screen.getByText('2 Phones')).toBeDefined();
    expect(screen.getByText('Airtel 5G NSA')).toBeDefined();
  });

  it('renders privacy and data minimization notes per G27 and G28', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Privacy architecture note/i })).toBeDefined();
    expect(screen.getByText(/Zero PII Collection:/i)).toBeDefined();
    expect(screen.getByText(/Cell Identifier Anonymization:/i)).toBeDefined();
    expect(screen.getByText(/Zero Public Disk Retention \(G29\):/i)).toBeDefined();
  });

  it('renders active model metadata', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Model metadata/i })).toBeDefined();
    expect(screen.getByText(/if_v1/i)).toBeDefined();
    expect(screen.getByText('0.05')).toBeDefined();
  });

  it('renders explicit system non-claims (Acceptance Criteria)', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Explicit non-claims list/i })).toBeDefined();
    expect(screen.getByText(/Not Universal 5G Detection:/i)).toBeDefined();
    expect(screen.getByText(/No Guaranteed Root Cause:/i)).toBeDefined();
    expect(screen.getByText(/No Inferred Architecture:/i)).toBeDefined();
    expect(screen.getByText(/No Operator Network Control:/i)).toBeDefined();
    expect(screen.getByText(/No Universal Thresholds:/i)).toBeDefined();
    expect(screen.getByText(/Not Every Cell Transition is Anomalous:/i)).toBeDefined();
    expect(screen.getByText(/Measurement Path Performs No Heavy ML:/i)).toBeDefined();
    expect(screen.getByText(/No Hard Latency Guarantees:/i)).toBeDefined();
    expect(screen.getByText(/Not a Safety or Outage Notification System:/i)).toBeDefined();
    expect(screen.getByText(/No Carrier Infrastructure Visibility:/i)).toBeDefined();
    expect(screen.getByText(/Live Results are Provisional:/i)).toBeDefined();
    expect(screen.getByText(/External Protocols Not Implemented:/i)).toBeDefined();
    expect(screen.getByText(/Academic Research Prototype:/i)).toBeDefined();
  });

  it('does not make un-hedged real-time claims per Guardrail G24', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    // Text must emphasize near-real-time or empirical latency without hard guarantees
    expect(screen.getAllByText(/near-real-time/i).length).toBeGreaterThanOrEqual(1);
  });
});
