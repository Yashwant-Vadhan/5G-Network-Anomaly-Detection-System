import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { HashRouter } from 'react-router-dom';
import axe from 'axe-core';
import App from './App';
import { DataProvider } from './data/DataContext';
import { ReplayProvider } from './data/ReplayContext';
import { Overview } from './pages/Overview';
import { SignalExplorer } from './pages/SignalExplorer';
import { CellsNetwork } from './pages/CellsNetwork';
import { EventsDiagnosis } from './pages/EventsDiagnosis';
import { StreamHealth } from './pages/StreamHealth';
import { DataQuality } from './pages/DataQuality';
import { About } from './pages/About';
import { ConnectionChip } from './components/ConnectionChip';
import { ReplayPlayer } from './components/ReplayPlayer';
import { DemoBundle } from './types/contracts';

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2026-10-18T10:00:00Z',
  model_version: '1.0.0',
  source: 'sample',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: 'a1b2c3d4e5f60718',
    cell_lookup: {},
  },
  quality: { clean_rows: 5, dropped: 0, total_raw: 5 },
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'session-access-1',
      device: 'Pixel 8',
      operator: 'Jio',
      start: '2026-10-18 10:00:00',
      end: '2026-10-18 10:00:15',
      n: 5,
    },
  ],
  samples: {
    columns: [
      'timestamp',
      'session_id',
      'device',
      'operator',
      'ss_rsrp',
      'ss_rsrq',
      'ss_sinr',
      'pci',
      'nci',
      'network_type',
      'if_score',
      'baseline_z_max',
      'is_anom',
      'anomaly_type',
      'severity',
    ],
    rows: [
      ['2026-10-18 10:00:00', 'session-access-1', 'Pixel 8', 'Jio', -85.0, -11.0, 15.0, 'PCI_100', 'NCI_1', '5G_SA', 0.1, 0.5, false, 'NORMAL', 'LOW'],
      ['2026-10-18 10:00:03', 'session-access-1', 'Pixel 8', 'Jio', -88.0, -12.0, 14.0, 'PCI_100', 'NCI_1', '5G_SA', 0.2, 0.7, false, 'NORMAL', 'LOW'],
      ['2026-10-18 10:00:06', 'session-access-1', 'Pixel 8', 'Jio', -115.0, -18.0, -2.0, 'PCI_100', 'NCI_1', '5G_SA', 0.85, 3.8, true, 'SIGNAL_DEGRADATION', 'HIGH'],
      ['2026-10-18 10:00:09', 'session-access-1', 'Pixel 8', 'Jio', -118.0, -19.0, -4.0, 'PCI_100', 'NCI_1', '5G_SA', 0.89, 4.2, true, 'SIGNAL_DEGRADATION', 'HIGH'],
      ['2026-10-18 10:00:12', 'session-access-1', 'Pixel 8', 'Jio', -86.0, -11.0, 16.0, 'PCI_101', 'NCI_1', '5G_SA', 0.15, 0.6, false, 'NORMAL', 'LOW'],
    ],
  },
  transitions: [
    {
      device: 'Pixel 8',
      session_id: 'session-access-1',
      sample_idx: 4,
      timestamp: '2026-10-18 10:00:12',
      kind: 'PCI_HANDOVER',
      pci_from: 100,
      pci_to: 101,
    },
  ],
  events: [
    {
      event_id: 'session-access-1-e001',
      session_id: 'session-access-1',
      start: '2026-10-18 10:00:06',
      end: '2026-10-18 10:00:09',
      duration_sec: 3.0,
      samples_count: 2,
      anomaly_type: 'SIGNAL_DEGRADATION',
      severity: 'HIGH',
      max_if_score: 0.89,
      max_baseline_z: 4.2,
      status: 'FINAL',
      diagnosis: {
        summary: 'Sudden SS-RSRP signal degradation below -115 dBm',
        primary_cause: 'Radio signal fading',
        recommendation: 'Check coverage and potential line-of-sight obstruction',
      },
    } as unknown as EventRecord,
  ],
};

// Axe runner helper: in jsdom environment, color-contrast cannot be computed, so we disable it
async function checkA11y(container: HTMLElement) {
  const results = await axe.run(container, {
    rules: {
      'color-contrast': { enabled: false }, // jsdom doesn't support layout/color calculation
    },
  });
  const seriousOrCritical = results.violations.filter(v =>
    v.impact === 'serious' || v.impact === 'critical'
  );
  return { results, seriousOrCritical };
}

describe('Accessibility Audit & Automated Axe Scan (T16-016)', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('verifies App shell has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <HashRouter>
        <App initialBundle={mockBundle} />
      </HashRouter>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies Overview page has no serious or critical accessibility violations', async () => {
    const sample = {
      timestamp: '2026-10-18 10:00:06',
      device: 'Pixel 8',
      operator: 'Jio',
      ss_rsrp: -115.0,
      ss_rsrq: -18.0,
      ss_sinr: -2.0,
      pci: 'PCI_100',
      nci: 'NCI_1',
      is_anom: true,
      anomaly_type: 'SIGNAL_DEGRADATION',
      severity: 'HIGH',
      if_score: 0.85,
      baseline_z_max: 3.8,
    };

    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <ReplayProvider>
          <Overview
            currentSample={sample}
            prevSample={null}
            events={mockBundle.events as unknown as EventRecord[]}
            connectionState="REPLAY-SOURCE"
          />
        </ReplayProvider>
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies SignalExplorer page has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <ReplayProvider>
          <SignalExplorer />
        </ReplayProvider>
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies CellsNetwork page has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <ReplayProvider>
          <CellsNetwork />
        </ReplayProvider>
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies EventsDiagnosis page has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <ReplayProvider>
          <EventsDiagnosis />
        </ReplayProvider>
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies StreamHealth page has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <StreamHealth />
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies DataQuality page has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <DataQuality />
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies About & Limitations page has no serious or critical accessibility violations', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <About />
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies ConnectionChip has accessible aria-live region and status description', async () => {
    const { container } = render(
      <ConnectionChip state="LIVE" lastSampleTime="2026-10-18T10:00:00Z" />
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });

  it('verifies ReplayPlayer component has accessible labels for all controls', async () => {
    const { container } = render(
      <DataProvider initialBundle={mockBundle}>
        <ReplayProvider>
          <ReplayPlayer />
        </ReplayProvider>
      </DataProvider>
    );

    const { seriousOrCritical } = await checkA11y(container);
    expect(seriousOrCritical).toEqual([]);
  });
});
