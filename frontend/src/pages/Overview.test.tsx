import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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

  describe('Live Overview Extensions (T17-003)', () => {
    const baseSample = {
      device: 'Pixel 7',
      operator: 'Jio',
      network_type: '5G_NSA',
      deployment_mode: 'NSA',
      registered: true,
      ss_rsrp: -85.0,
      ss_rsrq: -11.0,
      ss_sinr: 15.0,
      pci: 42,
      nci: 1234567,
      nrarfcn: 632000,
      is_anom: 0,
      anomaly_type: 'NORMAL',
      timestamp: '2024-05-01 10:00:00',
    };

    it('renders all six connection states correctly from mock data', () => {
      // 1. WAITING (without sample)
      const { unmount: u1 } = render(
        <Overview currentSample={null} connectionState="WAITING" />
      );
      expect(screen.getByTestId('overview-waiting-state')).toBeInTheDocument();
      expect(screen.getByText('Waiting for Initial Phone Stream')).toBeInTheDocument();
      u1();

      // 2. DISCONNECTED (without sample)
      const { unmount: u2 } = render(
        <Overview currentSample={null} connectionState="DISCONNECTED" />
      );
      expect(screen.getByTestId('overview-disconnected-state')).toBeInTheDocument();
      expect(screen.getByText('Disconnected from Telemetry Server')).toBeInTheDocument();
      u2();

      // 3. RECONNECTING (with sample)
      const { unmount: u3 } = render(
        <Overview currentSample={baseSample} connectionState="RECONNECTING" />
      );
      expect(screen.getByTestId('reconnecting-banner')).toBeInTheDocument();
      expect(
        screen.getByText(/Reconnecting to live telemetry stream/i)
      ).toBeInTheDocument();
      u3();

      // 4. STALE (with sample)
      const { unmount: u4 } = render(
        <Overview
          currentSample={baseSample}
          connectionState="STALE"
          sampleAgeText="45s ago"
        />
      );
      expect(screen.getByTestId('stale-banner')).toBeInTheDocument();
      expect(
        screen.getByText(/STALE: Showing last known values/i)
      ).toBeInTheDocument();
      expect(screen.getByText('(last known)')).toBeInTheDocument();
      u4();

      // 5. LIVE (with sample)
      const { unmount: u5 } = render(
        <Overview currentSample={baseSample} connectionState="LIVE" />
      );
      expect(screen.getByText('Phone live stream')).toBeInTheDocument();
      u5();

      // 6. REPLAY-SOURCE (with sample)
      const { unmount: u6 } = render(
        <Overview currentSample={baseSample} connectionState="REPLAY-SOURCE" />
      );
      expect(screen.getByText('Replay / Demo')).toBeInTheDocument();
      u6();
    });

    it('makes provisional and final events visibly and textually distinct', () => {
      const provSample = {
        ...baseSample,
        is_anom: 1,
        anomaly_type: 'SIGNAL_DEGRADATION',
        severity: 'HIGH',
        event_status: 'PROVISIONAL',
        timestamp: '2024-05-01 10:10:00',
      };

      const provEvent: EventRecord = {
        event_id: 'EVT-PROV',
        session_id: 'session-1',
        anomaly_type: 'SIGNAL_DEGRADATION',
        max_severity: 'HIGH',
        start: '2024-05-01 10:09:00',
        end: '2024-05-01 10:11:00',
        sample_count: 20,
        ml: {},
        signal: {},
        cell: {},
        network: {},
        status: 'PROVISIONAL',
        diagnosis: {
          summary: 'Degradation developing across active cell sector.',
        },
        recommendation: {
          kind: 'MONITORING',
          text: 'Monitor signal recovery in next window.',
        },
      };

      const { unmount } = render(
        <Overview currentSample={provSample} events={[provEvent]} />
      );

      // Verify PROVISIONAL badge and prefix
      expect(screen.getByTestId('provisional-badge')).toBeInTheDocument();
      expect(screen.getByText('PROVISIONAL (open)')).toBeInTheDocument();
      expect(
        screen.getByText(
          'Provisional — Degradation developing across active cell sector.'
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText('Provisional — Monitor signal recovery in next window.')
      ).toBeInTheDocument();
      unmount();

      // Now verify FINAL event
      const finalSample = {
        ...baseSample,
        is_anom: 1,
        anomaly_type: 'SIGNAL_DEGRADATION',
        severity: 'HIGH',
        event_status: 'FINAL',
        timestamp: '2024-05-01 10:10:00',
      };

      const finalEvent: EventRecord = {
        ...provEvent,
        event_id: 'EVT-FINAL',
        status: 'FINAL',
      };

      render(<Overview currentSample={finalSample} events={[finalEvent]} />);

      expect(screen.getByTestId('final-badge')).toBeInTheDocument();
      expect(screen.getByText('FINAL (closed)')).toBeInTheDocument();
      expect(
        screen.getByText('Degradation developing across active cell sector.')
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/Provisional — Degradation/)
      ).not.toBeInTheDocument();
    });

    it('renders active unacknowledged alert banner and handles acknowledge action', () => {
      let acknowledgedId = '';
      const handleAck = (id: string) => {
        acknowledgedId = id;
      };

      const alert = {
        id: 'ALT-101',
        severity: 'CRITICAL',
        summary: 'Critical coverage hole detected',
        timestamp: '10:15:00',
        acknowledged: false,
      };

      render(
        <Overview
          currentSample={baseSample}
          activeAlert={alert}
          onAcknowledgeAlert={handleAck}
        />
      );

      expect(screen.getByTestId('overview-alert-banner')).toBeInTheDocument();
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
      expect(screen.getByText('Critical coverage hole detected')).toBeInTheDocument();
      expect(
        screen.getByText(/\(10:15:00 device local time\)/)
      ).toBeInTheDocument();

      const ackBtn = screen.getByTestId('acknowledge-alert-button');
      fireEvent.click(ackBtn);

      expect(acknowledgedId).toBe('ALT-101');
      expect(screen.queryByTestId('overview-alert-banner')).not.toBeInTheDocument();
    });

    it('displays verbatim ML-only line when type is STATISTICAL_ONLY', () => {
      const mlSample = {
        ...baseSample,
        is_anom: 1,
        anomaly_type: 'STATISTICAL_ONLY',
      };

      render(<Overview currentSample={mlSample} />);

      expect(screen.getByTestId('ml-only-banner')).toBeInTheDocument();
      expect(
        screen.getByText(
          'Statistically unusual — no rule-based evidence (no alert)'
        )
      ).toBeInTheDocument();
    });

    it('labels timestamp as device local time without timezone', () => {
      render(<Overview currentSample={baseSample} />);
      expect(
        screen.getByText(/device local time, no timezone recorded/)
      ).toBeInTheDocument();
    });
  });
});
