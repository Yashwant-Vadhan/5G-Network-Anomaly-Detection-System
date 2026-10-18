import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataProvider } from '../data/DataContext';
import { CellsNetwork, formatCellId } from './CellsNetwork';
import { DemoBundle, BundleTransition } from '../types/contracts';

const mockTransitions: BundleTransition[] = [
  {
    sample_idx: 12,
    timestamp: '2026-10-18 10:00:36',
    device: 'Pixel 7 Pro',
    session_id: 'sess-cells-1',
    pci_from: 42,
    pci_to: 108,
    nci_from: 1234567,
    nci_to: 1234568,
    nrarfcn_from: 632000,
    nrarfcn_to: 632000,
    kind: 'PCI Handover',
    type: 'PCI Handover',
  },
  {
    sample_idx: 28,
    timestamp: '2026-10-18 10:01:24',
    device: 'Pixel 7 Pro',
    session_id: 'sess-cells-1',
    pci_from: 108,
    pci_to: 215,
    nci_from: 1234568,
    nci_to: 9876543,
    nrarfcn_from: 632000,
    nrarfcn_to: 633000,
    kind: 'Carrier Shift',
    type: 'Carrier Shift',
  },
];

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2026-10-18T10:00:00Z',
  model_version: '2.0.0',
  source: 'sample',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: 'a1b2c3d4e5f60718',
    cell_lookup: {},
  },
  quality: { clean_rows: 4, dropped: 0, total_raw: 4 },
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'sess-cells-1',
      device: 'Pixel 7 Pro',
      operator: 'Jio',
      start: '2026-10-18 10:00:00',
      end: '2026-10-18 10:02:00',
      n: 4,
    },
  ],
  samples: {
    columns: [
      'session_id',
      'sample_idx',
      'timestamp',
      'device',
      'operator',
      'pci',
      'nci',
      'nrarfcn',
      'deployment_mode',
    ],
    rows: [
      ['sess-cells-1', 0, '2026-10-18 10:00:00', 'Pixel 7 Pro', 'Jio', 42, 1234567, 632000, 'SA'],
      ['sess-cells-1', 1, '2026-10-18 10:00:03', 'Pixel 7 Pro', 'Jio', 42, 1234567, 632000, 'SA'],
      ['sess-cells-1', 2, '2026-10-18 10:00:06', 'Pixel 7 Pro', 'Jio', 108, 1234568, 632000, 'SA'],
      ['sess-cells-1', 3, '2026-10-18 10:00:09', 'Pixel 7 Pro', 'Jio', 215, 9876543, 633000, 'SA'],
    ],
  },
  transitions: mockTransitions,
  events: [],
};

