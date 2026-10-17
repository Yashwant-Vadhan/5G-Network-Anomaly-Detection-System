/**
 * Events & Diagnosis Page Component (T16-013).
 *
 * Implements:
 * - High-performance virtualized/scrollable events table (handling 1,000+ rows)
 * - Filter controls by anomaly type and severity
 * - Multi-agent structured reports (Signal, Cell, Network, Diagnosis, Recommendation)
 * - Event window telemetry visualization
 * - JSON download matching Contract C5 shape
 * - Time labeled: 'device local time (no timezone recorded)'
 */

import React, { useState, useMemo } from 'react';
import { useData } from '../data/useData';
import { EventRecord } from '../types/contracts';

export interface EventsDiagnosisProps {
  events?: EventRecord[];
}

export const EventsDiagnosis: React.FC<EventsDiagnosisProps> = ({ events: propEvents }) => {
  const { events: contextEvents, samples } = useData();
  const allEvents = propEvents || contextEvents || [];

  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [sevFilter, setSevFilter] = useState<string>('all');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  // Collect distinct anomaly types and severities
  const anomalyTypes = useMemo(() => {
    const set = new Set<string>();
    for (const e of allEvents) {
      if (e.anomaly_type) set.add(String(e.anomaly_type));
    }
    return Array.from(set).sort();
  }, [allEvents]);

  const severities = useMemo(() => {
    const set = new Set<string>();
    for (const e of allEvents) {
      const raw = e as unknown as Record<string, unknown>;
      const s = raw.severity || e.max_severity;
      if (s) set.add(String(s));
    }
    return Array.from(set).sort();
  }, [allEvents]);

  // Filter events
  const filteredEvents = useMemo(() => {
    return allEvents.filter(e => {
      if (typeFilter !== 'all' && String(e.anomaly_type) !== typeFilter) {
        return false;
      }
      const raw = e as unknown as Record<string, unknown>;
      const s = String(raw.severity || e.max_severity || '');
      if (sevFilter !== 'all' && s !== sevFilter) {
        return false;
      }
      return true;
    });
  }, [allEvents, typeFilter, sevFilter]);

  // Ensure an active event is selected
  const activeEvent = useMemo(() => {
    if (filteredEvents.length === 0) return null;
    if (selectedEventId) {
      const match = filteredEvents.find(e => e.event_id === selectedEventId);
      if (match) return match;
    }
    return filteredEvents[0];
  }, [filteredEvents, selectedEventId]);

  // JSON Download URL for active event
  const downloadUrl = useMemo(() => {
    if (!activeEvent) return null;
    const jsonStr = JSON.stringify(activeEvent, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    return URL.createObjectURL(blob);
  }, [activeEvent]);

  // Extract agent reports safely
  const rawEvt = (activeEvent as unknown as Record<string, unknown>) || {};
  const sigReport =
    (rawEvt.signal_report as Record<string, unknown>) ||
    (rawEvt.signal as Record<string, unknown>) ||
    {};
  const cellReport =
    (rawEvt.cell_report as Record<string, unknown>) ||
    (rawEvt.cell as Record<string, unknown>) ||
    {};
  const netReport =
    (rawEvt.network_report as Record<string, unknown>) ||
    (rawEvt.network as Record<string, unknown>) ||
    {};
  const diagData =
    (rawEvt.diagnosis as Record<string, unknown>) || {};
  const recData =
    (rawEvt.recommendation as Record<string, unknown>) || {};

  // Event window sample points for chart
  const eventWindowSamples = useMemo(() => {
    if (!activeEvent || samples.length === 0) return [];
    const raw = activeEvent as unknown as Record<string, unknown>;
    const startTs = String(activeEvent.start || raw.start_time);
    const endTs = String(activeEvent.end || raw.end_time);

    return samples.map((s, idx) => {
      const ts = String(s.timestamp || '');
      const rawRsrp = s.ss_rsrp;
      let val: number | null = null;
      if (
        rawRsrp !== null &&
        rawRsrp !== undefined &&
        rawRsrp !== 2147483647 &&
        !isNaN(Number(rawRsrp))
      ) {
        val = Number(rawRsrp);
      }
      const inSpan = startTs <= ts && ts <= endTs;
      return { idx, ts, val, inSpan };
    });
  }, [activeEvent, samples]);

  return (
    <div
      data-testid="events-diagnosis-page"
      style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
    >
      {/* Header & Filter Controls */}
      <section
        style={{
          background: 'var(--color-surface)',
          padding: '16px 20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>
              Events List ({filteredEvents.length} matched)
            </h2>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              Timestamps show device local time (no timezone recorded)
            </div>
          </div>

          {/* Filters */}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <label
                htmlFor="filter-type"
                style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}
              >
                Type:
              </label>
              <select
                id="filter-type"
                aria-label="Filter by Anomaly Type"
                value={typeFilter}
                onChange={e => setTypeFilter(e.target.value)}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-bg)',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                }}
              >
                <option value="all">All Types</option>
                {anomalyTypes.map(t => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <label
                htmlFor="filter-sev"
                style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}
              >
                Severity:
              </label>
              <select
                id="filter-sev"
                aria-label="Filter by Severity"
                value={sevFilter}
                onChange={e => setSevFilter(e.target.value)}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-bg)',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                }}
              >
                <option value="all">All Severities</option>
                {severities.map(s => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* High-Performance Virtualized/Scrollable Events Table */}
        <div
          data-testid="events-table-container"
          style={{
            maxHeight: '300px',
            overflowY: 'auto',
            border: '1px solid var(--color-border)',
            borderRadius: '6px',
          }}
        >
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '12px',
              textAlign: 'left',
            }}
          >
            <thead style={{ background: 'var(--color-bg)', position: 'sticky', top: 0 }}>
              <tr>
                <th style={{ padding: '8px 12px' }}>Event ID</th>
                <th style={{ padding: '8px 12px' }}>Session</th>
                <th style={{ padding: '8px 12px' }}>Type</th>
                <th style={{ padding: '8px 12px' }}>Severity</th>
                <th style={{ padding: '8px 12px' }}>Start Time</th>
                <th style={{ padding: '8px 12px' }}>End Time</th>
                <th style={{ padding: '8px 12px' }}>Samples</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '24px', textAlign: 'center' }}>
                    No events match the selected filters.
                  </td>
                </tr>
              ) : (
                filteredEvents.map(evt => {
                  const isSelected = activeEvent?.event_id === evt.event_id;
                  const raw = evt as unknown as Record<string, unknown>;
                  const sev = String(raw.severity || evt.max_severity || 'LOW');
                  return (
                    <tr
                      key={evt.event_id}
                      onClick={() => setSelectedEventId(evt.event_id)}
                      data-testid={`event-row-${evt.event_id}`}
                      style={{
                        cursor: 'pointer',
                        borderBottom: '1px solid var(--color-border)',
                        background: isSelected ? 'rgba(37, 99, 235, 0.12)' : 'transparent',
                        fontWeight: isSelected ? 600 : 400,
                      }}
                    >
                      <td style={{ padding: '8px 12px' }}>
                        <code>{evt.event_id}</code>
                      </td>
                      <td style={{ padding: '8px 12px' }}>{evt.session_id}</td>
                      <td style={{ padding: '8px 12px' }}>{evt.anomaly_type}</td>
                      <td style={{ padding: '8px 12px' }}>
                        <span
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            background:
                              sev === 'HIGH' || sev === 'CRITICAL'
                                ? 'rgba(220, 38, 38, 0.15)'
                                : 'rgba(217, 119, 6, 0.15)',
                            color:
                              sev === 'HIGH' || sev === 'CRITICAL' ? '#dc2626' : '#d97706',
                          }}
                        >
                          {sev}
                        </span>
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        {String(evt.start || raw.start_time || '—')}
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        {String(evt.end || raw.end_time || '—')}
                      </td>
                      <td style={{ padding: '8px 12px' }}>{evt.sample_count}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Selected Event Details & Agent Reports */}
      {activeEvent && (
        <section
          data-testid="selected-event-details"
          style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
        >
          {/* Action Row: Title & Download Button */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <h3 style={{ margin: 0, fontSize: '16px' }}>
              Event Detail: <code>{activeEvent.event_id}</code>
            </h3>

            {downloadUrl && (
              <a
                href={downloadUrl}
                download={`${activeEvent.event_id}_diagnosed.json`}
                data-testid="download-json-button"
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  background: 'var(--color-primary)',
                  color: '#ffffff',
                  textDecoration: 'none',
                  fontSize: '13px',
                  fontWeight: 600,
                }}
              >
                📥 Download Event JSON
              </a>
            )}
          </div>

          {/* Row 1: Signal, Cell, Network Agent Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '16px',
            }}
          >
            {/* Signal Agent Card */}
            <div
              data-testid="agent-card-signal"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <h4 style={{ margin: '0 0 8px 0', fontSize: '14px' }}>📶 Signal Agent</h4>
              <div style={{ fontSize: '13px', marginBottom: '8px' }}>
                <strong>Condition:</strong>{' '}
                <code>{String(sigReport.signal_condition || 'unknown')}</code>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                <strong>Evidence:</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                  {Array.isArray(sigReport.evidence) && sigReport.evidence.length > 0 ? (
                    (sigReport.evidence as unknown[]).map((ev, i) => (
                      <li key={i}>{String(ev)}</li>
                    ))
                  ) : (
                    <li>No signal evidence recorded.</li>
                  )}
                </ul>
              </div>
            </div>

            {/* Cell Agent Card */}
            <div
              data-testid="agent-card-cell"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <h4 style={{ margin: '0 0 8px 0', fontSize: '14px' }}>🗼 Cell Agent</h4>
              <div style={{ fontSize: '13px', marginBottom: '8px' }}>
                <strong>Cell Event:</strong>{' '}
                <code>{String(cellReport.cell_event || 'NONE')}</code>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                <strong>Evidence:</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                  {Array.isArray(cellReport.evidence) && cellReport.evidence.length > 0 ? (
                    (cellReport.evidence as unknown[]).map((ev, i) => (
                      <li key={i}>{String(ev)}</li>
                    ))
                  ) : (
                    <li>No cell transition evidence.</li>
                  )}
                </ul>
              </div>
            </div>

            {/* Network Agent Card */}
            <div
              data-testid="agent-card-network"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <h4 style={{ margin: '0 0 8px 0', fontSize: '14px' }}>🌐 Network Agent</h4>
              <div style={{ fontSize: '13px', marginBottom: '8px' }}>
                <strong>State:</strong> <code>{String(netReport.network_state || 'stable')}</code>
                {' · '}
                <strong>Deployment:</strong>{' '}
                <code>{String(netReport.deployment_mode || 'UNKNOWN')}</code>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                <strong>Evidence:</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                  {Array.isArray(netReport.evidence) && netReport.evidence.length > 0 ? (
                    (netReport.evidence as unknown[]).map((ev, i) => (
                      <li key={i}>{String(ev)}</li>
                    ))
                  ) : (
                    <li>No network state changes.</li>
                  )}
                </ul>
              </div>
            </div>
          </div>

          {/* Row 2: Diagnosis Agent & Recommendation Agent */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '16px',
            }}
          >
            {/* Diagnosis Agent Card */}
            <div
              data-testid="agent-card-diagnosis"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <h4 style={{ margin: '0 0 8px 0', fontSize: '14px' }}>🧠 Diagnosis Agent</h4>
              <div style={{ fontSize: '13px', marginBottom: '8px' }}>
                <strong>Summary:</strong> {String(diagData.summary || '—')}
              </div>
              {Boolean(diagData.confidence_note) && (
                <div
                  style={{
                    fontSize: '12px',
                    fontStyle: 'italic',
                    color: 'var(--color-text-muted)',
                    marginBottom: '8px',
                  }}
                >
                  Confidence Note: {String(diagData.confidence_note)}
                </div>
              )}
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                <strong>Aggregated Evidence:</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                  {Array.isArray(diagData.evidence) && diagData.evidence.length > 0 ? (
                    (diagData.evidence as unknown[]).map((ev, i) => (
                      <li key={i}>{String(ev)}</li>
                    ))
                  ) : (
                    <li>No diagnosis evidence.</li>
                  )}
                </ul>
              </div>
            </div>

            {/* Recommendation Agent Card */}
            <div
              data-testid="agent-card-recommendation"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <h4 style={{ margin: '0 0 8px 0', fontSize: '14px' }}>💡 Recommendation Agent</h4>
              <div style={{ fontSize: '13px', marginBottom: '8px' }}>
                <strong>Kind:</strong> <code>{String(recData.kind || 'MONITORING')}</code>
              </div>
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  background: 'var(--color-bg)',
                  border: '1px solid var(--color-border)',
                  fontSize: '13px',
                }}
              >
                {String(recData.text || 'No recommendation provided.')}
              </div>
            </div>
          </div>

          {/* Event Window Telemetry Visualization */}
          {eventWindowSamples.length > 0 && (
            <section
              data-testid="event-window-chart"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <h4 style={{ margin: '0 0 12px 0', fontSize: '14px' }}>
                Event Window Telemetry (SS-RSRP)
              </h4>
              <svg
                viewBox="0 0 800 120"
                style={{ width: '100%', height: '120px', overflow: 'visible' }}
                role="img"
                aria-label="Event Window Telemetry Chart"
              >
                {/* SVG Polyline Context and Span */}
                {(() => {
                  const valid = eventWindowSamples.filter(p => p.val !== null);
                  if (valid.length === 0) return null;
                  const vals = valid.map(p => p.val as number);
                  const min = Math.min(...vals) - 2;
                  const max = Math.max(...vals) + 2;
                  const range = max - min || 1;

                  const getX = (idx: number) =>
                    40 + (idx / Math.max(1, eventWindowSamples.length - 1)) * 730;
                  const getY = (val: number) => 10 + (1 - (val - min) / range) * 90;

                  const linePts = valid
                    .map(p => `${getX(p.idx).toFixed(1)},${getY(p.val as number).toFixed(1)}`)
                    .join(' ');

                  const spanPts = valid.filter(p => p.inSpan);

                  return (
                    <g>
                      <polyline
                        points={linePts}
                        fill="none"
                        stroke="#0284c7"
                        strokeWidth="1.5"
                        opacity={0.6}
                      />
                      {spanPts.map(p => (
                        <circle
                          key={p.idx}
                          cx={getX(p.idx)}
                          cy={getY(p.val as number)}
                          r={3}
                          fill="#dc2626"
                        />
                      ))}
                    </g>
                  );
                })()}
              </svg>
            </section>
          )}
        </section>
      )}
    </div>
  );
};
