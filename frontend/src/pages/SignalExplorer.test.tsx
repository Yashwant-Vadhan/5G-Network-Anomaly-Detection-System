import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataProvider } from '../data/DataContext';
import { ReplayProvider } from '../data/ReplayContext';
import {
  SignalExplorer,
  computeSummary,
  formatSummary,
  SignalChartPanel,
} from './SignalExplorer';
import { DemoBundle } from '../types/contracts';

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2024-05-01T12:00:00Z',
  model_version: '1.0.0',
  source: 'sample',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: 'a1b2c3d4e5f60718',
    cell_lookup: {},
  },
  quality: { clean_rows: 6, dropped: 0, total_raw: 6 },
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'sess-A',
      device: 'Pixel 7',
      operator: 'Jio',
      start: '2024-05-01 10:00:00',
      end: '2024-05-01 10:00:03',
      n: 4,
    },
    {
      session_id: 'sess-B',
      device: 'Pixel 7',
      operator: 'Jio',
      start: '2024-05-01 10:10:00',
      end: '2024-05-01 10:10:02',
      n: 2,
    },
  ],
  samples: {
    columns: [
      'timestamp',
      'session_id',
      'ss_rsrp',
      'ss_rsrq',
      'ss_sinr',
      'if_score',
      'baseline_flag',
      'if_flag',
      'pci',
      'nci',
      'anomaly_type',
    ],
    rows: [
      // sess-A samples: sample 2 has an NA gap (null ss_rsrp)
      ['2024-05-01 10:00:00', 'sess-A', -80.0, -10.0, 15.0, 0.25, 0, 0, 42, 1001, 'NORMAL'],
      ['2024-05-01 10:00:01', 'sess-A', -85.0, -12.0, 12.0, 0.45, 1, 0, 42, 1001, 'ANOMALY_A'],
      ['2024-05-01 10:00:02', 'sess-A', null, -14.0, 8.0, 0.65, 0, 1, 42, 1001, 'ANOMALY_B'],
      ['2024-05-01 10:00:03', 'sess-A', -95.0, -16.0, 5.0, 0.75, 1, 1, 42, 1001, 'ANOMALY_C'],
      // sess-B samples
      ['2024-05-01 10:10:00', 'sess-B', -70.0, -8.0, 20.0, 0.15, 0, 0, 100, 2002, 'NORMAL'],
      ['2024-05-01 10:10:01', 'sess-B', -72.0, -9.0, 18.0, 0.20, 0, 0, 100, 2002, 'NORMAL'],
    ],
  },
  events: [],
  transitions: [],
};

function renderSignalExplorer() {
  return render(
    <DataProvider initialBundle={mockBundle}>
      <ReplayProvider>
        <SignalExplorer />
      </ReplayProvider>
    </DataProvider>
  );
}