describe('Cells & Network Page (T16-012 / Guardrail G30)', () => {
  it('formats cell IDs and sentinel values correctly', () => {
    expect(formatCellId(42)).toBe('42');
    expect(formatCellId('1234567')).toBe('1234567');
    expect(formatCellId(null)).toBe('—');
    expect(formatCellId(undefined)).toBe('—');
    expect(formatCellId('NA')).toBe('—');
    expect(formatCellId('<NA>')).toBe('—');
  });

  it('renders page heading and normal behaviour operational note', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork />
      </DataProvider>
    );

    expect(screen.getByTestId('cells-network-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Cells & Network' })).toBeInTheDocument();

    const note = screen.getByTestId('normal-behavior-note');
    expect(note).toBeInTheDocument();
    expect(note).toHaveTextContent(/cell change is normal behaviour/i);
    expect(note).toHaveTextContent(/does not represent an anomaly/i);
  });

  it('displays transition count equal to bundle transitions (G30)', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork />
      </DataProvider>
    );

    const badge = screen.getByTestId('transition-count-badge');
    expect(badge).toBeInTheDocument();
    // Must strictly equal mockTransitions.length (2)
    expect(badge).toHaveTextContent('2');
  });

  it('renders serving cell metrics and categorical step chart', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork />
      </DataProvider>
    );

    // Latest sample PCI is 215, NCI 9876543, NRARFCN 633000
    expect(screen.getAllByText('215')[0]).toBeInTheDocument();
    expect(screen.getAllByText('9876543')[0]).toBeInTheDocument();
    expect(screen.getAllByText('633000')[0]).toBeInTheDocument();

    const chart = screen.getByTestId('cell-step-chart');
    expect(chart).toBeInTheDocument();
  });

  it('renders transition table rows matching bundle transitions', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork />
      </DataProvider>
    );

    const table = screen.getByTestId('transitions-table');
    expect(table).toBeInTheDocument();
    expect(screen.getByText('PCI Handover')).toBeInTheDocument();
    expect(screen.getByText('Carrier Shift')).toBeInTheDocument();
    expect(screen.getByText('42 -> 108')).toBeInTheDocument();
    expect(screen.getByText('108 -> 215')).toBeInTheDocument();
  });

  it('filters transitions via search query', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork />
      </DataProvider>
    );

    const filterInput = screen.getByPlaceholderText(/filter transitions/i);
    fireEvent.change(filterInput, { target: { value: 'Carrier' } });

    expect(screen.getByText('Carrier Shift')).toBeInTheDocument();
    expect(screen.queryByText('PCI Handover')).not.toBeInTheDocument();
  });

  it('renders in Live mode with connection badge and live telemetry', () => {
    const liveSamples = [
      { pci: 55, nci: 555555, nrarfcn: 634000, deployment_mode: 'SA', timestamp: '10:10:00' },
      { pci: 99, nci: 999999, nrarfcn: 635000, deployment_mode: 'SA', timestamp: '10:10:03' },
    ];

    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork
          isLiveMode={true}
          connectionState="LIVE"
          liveSamples={liveSamples}
        />
      </DataProvider>
    );

    const badge = screen.getByTestId('live-state-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('LIVE');
    expect(badge).toHaveTextContent('2 frames');

    // Serving cell cards reflect latest live sample (pci: 99, nci: 999999, nrarfcn: 635000)
    expect(screen.getAllByText('99')[0]).toBeInTheDocument();
    expect(screen.getAllByText('999999')[0]).toBeInTheDocument();
    expect(screen.getAllByText('635000')[0]).toBeInTheDocument();
  });

  it('supports window filter selection in Live mode', () => {
    const liveSamples = Array.from({ length: 150 }, (_, i) => ({
      pci: 100 + (i % 5),
      nci: 1000 + i,
      nrarfcn: 632000,
      timestamp: `10:00:${i}`,
    }));

    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork
          isLiveMode={true}
          connectionState="LIVE"
          liveSamples={liveSamples}
        />
      </DataProvider>
    );

    const btn5m = screen.getByRole('button', { name: '5M' });
    expect(btn5m).toBeInTheDocument();
    fireEvent.click(btn5m);

    // Switching to 5M caps window to 100 samples
    const chart = screen.getByTestId('cell-step-chart');
    expect(chart).toBeInTheDocument();
  });

  it('renders server-pushed liveTransitions directly (G30)', () => {
    const liveTrans: BundleTransition[] = [
      {
        sample_idx: 5,
        timestamp: '2026-10-18 10:05:00',
        device: 'Live Pixel',
        session_id: 'live-sess',
        pci_from: 55,
        pci_to: 99,
        nci_from: 555555,
        nci_to: 999999,
        kind: 'Server Handover',
        type: 'Server Handover',
      },
    ];

    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork
          isLiveMode={true}
          connectionState="LIVE"
          liveTransitions={liveTrans}
        />
      </DataProvider>
    );

    const badge = screen.getByTestId('transition-count-badge');
    expect(badge).toHaveTextContent('1');
    expect(screen.getByText('Server Handover')).toBeInTheDocument();
    expect(screen.getByText('55 -> 99')).toBeInTheDocument();
  });

  it('maps server CELL_TRANSITION events when liveTransitions is empty (G30)', () => {
    const liveEvents = [
      {
        event_id: 'evt-cell-1',
        session_id: 'live-sess',
        device: 'Live Pixel',
        anomaly_type: 'CELL_TRANSITION' as const,
        severity: 'LOW' as const,
        score: 0.1,
        start: '2026-10-18 10:08:00',
        end: '2026-10-18 10:08:00',
        duration_sec: 0,
        ml: { pci_from: 200, pci_to: 300, nci_from: 111, nci_to: 222 },
        summary: 'Server detected transition',
      },
    ];

    render(
      <DataProvider initialBundle={mockBundle}>
        <CellsNetwork
          isLiveMode={true}
          connectionState="LIVE"
          liveEvents={liveEvents}
        />
      </DataProvider>
    );

    const badge = screen.getByTestId('transition-count-badge');
    expect(badge).toHaveTextContent('1');
    expect(screen.getByText('Server Cell Transition')).toBeInTheDocument();
    expect(screen.getByText('200 -> 300')).toBeInTheDocument();
    expect(screen.getByText('111 -> 222')).toBeInTheDocument();
  });

  it('renders empty table state when transitions array is empty', () => {
    render(
      <DataProvider initialBundle={{ ...mockBundle, transitions: [] }}>
        <CellsNetwork transitionsOverride={[]} />
      </DataProvider>
    );

    expect(
      screen.getByText(/no cell or network transitions recorded for this session/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId('transition-count-badge')).toHaveTextContent('0');
  });
});


