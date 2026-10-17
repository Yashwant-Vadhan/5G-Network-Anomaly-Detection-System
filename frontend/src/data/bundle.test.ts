/**
 * Unit tests for Data layer: bundle loader, validator, and selectors (T16-008).
 */

import { describe, it, expect } from 'vitest';
import { loadAndValidateBundle } from './bundleLoader';
import {
  getDevices,
  getOperators,
  getFilteredSessions,
  getSamplesForSession,
  getEventsForSession,
  getTransitionsForSession,
  getDataQuality,
  getModelMeta,
} from './selectors';
import { DemoBundle } from '../types/contracts';

const validBundleFixture: DemoBundle = {
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
  quality: {
    clean_rows: 3,
    dropped: 0,
    total_raw: 3,
  },
  model_meta: {
    contamination: 0.05,
    model_name: 'if_v1',
  },
  sessions: [
    {
      session_id: 'samsung-1',
      device: 'Samsung Galaxy S21',
      operator: 'Jio',
      start: '2026-10-09 10:15:00',
      end: '2026-10-09 10:15:06',
      n: 3,
    },
    {
      session_id: 'redmi-1',
      device: 'Redmi 13 5G',
      operator: 'Airtel',
      start: '2026-10-09 11:00:00',
      end: '2026-10-09 11:05:00',
      n: 5,
    },
  ],
  samples: {
    columns: [
      'timestamp',
      'device',
      'operator',
      'session_id',
      'sample_idx',
      'ss_rsrp',
      'is_anom',
      'anomaly_type',
      'severity',
      'if_score',
    ],
    rows: [
      ['2026-10-09 10:15:00', 'Samsung Galaxy S21', 'Jio', 'samsung-1', 0, -95.0, false, 'NORMAL', 'NONE', 0.12],
      ['2026-10-09 10:15:03', 'Samsung Galaxy S21', 'Jio', 'samsung-1', 1, -115.0, true, 'SIGNAL_DEGRADATION', 'MEDIUM', 0.72],
      ['2026-10-09 11:00:00', 'Redmi 13 5G', 'Airtel', 'redmi-1', 0, -88.0, false, 'NORMAL', 'NONE', 0.05],
    ],
  },
  transitions: [
    {
      session_id: 'samsung-1',
      device: 'Samsung Galaxy S21',
      timestamp: '2026-10-09 10:15:03',
      sample_idx: 1,
      from_cell: 'Cell-A',
      to_cell: 'Cell-B',
      type: 'PCI',
    },
  ],
  events: [
    {
      event_id: 'e-001',
      session_id: 'samsung-1',
      anomaly_type: 'SIGNAL_DEGRADATION',
      max_severity: 'MEDIUM',
      status: 'FINAL',
      start: '2026-10-09 10:15:03',
      end: '2026-10-09 10:15:06',
    },
  ],
};

describe('Demo Bundle Loader & Validator (T16-008)', () => {
  it('successfully validates a compliant C11 demo bundle', () => {
    const result = loadAndValidateBundle(validBundleFixture);
    expect(result.error).toBeNull();
    expect(result.bundle).not.toBeNull();
    expect(result.bundle?.bundle_version).toBe(1);
    expect(result.bundle?.sessions.length).toBe(2);
  });

  it('returns readable error without stack trace when bundle is null or undefined', () => {
    const resNull = loadAndValidateBundle(null);
    expect(resNull.bundle).toBeNull();
    expect(resNull.error).toContain('missing or empty');
    expect(resNull.error).toContain('python scripts/build_demo_bundle.py');
    expect(resNull.error).not.toContain('Traceback');
    expect(resNull.error).not.toContain('at ');

    const resUndef = loadAndValidateBundle(undefined);
    expect(resUndef.bundle).toBeNull();
    expect(resUndef.error).toContain('missing or empty');
  });

  it('rejects unsupported bundle version with clear upgrade instructions', () => {
    const badVersion = { ...validBundleFixture, bundle_version: 0 };
    const res = loadAndValidateBundle(badVersion);
    expect(res.bundle).toBeNull();
    expect(res.error).toContain("Unsupported bundle version '0'");
    expect(res.error).toContain('Expected bundle_version 1');
    expect(res.error).toContain('build_demo_bundle.py');
    expect(res.error).not.toContain('Traceback');
  });

  it('reports missing required top-level key with actionable fix instruction', () => {
    const missingSessions = { ...validBundleFixture };
    delete (missingSessions as Record<string, unknown>)['sessions'];
    const res = loadAndValidateBundle(missingSessions);
    expect(res.bundle).toBeNull();
    expect(res.error).toContain("Missing required field 'sessions'");
    expect(res.error).toContain('python scripts/build_demo_bundle.py');

    const missingSamples = { ...validBundleFixture };
    delete (missingSamples as Record<string, unknown>)['samples'];
    const res2 = loadAndValidateBundle(missingSamples);
    expect(res2.bundle).toBeNull();
    expect(res2.error).toContain("Missing required field 'samples'");
  });

  it('validates samples columns and rows structure', () => {
    const brokenSamples = {
      ...validBundleFixture,
      samples: { columns: 'not-an-array', rows: [] },
    };
    const res = loadAndValidateBundle(brokenSamples);
    expect(res.bundle).toBeNull();
    expect(res.error).toContain("'samples' must contain 'columns' and 'rows' arrays");
  });
});

