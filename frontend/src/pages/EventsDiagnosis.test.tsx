import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataProvider } from '../data/DataContext';
import { ReplayProvider } from '../data/ReplayContext';
import {
  EventsDiagnosis,
  ALERT_DECISION_REASONS,
  STORAGE_ACK_KEY,
} from './EventsDiagnosis';
import { DemoBundle, EventRecord, AlertRecord } from '../types/contracts';

const mockEvents: EventRecord[] = [
  {
    event_id: 'EVT-001',
    session_id: 'sess-1',
    anomaly_type: 'COVERAGE_HOLE',
    max_severity: 'HIGH',
    start: '2024-05-01 10:00:00',
    end: '2024-05-01 10:00:30',
    sample_count: 30,
    ml: {},
    signal: {
      signal_condition: 'critical_attenuation',
      evidence: ['SS-RSRP dropped below -120 dBm'],
    },
    cell: {
      cell_event: 'NONE',
      evidence: ['PCI remained stable at 42'],
    },
    network: {
      network_state: 'stable',
      deployment_mode: 'NSA',
      evidence: ['Attached to LTE anchor cell'],
    },
    diagnosis: {
      summary: 'Severe coverage hole in serving cell sector.',
      confidence_note: 'High confidence based on continuous RSRP drop.',
      evidence: ['RSRP < -120 dBm for 30s'],
    },
    recommendation: {
      kind: 'RAN_EXPANSION',
      text: 'Deploy supplementary small cell for coverage enhancement.',
    },
    status: 'FINAL',
  },
  {
    event_id: 'EVT-002',
    session_id: 'sess-1',
    anomaly_type: 'INTERFERENCE',
    max_severity: 'LOW',
    start: '2024-05-01 10:05:00',
    end: '2024-05-01 10:05:15',
    sample_count: 15,
    ml: {},
    signal: {
      signal_condition: 'sinr_degradation',
      evidence: ['SS-SINR dropped to -6 dB'],
    },
    cell: {
      cell_event: 'RAPID_PING_PONG',
      evidence: ['Frequent switching between PCI 42 and 43'],
    },
    network: {
      network_state: 'transition',
      deployment_mode: 'NSA',
      evidence: ['Frequent handover events'],
    },
    diagnosis: {
      summary: 'Inter-cell interference leading to ping-pong handover.',
      confidence_note: 'Moderate confidence.',
      evidence: ['SINR < 0 dB alongside rapid PCI change'],
    },
    recommendation: {
      kind: 'PARAMETER_TUNING',
      text: 'Adjust handover hysteresis margins.',
    },
    status: 'FINAL',
  },
];

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
  quality: { clean_rows: 2, dropped: 0, total_raw: 2 },
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'sess-1',
      device: 'Pixel 7',
      operator: 'Jio',
      start: '2024-05-01 10:00:00',
      end: '2024-05-01 10:10:00',
      n: 2,
    },
  ],
  samples: {
    columns: ['timestamp', 'session_id', 'ss_rsrp'],
    rows: [
      ['2024-05-01 10:00:15', 'sess-1', -125.0],
      ['2024-05-01 10:05:10', 'sess-1', -90.0],
    ],
  },
  events: mockEvents,
  transitions: [],
};

function renderEventsDiagnosis(customEvents?: EventRecord[]) {
  return render(
    <DataProvider initialBundle={mockBundle}>
      <ReplayProvider>
        <EventsDiagnosis events={customEvents} />
      </ReplayProvider>
    </DataProvider>
  );
}