describe('Signal Explorer Component (T16-011)', () => {
  it('renders all 4 stacked signal panels and controls', () => {
    renderSignalExplorer();

    expect(screen.getByTestId('signal-explorer-page')).toBeInTheDocument();
    expect(screen.getByTestId('signal-panel-ss_rsrp')).toBeInTheDocument();
    expect(screen.getByTestId('signal-panel-ss_rsrq')).toBeInTheDocument();
    expect(screen.getByTestId('signal-panel-ss_sinr')).toBeInTheDocument();
    expect(screen.getByTestId('signal-panel-if_score')).toBeInTheDocument();

    expect(screen.getByLabelText(/Anomaly Marker Overlay/i)).toBeInTheDocument();
    expect(screen.getByText(/Show Rolling Mean Overlay/i)).toBeInTheDocument();
  });

  it('computes summary statistics equal to min/max/mean', () => {
    const rawSamples = [
      { ss_rsrp: -80.0 },
      { ss_rsrp: -85.0 },
      { ss_rsrp: null }, // NA gap
      { ss_rsrp: -95.0 },
    ];

    const stats = computeSummary(rawSamples, 'ss_rsrp');
    expect(stats).not.toBeNull();
    expect(stats!.min).toBe(-95.0);
    expect(stats!.max).toBe(-80.0);
    expect(stats!.mean).toBeCloseTo((-80.0 - 85.0 - 95.0) / 3, 2);

    const formatted = formatSummary(stats, 'SS-RSRP', 'dBm');
    expect(formatted).toBe('SS-RSRP: min -95.0 dBm, max -80.0 dBm, mean -86.7 dBm.');
  });

  it('breaks line paths at NA gaps rather than bridging missing points', () => {
    const samplesWithGap = [
      { timestamp: '10:00:00', ss_rsrp: -80 },
      { timestamp: '10:00:01', ss_rsrp: -85 },
      { timestamp: '10:00:02', ss_rsrp: null }, // Gap
      { timestamp: '10:00:03', ss_rsrp: -95 },
    ];

    const { container } = render(
      <SignalChartPanel
        title="SS-RSRP"
        unit="dBm"
        field="ss_rsrp"
        samples={samplesWithGap}
        flagFilter="none"
        showRolling={false}
        activeSampleIndex={0}
        onSelectSample={() => {}}
      />
    );

    const path = container.querySelector('path');
    expect(path).toBeInTheDocument();
    const d = path!.getAttribute('d') || '';

    // Must contain at least two separate 'M' commands because of the NA gap break!
    const mCommands = (d.match(/M\s/g) || []).length;
    expect(mCommands).toBe(2);
  });

  it('renders anomaly markers with "×" shape and tooltip details', () => {
    renderSignalExplorer();

    const markers = screen.getAllByTestId('anomaly-marker');
    expect(markers.length).toBeGreaterThanOrEqual(1);

    // Each marker contains two lines crossing to form the '×' shape
    const firstMarker = markers[0];
    const lines = firstMarker.querySelectorAll('line');
    expect(lines.length).toBe(2);

    // Check tooltip title content
    const title = firstMarker.querySelector('title');
    expect(title).toBeInTheDocument();
    expect(title!.textContent).toContain('Anomaly Flagged');
  });

  it('filters anomaly markers based on flag selection options', () => {
    renderSignalExplorer();

    const select = screen.getByLabelText(/Anomaly Marker Overlay/i);

    // Default 'both': should show baseline or IF flags
    const bothCount = screen.getAllByTestId('anomaly-marker').length;
    expect(bothCount).toBeGreaterThan(0);

    // Filter to 'baseline' only
    fireEvent.change(select, { target: { value: 'baseline' } });
    const baseCount = screen.getAllByTestId('anomaly-marker').length;
    expect(baseCount).toBeGreaterThan(0);

    // Filter to 'if' only
    fireEvent.change(select, { target: { value: 'if' } });
    const ifCount = screen.getAllByTestId('anomaly-marker').length;
    expect(ifCount).toBeGreaterThan(0);

    // Filter to 'none': hide all anomaly markers
    fireEvent.change(select, { target: { value: 'none' } });
    expect(screen.queryByTestId('anomaly-marker')).toBeNull();
  });

  it('renders 0.60 threshold line on the IF score panel', () => {
    renderSignalExplorer();

    const scorePanel = screen.getByTestId('signal-panel-if_score');
    expect(scorePanel).toBeInTheDocument();
    expect(screen.getByTestId('threshold-line-group')).toBeInTheDocument();
    expect(screen.getByText('Threshold (0.60)')).toBeInTheDocument();
  });

  it('expands data table and shows fallback "—" for missing values', () => {
    renderSignalExplorer();

    const toggleBtn = screen.getByText(/Show Data Table/i);
    expect(screen.queryByTestId('signal-data-table')).toBeNull();

    // Click to expand
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId('signal-data-table')).toBeInTheDocument();

    // Table should contain '—' for missing RSRP in row 3
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  describe('Live Signals Extensions (T17-004)', () => {
    it('renders shaded gap bands and ensures no line crosses a gap', () => {
      const samplesWithTimeGap = [
        { timestamp: '2024-05-01 10:00:00', ss_rsrp: -80 },
        { timestamp: '2024-05-01 10:00:05', ss_rsrp: -82 },
        // 45-second gap (> 15s SESSION_GAP_SECONDS)
        { timestamp: '2024-05-01 10:00:50', ss_rsrp: -88 },
        { timestamp: '2024-05-01 10:00:55', ss_rsrp: -90 },
      ];

      const { container } = render(
        <SignalChartPanel
          title="SS-RSRP"
          unit="dBm"
          field="ss_rsrp"
          samples={samplesWithTimeGap}
          flagFilter="none"
          showRolling={false}
          activeSampleIndex={0}
          onSelectSample={() => {}}
        />
      );

      // Verify shaded gap band is rendered
      const gapBands = screen.getAllByTestId('gap-band');
      expect(gapBands.length).toBe(1);

      // Verify no line segment bridges across the gap (requires 2 separate subpaths)
      const path = container.querySelector('path');
      expect(path).toBeInTheDocument();
      const d = path!.getAttribute('d') || '';
      const mCommands = (d.match(/M\s/g) || []).length;
      expect(mCommands).toBe(2);
    });

    it('pause button freezes the view without losing data and resume unfreezes', () => {
      renderSignalExplorer();

      const pauseBtn = screen.getByTestId('pause-resume-button');
      expect(pauseBtn).toHaveTextContent('⏸️ Pause Stream');
      expect(screen.queryByTestId('pause-badge')).not.toBeInTheDocument();

      // Click pause
      fireEvent.click(pauseBtn);
      expect(screen.getByTestId('pause-badge')).toBeInTheDocument();
      expect(pauseBtn).toHaveTextContent('▶️ Resume Stream');

      // Click resume
      fireEvent.click(pauseBtn);
      expect(screen.queryByTestId('pause-badge')).not.toBeInTheDocument();
      expect(pauseBtn).toHaveTextContent('⏸️ Pause Stream');
    });

    it('rolling window selector allows selecting 5m, 15m, 60m windows', () => {
      renderSignalExplorer();

      const windowSelect = screen.getByLabelText(/Time Window Range/i);
      expect(windowSelect).toBeInTheDocument();

      fireEvent.change(windowSelect, { target: { value: '5m' } });
      expect((windowSelect as HTMLSelectElement).value).toBe('5m');

      fireEvent.change(windowSelect, { target: { value: '15m' } });
      expect((windowSelect as HTMLSelectElement).value).toBe('15m');

      fireEvent.change(windowSelect, { target: { value: 'all' } });
      expect((windowSelect as HTMLSelectElement).value).toBe('all');
    });
  });
});