describe('Typed Selectors (T16-008 / Guardrail G30)', () => {
  it('getDevices returns unique sorted device list', () => {
    const devices = getDevices(validBundleFixture);
    expect(devices).toEqual(['Redmi 13 5G', 'Samsung Galaxy S21']);
  });

  it('getOperators returns unique sorted operators, optionally filtered by device', () => {
    const allOps = getOperators(validBundleFixture);
    expect(allOps).toEqual(['Airtel', 'Jio']);

    const samsungOps = getOperators(validBundleFixture, 'Samsung Galaxy S21');
    expect(samsungOps).toEqual(['Jio']);

    const redmiOps = getOperators(validBundleFixture, 'Redmi 13 5G');
    expect(redmiOps).toEqual(['Airtel']);
  });

  it('getFilteredSessions filters by device and operator', () => {
    const allSessions = getFilteredSessions(validBundleFixture);
    expect(allSessions.length).toBe(2);

    const samsungSessions = getFilteredSessions(validBundleFixture, { device: 'Samsung Galaxy S21' });
    expect(samsungSessions.length).toBe(1);
    expect(samsungSessions[0].session_id).toBe('samsung-1');

    const airtelSessions = getFilteredSessions(validBundleFixture, { operator: 'Airtel' });
    expect(airtelSessions.length).toBe(1);
    expect(airtelSessions[0].session_id).toBe('redmi-1');
  });

  it('getSamplesForSession returns parsed row objects matching session_id', () => {
    const samsungSamples = getSamplesForSession(validBundleFixture, 'samsung-1');
    expect(samsungSamples.length).toBe(2);
    expect(samsungSamples[0].timestamp).toBe('2026-10-09 10:15:00');
    expect(samsungSamples[0].ss_rsrp).toBe(-95.0);
    expect(samsungSamples[0].if_score).toBe(0.12);
    expect(samsungSamples[1].anomaly_type).toBe('SIGNAL_DEGRADATION');
    expect(samsungSamples[1].severity).toBe('MEDIUM');

    const redmiSamples = getSamplesForSession(validBundleFixture, 'redmi-1');
    expect(redmiSamples.length).toBe(1);
    expect(redmiSamples[0].device).toBe('Redmi 13 5G');
  });

  it('getEventsForSession returns precomputed event records for session', () => {
    const events = getEventsForSession(validBundleFixture, 'samsung-1');
    expect(events.length).toBe(1);
    expect(events[0].event_id).toBe('e-001');
    expect(events[0].anomaly_type).toBe('SIGNAL_DEGRADATION');

    const noEvents = getEventsForSession(validBundleFixture, 'redmi-1');
    expect(noEvents.length).toBe(0);
  });

  it('getTransitionsForSession returns precomputed transitions', () => {
    const transitions = getTransitionsForSession(validBundleFixture, 'samsung-1');
    expect(transitions.length).toBe(1);
    expect(transitions[0].from_cell).toBe('Cell-A');
    expect(transitions[0].to_cell).toBe('Cell-B');
  });

  it('getDataQuality and getModelMeta return bundle metadata directly', () => {
    const quality = getDataQuality(validBundleFixture);
    expect(quality.clean_rows).toBe(3);

    const meta = getModelMeta(validBundleFixture);
    expect(meta.model_name).toBe('if_v1');
  });

  it('enforces G30: selectors do not recompute or mutate flags or scores', () => {
    const samples = getSamplesForSession(validBundleFixture, 'samsung-1');
    // Scores and flags are strictly preserved as precomputed in bundle
    expect(samples[0].is_anom).toBe(false);
    expect(samples[1].is_anom).toBe(true);
    expect(samples[0].if_score).toBe(0.12);
    expect(samples[1].if_score).toBe(0.72);
  });
});