describe('Events & Diagnosis Component (T16-013)', () => {
  beforeEach(() => {
    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:http://localhost/mock-blob-uuid');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders events list with time note and agent cards', () => {
    renderEventsDiagnosis();

    expect(screen.getByTestId('events-diagnosis-page')).toBeInTheDocument();
    expect(screen.getByText(/Events List \(2 matched\)/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Timestamps show device local time \(no timezone recorded\)/i)
    ).toBeInTheDocument();

    // Table rows
    expect(screen.getByTestId('event-row-EVT-001')).toBeInTheDocument();
    expect(screen.getByTestId('event-row-EVT-002')).toBeInTheDocument();

    // Agent cards for default selected first event (EVT-001)
    expect(screen.getByTestId('agent-card-signal')).toBeInTheDocument();
    expect(screen.getByTestId('agent-card-cell')).toBeInTheDocument();
    expect(screen.getByTestId('agent-card-network')).toBeInTheDocument();
    expect(screen.getByTestId('agent-card-diagnosis')).toBeInTheDocument();
    expect(screen.getByTestId('agent-card-recommendation')).toBeInTheDocument();

    // Content of EVT-001
    expect(screen.getByText('critical_attenuation')).toBeInTheDocument();
    expect(screen.getByText('SS-RSRP dropped below -120 dBm')).toBeInTheDocument();
    expect(
      screen.getByText('Severe coverage hole in serving cell sector.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Deploy supplementary small cell for coverage enhancement.')
    ).toBeInTheDocument();
  });

  it('filters events by type and severity accurately matching counts', () => {
    renderEventsDiagnosis();

    const typeSelect = screen.getByLabelText(/Filter by Anomaly Type/i);
    const sevSelect = screen.getByLabelText(/Filter by Severity/i);

    // Filter by type: COVERAGE_HOLE
    fireEvent.change(typeSelect, { target: { value: 'COVERAGE_HOLE' } });
    expect(screen.getByText(/Events List \(1 matched\)/i)).toBeInTheDocument();
    expect(screen.getByTestId('event-row-EVT-001')).toBeInTheDocument();
    expect(screen.queryByTestId('event-row-EVT-002')).toBeNull();

    // Reset type, filter by severity: LOW
    fireEvent.change(typeSelect, { target: { value: 'all' } });
    fireEvent.change(sevSelect, { target: { value: 'LOW' } });
    expect(screen.getByText(/Events List \(1 matched\)/i)).toBeInTheDocument();
    expect(screen.getByTestId('event-row-EVT-002')).toBeInTheDocument();
    expect(screen.queryByTestId('event-row-EVT-001')).toBeNull();

    // Filter combination yielding 0 matches
    fireEvent.change(typeSelect, { target: { value: 'COVERAGE_HOLE' } });
    fireEvent.change(sevSelect, { target: { value: 'LOW' } });
    expect(screen.getByText(/Events List \(0 matched\)/i)).toBeInTheDocument();
    expect(screen.getByText('No events match the selected filters.')).toBeInTheDocument();
  });

  it('updates selected event when a table row is clicked', () => {
    renderEventsDiagnosis();

    // Initially EVT-001 is active
    expect(screen.getByText('critical_attenuation')).toBeInTheDocument();

    // Click on EVT-002 row
    fireEvent.click(screen.getByTestId('event-row-EVT-002'));

    // Agent cards now show EVT-002 details
    expect(screen.getByText('sinr_degradation')).toBeInTheDocument();
    expect(screen.getByText('RAPID_PING_PONG')).toBeInTheDocument();
    expect(
      screen.getByText('Inter-cell interference leading to ping-pong handover.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Adjust handover hysteresis margins.')
    ).toBeInTheDocument();
  });

  it('provides JSON download button linking to valid C5 event JSON blob', () => {
    renderEventsDiagnosis();

    const downloadLink = screen.getByTestId('download-json-button');
    expect(downloadLink).toBeInTheDocument();
    expect(downloadLink).toHaveAttribute('download', 'EVT-001_diagnosed.json');
    expect(downloadLink).toHaveAttribute('href', 'blob:http://localhost/mock-blob-uuid');
    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  it('stays responsive with 1,000 rows', () => {
    // Generate 1,000 mock events
    const largeEvents: EventRecord[] = Array.from({ length: 1000 }, (_, i) => ({
      event_id: `EVT-${String(i).padStart(4, '0')}`,
      session_id: `sess-${i % 10}`,
      anomaly_type: i % 2 === 0 ? 'COVERAGE_HOLE' : 'INTERFERENCE',
      max_severity: i % 3 === 0 ? 'HIGH' : 'LOW',
      start: `2024-05-01 10:00:${String(i % 60).padStart(2, '0')}`,
      end: `2024-05-01 10:01:${String(i % 60).padStart(2, '0')}`,
      sample_count: 10,
      ml: {},
      signal: { signal_condition: 'nominal', evidence: [] },
      cell: { cell_event: 'NONE', evidence: [] },
      network: { network_state: 'stable', deployment_mode: 'NSA', evidence: [] },
      diagnosis: { summary: `Diagnosis summary ${i}`, evidence: [] },
      recommendation: { kind: 'MONITORING', text: `Recommendation ${i}` },
      status: 'FINAL',
    }));

    const start = performance.now();
    renderEventsDiagnosis(largeEvents);
    const renderDuration = performance.now() - start;

    expect(screen.getByText(/Events List \(1000 matched\)/i)).toBeInTheDocument();
    expect(screen.getByTestId('events-table-container')).toBeInTheDocument();
    // Rendering 1,000 rows should complete quickly (< 1500ms)
    expect(renderDuration).toBeLessThan(1500);
  });

  describe('Live Events & Alerts Extensions (T17-006)', () => {
    beforeEach(() => {
      localStorage.clear();
    });

    it('renders events with status and the five fixed reason strings', () => {
      // Create events for all 5 fixed reasons
      const eventsWithReasons: EventRecord[] = ALERT_DECISION_REASONS.map((reason, idx) => ({
        event_id: `EVT-REASON-${idx}`,
        session_id: 'sess-live',
        anomaly_type: idx === 1 ? 'STATISTICAL_ONLY' : 'COVERAGE_HOLE',
        max_severity: 'HIGH',
        start: `2024-05-01 10:0${idx}:00`,
        end: `2024-05-01 10:0${idx}:30`,
        sample_count: 10,
        ml: {},
        signal: {},
        cell: {},
        network: {},
        diagnosis: { summary: `Diagnosis for ${reason}` },
        recommendation: { kind: 'MONITORING', text: 'Action' },
        status: idx % 2 === 0 ? 'PROVISIONAL' : 'FINAL',
        alert_decision: {
          alerted: idx === 0, // only the first is alerted
          reason: reason,
        },
      }));

      renderEventsDiagnosis(eventsWithReasons);

      // Verify each of the 5 fixed reasons is rendered
      expect(screen.getByText('Yes — Alert triggered')).toBeInTheDocument();
      expect(
        screen.getByText('No — ML-only (no rule evidence)')
      ).toBeInTheDocument();
      expect(screen.getByText('No — Transition only')).toBeInTheDocument();
      expect(
        screen.getByText('No — Below persistence/severity threshold')
      ).toBeInTheDocument();
      expect(screen.getByText('No — Cooldown active')).toBeInTheDocument();

      // Verify PROVISIONAL and FINAL badges
      expect(
        screen.getByTestId('event-status-EVT-REASON-0')
      ).toHaveTextContent('PROVISIONAL');
      expect(
        screen.getByTestId('event-status-EVT-REASON-1')
      ).toHaveTextContent('FINAL');
    });

    it('persists alert acknowledgement across page reloads via localStorage and API', async () => {
      let ackApiCalledWith = '';
      const handleAck = vi.fn((alertId: string) => {
        ackApiCalledWith = alertId;
      });

      const mockAlert: AlertRecord = {
        alert_id: 'ALT-LIVE-001',
        created_at: '2024-05-01 10:00:00',
        event_id: 'EVT-001',
        session_id: 'sess-1',
        source: 'server',
        kind: 'NEW',
        severity: 'CRITICAL',
        anomaly_type: 'COVERAGE_HOLE',
        event_status: 'FINAL',
        title: 'Severe Coverage Hole Alert',
        body: 'Cell RSRP dropped below threshold',
        evidence: [],
        recommendation: {},
        policy: {},
        delivery: [
          { channel: 'webhook', status: 'SENT' },
          { channel: 'email', status: 'SENT' },
          { channel: 'phone', status: 'SKIPPED' },
        ],
      };

      // 1. Initial Render: Alert is unacknowledged
      const { unmount } = render(
        <DataProvider initialBundle={mockBundle}>
          <ReplayProvider>
            <EventsDiagnosis
              events={mockEvents}
              alerts={[mockAlert]}
              onAcknowledgeAlert={handleAck}
            />
          </ReplayProvider>
        </DataProvider>
      );

      const ackBtn = screen.getByTestId('ack-button-ALT-LIVE-001');
      expect(ackBtn).toBeInTheDocument();
      expect(
        screen.queryByTestId('acked-badge-ALT-LIVE-001')
      ).not.toBeInTheDocument();

      // 2. Click Acknowledge
      fireEvent.click(ackBtn);

      expect(handleAck).toHaveBeenCalledWith('ALT-LIVE-001');
      expect(ackApiCalledWith).toBe('ALT-LIVE-001');
      expect(
        screen.getByTestId('acked-badge-ALT-LIVE-001')
      ).toBeInTheDocument();

      // Verify localStorage was updated
      const rawStored = localStorage.getItem(STORAGE_ACK_KEY);
      expect(rawStored).toBeTruthy();
      expect(JSON.parse(rawStored!)).toContain('ALT-LIVE-001');

      // 3. Simulate Page Reload (unmount and remount fresh)
      unmount();

      render(
        <DataProvider initialBundle={mockBundle}>
          <ReplayProvider>
            <EventsDiagnosis
              events={mockEvents}
              alerts={[mockAlert]}
              onAcknowledgeAlert={handleAck}
            />
          </ReplayProvider>
        </DataProvider>
      );

      // On reload, acknowledgement immediately persists without user intervention
      expect(
        screen.getByTestId('acked-badge-ALT-LIVE-001')
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId('ack-button-ALT-LIVE-001')
      ).not.toBeInTheDocument();
    });

    it('renders multi-channel delivery status for live alerts', () => {
      const mockAlertWithChannels: AlertRecord = {
        alert_id: 'ALT-CHANNELS-001',
        created_at: '2024-05-01 10:00:00',
        event_id: 'EVT-001',
        session_id: 'sess-1',
        source: 'server',
        kind: 'NEW',
        severity: 'HIGH',
        anomaly_type: 'COVERAGE_HOLE',
        event_status: 'FINAL',
        title: 'Multi-Channel Alert',
        body: 'Details',
        evidence: [],
        recommendation: {},
        policy: {},
        delivery: [
          { channel: 'webhook', status: 'SENT' },
          { channel: 'email', status: 'SENT' },
          { channel: 'phone', status: 'SKIPPED' },
        ],
      };

      render(
        <DataProvider initialBundle={mockBundle}>
          <ReplayProvider>
            <EventsDiagnosis alerts={[mockAlertWithChannels]} />
          </ReplayProvider>
        </DataProvider>
      );

      expect(screen.getByTestId('channel-webhook')).toHaveTextContent('webhook: SENT');
      expect(screen.getByTestId('channel-email')).toHaveTextContent('email: SENT');
      expect(screen.getByTestId('channel-phone')).toHaveTextContent('phone: SKIPPED');
    });
  });
});
