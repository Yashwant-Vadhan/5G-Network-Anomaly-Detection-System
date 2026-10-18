import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DataProvider } from '../data/DataContext';
import { DataQuality } from './DataQuality';
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
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'sess-redmi-1',
      device: 'Redmi 13 5G',
      operator: 'Airtel',
      start: '2026-10-18 10:00:00',
      end: '2026-10-18 10:30:00',
      n: 3756,
    },
    {
      session_id: 'sess-samsung-1',
      device: 'Samsung Galaxy A15 5G',
      operator: 'Airtel',
      start: '2026-10-18 11:00:00',
      end: '2026-10-18 11:30:00',
      n: 1772,
    },
  ],
  samples: {
    columns: [
      'timestamp',
      'device',
      'operator',
      'network_type',
      'deployment_mode',
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
      'session_id',
      'sample_idx',
      'is_anom',
      'anomaly_type',
      'severity',
      'baseline_flag',
      'if_flag',
      'if_score',
      'is_synthetic',
    ],
    rows: [
      [
        '2026-10-18 10:00:00',
        'Redmi 13 5G',
        'Airtel',
        'LTE',
        'UNKNOWN',
        true,
        -95.0,
        -11.0,
        5.0,
        null,
        null,
        null,
        42,
        1234567,
        632000,
        'sess-redmi-1',
        0,
        false,
        'NORMAL',
        'NONE',
        false,
        false,
        0.35,
        false,
      ],
      [
        '2026-10-18 10:00:01',
        'Redmi 13 5G',
        'Airtel',
        'LTE',
        'UNKNOWN',
        true,
        null,
        -12.0,
        4.0,
        null,
        null,
        null,
        42,
        1234567,
        632000,
        'sess-redmi-1',
        1,
        false,
        'NORMAL',
        'NONE',
        false,
        false,
        0.38,
        false,
      ],
      [
        '2026-10-18 11:00:00',
        'Samsung Galaxy A15 5G',
        'Airtel',
        'NR',
        'NSA',
        true,
        -88.0,
        -9.0,
        12.0,
        -90.0,
        -10.0,
        11.0,
        108,
        9876543,
        633000,
        'sess-samsung-1',
        0,
        false,
        'NORMAL',
        'NONE',
        false,
        false,
        0.28,
        false,
      ],
    ],
  },
  transitions: [],
  events: [],
};

describe('DataQuality Component (T16-014)', () => {
  it('renders page header and descriptive caption', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    expect(screen.getByRole('heading', { level: 1, name: /6\. Data Quality/i })).toBeDefined();
    expect(screen.getByText(/Inspect missing metrics, device quirks/i)).toBeDefined();
  });

  it('renders verbatim UNKNOWN copy rule note (Acceptance Criteria)', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    // Exact copy rule string from DESIGN.md / PRD.md / Acceptance Criteria
    const rulePattern =
      /UNKNOWN means Android did not expose enough information\. It does not mean SA\./i;
    expect(screen.getByText(rulePattern)).toBeDefined();
  });

  it('renders preprocessing audit log metrics correctly', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    expect(screen.getByText(/Raw Rows Loaded/i)).toBeDefined();
    expect(screen.getByText('5,532')).toBeDefined();
    expect(screen.getByText(/Valid Rows Kept/i)).toBeDefined();
    expect(screen.getByText('5,528')).toBeDefined();
    expect(screen.getByText(/Invalid Rows Dropped/i)).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();
  });

  it('renders missing value table with calculated metrics per device', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Missing value counts table/i })).toBeDefined();
    // Verify devices appear in the tables
    expect(screen.getAllByText('Redmi 13 5G').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Samsung Galaxy A15 5G').length).toBeGreaterThanOrEqual(1);

    // In mock data: Redmi has 1 missing ss_rsrp out of 2 samples (50.0%)
    expect(screen.getByText('1 (50.0%)')).toBeDefined();
  });

  it('renders CSI signal availability breakdown for each device', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /CSI availability breakdown/i })).toBeDefined();
    // Redmi has 0% CSI availability in mock data
    expect(screen.getByText('0.0%')).toBeDefined();
    // Samsung has 100% CSI availability in mock data
    expect(screen.getByText('100.0%')).toBeDefined();
  });

  it('renders deployment mode distribution with UNKNOWN and NSA columns', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    expect(screen.getByRole('region', { name: /Deployment mode distribution/i })).toBeDefined();
    expect(screen.getByRole('columnheader', { name: 'NSA' })).toBeDefined();
    expect(screen.getByRole('columnheader', { name: 'SA' })).toBeDefined();
    expect(screen.getByRole('columnheader', { name: 'UNKNOWN' })).toBeDefined();
  });

  it('displays synthetic data banner when synthetic rows are present', () => {
    const syntheticSamples = [
      {
        device: 'Pixel 8',
        ss_rsrp: -100.0,
        is_synthetic: true,
      },
    ];

    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality samplesOverride={syntheticSamples} />
      </DataProvider>
    );

    expect(screen.getByRole('alert')).toBeDefined();
    expect(screen.getByText(/Synthetic Data Banner/i)).toBeDefined();
    expect(screen.getByText(/is_synthetic = True/i)).toBeDefined();
  });

  it('does not display synthetic data banner when no synthetic rows exist', () => {
    render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    expect(screen.queryByRole('alert')).toBeNull();
  });
});
