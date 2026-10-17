import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Overview, formatVal, calcDelta } from './Overview';
import { EventRecord } from '../types/contracts';

describe('Overview Component (T16-009)', () => {
  it('renders clean empty state when currentSample is null or undefined', () => {
    render(<Overview currentSample={null} />);
    expect(screen.getByTestId('overview-empty-state')).toBeInTheDocument();
    expect(
      screen.getByText('No sample selected at current replay position.')
    ).toBeInTheDocument();
  });

  it('renders normal operating conditions when sample is normal', () => {
    const normalSample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: true,
      ss_rsrp: -85.4,
      ss_rsrq: -11.2,
      ss_sinr: 15.6,
      pci: 42,
      nci: 1234567,
      nrarfcn: 632000,
      is_anom: 0,
      anomaly_type: 'NORMAL',
      severity: 'LOW',
      if_score: 0.32,
      baseline_z_max: 0.85,
      baseline_flag: 0,
      if_flag: 0,
      timestamp: '2024-05-01 10:00:00',
    };

    render(<Overview currentSample={normalSample} />);

    expect(screen.getByText('✅ NORMAL OPERATING CONDITIONS')).toBeInTheDocument();
    expect(screen.getByText('Status: OK')).toBeInTheDocument();
    expect(screen.getByText('-85.4 dBm')).toBeInTheDocument();
    expect(screen.getByText('-11.2 dB')).toBeInTheDocument();
    expect(screen.getByText('15.6 dB')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('1234567')).toBeInTheDocument();
    expect(screen.getByText('632000')).toBeInTheDocument();
    expect(screen.getByText('NSA')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('0.320')).toBeInTheDocument();
    expect(
      screen.getByText('Normal network operating conditions. No active anomaly event.')
    ).toBeInTheDocument();
  });

  it('renders anomaly status banner and severity badge correctly', () => {
    const anomalySample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: 1,
      ss_rsrp: -128.0,
      ss_rsrq: -22.5,
      ss_sinr: -5.0,
      pci: 101,
      nci: 9876543,
      nrarfcn: 632000,
      is_anom: 1,
      anomaly_type: 'COVERAGE_HOLE',
      severity: 'HIGH',
      if_score: 0.785,
      baseline_z_max: 3.45,
      baseline_flag: 1,
      if_flag: 1,
      timestamp: '2024-05-01 10:05:00',
    };

    render(<Overview currentSample={anomalySample} />);

    expect(screen.getByText('⚠️ ANOMALY DETECTED')).toBeInTheDocument();
    expect(screen.getByText('Severity: HIGH')).toBeInTheDocument();
    expect(screen.getByText('COVERAGE_HOLE')).toBeInTheDocument();
  });

  it('renders UNKNOWN deployment mode verbatim as required', () => {
    const sampleUnknownDep = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'UNKNOWN',
      registered: false,
      ss_rsrp: -95.0,
      is_anom: 0,
      anomaly_type: 'NORMAL',
    };

    render(<Overview currentSample={sampleUnknownDep} />);

    expect(
      screen.getByText('Unknown (not exposed by this device)')
    ).toBeInTheDocument();
    expect(screen.getByText('No')).toBeInTheDocument();
  });

  it('displays "—" for missing/null/NA/2147483647 values and NEVER 0', () => {
    const missingSample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: null,
      ss_rsrp: 2147483647,
      ss_rsrq: 'NA',
      ss_sinr: null,
      pci: undefined,
      nci: 'nan',
      nrarfcn: '<NA>',
      is_anom: 0,
      anomaly_type: 'NORMAL',
      if_score: null,
      baseline_z_max: null,
    };

    render(<Overview currentSample={missingSample} />);

    // None of the missing fields should be 0 or 0.0
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(6);
    expect(screen.queryByText('0 dBm')).toBeNull();
    expect(screen.queryByText('0.0 dBm')).toBeNull();
    expect(screen.getByText(/N\/A \(Ineligible\)/)).toBeInTheDocument();
  });

  it('calculates deltas correctly with + and - signs', () => {
    const prevSample = {
      ss_rsrp: -90.0,
      ss_rsrq: -10.0,
      ss_sinr: 10.0,
    };
    const currentSample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: true,
      ss_rsrp: -85.5, // diff: +4.5
      ss_rsrq: -12.5, // diff: -2.5
      ss_sinr: 10.0,  // diff: +0.0
      pci: 42,
      nci: 1234567,
      nrarfcn: 632000,
      is_anom: 0,
      anomaly_type: 'NORMAL',
    };

    render(<Overview currentSample={currentSample} prevSample={prevSample} />);

    expect(screen.getByText('+4.5')).toBeInTheDocument();
    expect(screen.getByText('-2.5')).toBeInTheDocument();
    expect(screen.getByText('+0.0')).toBeInTheDocument();
  });

  it('displays ML-only statistical warning banner when type is STATISTICAL_ONLY', () => {
    const statSample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: true,
      ss_rsrp: -90.0,
      is_anom: 1,
      anomaly_type: 'STATISTICAL_ONLY',
      severity: 'LOW',
      if_score: 0.65,
    };

    render(<Overview currentSample={statSample} />);

    expect(
      screen.getByText('ML-Only Statistical Flag (No Domain Rule Corroboration)')
    ).toBeInTheDocument();
  });

  it('matches and displays event diagnosis, evidence list, and recommendation', () => {
    const currentSample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: true,
      timestamp: '2024-05-01 10:15:30',
      is_anom: 1,
      anomaly_type: 'COVERAGE_HOLE',
      severity: 'HIGH',
      ss_rsrp: -125.0,
    };

    const mockEvent: EventRecord = {
      event_id: 'EVT-001',
      session_id: 'session-1',
      anomaly_type: 'COVERAGE_HOLE',
      max_severity: 'HIGH',
      start: '2024-05-01 10:15:00',
      end: '2024-05-01 10:16:00',
      sample_count: 30,
      ml: {},
      signal: {},
      cell: {},
      network: {},
      status: 'FINAL',
      diagnosis: {
        summary: 'Severe coverage attenuation detected with RSRP < -120 dBm.',
        evidence: [
          'SS-RSRP dropped below -120 dBm for 60 consecutive seconds',
          'SS-SINR degraded to -6 dB',
        ],
      },
      recommendation: {
        kind: 'RAN_EXPANSION',
        text: 'Consider adding small cell coverage in this sector.',
      },
    };

    render(<Overview currentSample={currentSample} events={[mockEvent]} />);

    expect(
      screen.getByText('Severe coverage attenuation detected with RSRP < -120 dBm.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('SS-RSRP dropped below -120 dBm for 60 consecutive seconds')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Consider adding small cell coverage in this sector.')
    ).toBeInTheDocument();
  });

  it('helper functions formatVal and calcDelta behave accurately', () => {
    expect(formatVal(null)).toBe('—');
    expect(formatVal(undefined)).toBe('—');
    expect(formatVal(2147483647)).toBe('—');
    expect(formatVal('2147483647')).toBe('—');
    expect(formatVal('NA')).toBe('—');
    expect(formatVal('<NA>')).toBe('—');
    expect(formatVal(NaN)).toBe('—');
    expect(formatVal(-85.456, 'dBm', 1)).toBe('-85.5 dBm');
    expect(formatVal(42, '', 0)).toBe('42');

    expect(calcDelta(null, -80)).toBeNull();
    expect(calcDelta(-80, null)).toBeNull();
    expect(calcDelta(2147483647, -80)).toBeNull();
    expect(calcDelta(-80, 2147483647)).toBeNull();
    expect(calcDelta(-75, -80, 1)).toBe('+5.0');
    expect(calcDelta(-85, -80, 1)).toBe('-5.0');
  });
});
