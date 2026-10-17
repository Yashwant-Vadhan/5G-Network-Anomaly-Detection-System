import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DataProvider } from '../data/DataContext';
import {
  StreamHealth,
  StreamMetricsData,
  NO_LATENCY_GUARANTEE_FOOTNOTE,
  formatMetricNum,
} from './StreamHealth';
import { DemoBundle } from '../types/contracts';

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2024-05-01T12:00:00Z',
  model_version: '2.1.0',
  source: 'sample',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: '9f8e7d6c5b4a3210',
    cell_lookup: {},
  },
  quality: { clean_rows: 10, dropped: 2, total_raw: 12 },
  model_meta: {
    contamination: 0.05,
    model_name: 'if_v2_streaming',
  },
  sessions: [],
  samples: { columns: [], rows: [] },
  events: [],
  transitions: [],
};

const sampleMetrics: StreamMetricsData = {
  p50_latency_ms: 15.2,
  p95_latency_ms: 38.7,
  max_latency_ms: 74.9,
  sequence_gaps: [{ expected: 10, received: 14 }],
  duplicates_count: 3,
  drops_count: 5,
  skew_estimate_s: 0.032,
  queue_depth: 2,
  edge_divergence: '0.012',
  model_name: 'if_v2_streaming',
  model_version: '2.1.0',
  model_hash: '9f8e7d6c5b4a3210',
};

function renderStreamHealth(props: {
  metrics?: StreamMetricsData;
  edgeDivergenceEnabled?: boolean;
} = {}) {
  return render(
    <DataProvider initialBundle={mockBundle}>
      <StreamHealth {...props} />
    </DataProvider>
  );
}

describe('Stream Health Component (T17-007)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders latency percentiles exactly matching values served by /metrics', () => {
    renderStreamHealth({ metrics: sampleMetrics });

    expect(screen.getByTestId('stream-health-page')).toBeInTheDocument();
    expect(screen.getByTestId('latency-percentiles-card')).toBeInTheDocument();

    // p50
    expect(screen.getByTestId('p50-latency')).toHaveTextContent('15.2 ms');
    // p95
    expect(screen.getByTestId('p95-latency')).toHaveTextContent('38.7 ms');
    // max
    expect(screen.getByTestId('max-latency')).toHaveTextContent('74.9 ms');
  });

  it('renders the mandatory "no latency guarantee" footnote verbatim', () => {
    renderStreamHealth({ metrics: sampleMetrics });

    const footnote = screen.getByTestId('latency-guarantee-footnote');
    expect(footnote).toBeInTheDocument();
    expect(footnote.textContent).toContain(
      'Near-real-time monitoring of UE-side measurements with no latency guarantee'
    );
    expect(footnote.textContent).toBe(NO_LATENCY_GUARANTEE_FOOTNOTE);
  });

  it('renders message integrity, sequence gaps, and queue metrics', () => {
    renderStreamHealth({ metrics: sampleMetrics });

    expect(screen.getByTestId('sequence-gaps-count')).toHaveTextContent('1');
    expect(screen.getByTestId('duplicates-count')).toHaveTextContent('3');
    expect(screen.getByTestId('drops-count')).toHaveTextContent('5');
    expect(screen.getByTestId('queue-depth')).toHaveTextContent('2');
  });

  it('renders clock skew estimate accurately', () => {
    renderStreamHealth({ metrics: sampleMetrics });

    expect(screen.getByTestId('clock-skew')).toHaveTextContent('0.032 s');
  });

  it('renders model verification metadata and hash', () => {
    renderStreamHealth({ metrics: sampleMetrics });

    expect(screen.getByText('if_v2_streaming')).toBeInTheDocument();
    expect(screen.getByText('2.1.0')).toBeInTheDocument();
    expect(
      screen.getByTestId('model-hash-verification')
    ).toHaveTextContent('9f8e7d6c5b4a3210');
  });

  it('handles edge divergence display when enabled vs disabled', () => {
    // Disabled (default)
    const { unmount } = renderStreamHealth({
      metrics: sampleMetrics,
      edgeDivergenceEnabled: false,
    });
    expect(
      screen.getByText('Disabled (Edge inference not active)')
    ).toBeInTheDocument();
    unmount();

    // Enabled
    renderStreamHealth({
      metrics: sampleMetrics,
      edgeDivergenceEnabled: true,
    });
    expect(screen.getByTestId('edge-divergence')).toHaveTextContent('0.012');
  });

  it('fetches metrics from /api/v1/metrics when no props are provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        p50_latency_ms: 12.5,
        p95_latency_ms: 28.0,
        max_latency_ms: 55.0,
        sequence_gaps: [],
        duplicates_count: 0,
        drops_count: 0,
        skew_estimate_s: 0.015,
        queue_depth: 0,
      }),
    });
    global.fetch = fetchMock;

    renderStreamHealth();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/metrics');
      expect(screen.getByTestId('p50-latency')).toHaveTextContent('12.5 ms');
      expect(screen.getByTestId('p95-latency')).toHaveTextContent('28.0 ms');
      expect(screen.getByTestId('max-latency')).toHaveTextContent('55.0 ms');
    });

    // Test refresh button
    const refreshBtn = screen.getByTestId('refresh-metrics-button');
    fireEvent.click(refreshBtn);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  it('formatMetricNum helper correctly formats numbers and handles nulls', () => {
    expect(formatMetricNum(null)).toBe('—');
    expect(formatMetricNum(undefined)).toBe('—');
    expect(formatMetricNum(NaN)).toBe('—');
    expect(formatMetricNum(12.345, 'ms', 1)).toBe('12.3 ms');
    expect(formatMetricNum(0.0456, 's', 3)).toBe('0.046 s');
  });
});
