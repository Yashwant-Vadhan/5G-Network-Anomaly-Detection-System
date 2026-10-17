/**
 * Overview Page Component (T16-009 / T17-003).
 *
 * Implements:
 * - Status banner (anomaly rule from 1_Overview.py L47-52)
 * - PROVISIONAL / FINAL badge (G23: open events labelled PROVISIONAL)
 * - Provisional diagnosis / recommendation prefix ("Provisional — ")
 * - Connection state rendering across all six states:
 *   LIVE, STALE, RECONNECTING, WAITING, DISCONNECTED, REPLAY-SOURCE
 * - STALE state: "Showing last known values" notification banner
 * - Alert banner with Acknowledge button and severity chip
 * - ML-only line: "Statistically unusual — no rule-based evidence (no alert)"
 * - Network & device state card (UNKNOWN displayed as 'Unknown (not exposed by this device)')
 * - Six metric cards with deltas that never truncate at 1280px or 375px
 * - Score block (separate baseline and IF scores, distinct ML-only flag)
 * - Clean empty, waiting, and disconnected states
 * - Missing values displayed as '—', never 0
 * - Timestamp labelled "device local time (no timezone recorded)"
 */

import React, { useState } from 'react';
import { EventRecord, ConnectionState } from '../types/contracts';

export interface AlertRecord {
  id?: string;
  alert_id?: string;
  severity?: string;
  summary?: string;
  message?: string;
  timestamp?: string;
  acknowledged?: boolean;
}

export interface OverviewProps {
  currentSample?: Record<string, unknown> | null;
  prevSample?: Record<string, unknown> | null;
  events?: EventRecord[];
  connectionState?: ConnectionState;
  sampleAgeText?: string;
  activeAlert?: AlertRecord | null;
  onAcknowledgeAlert?: (alertId: string) => void;
}

export function formatVal(
  val: unknown,
  unit: string = '',
  decimals: number = 1
): string {
  if (
    val === null ||
    val === undefined ||
    val === 'nan' ||
    val === 'NA' ||
    val === 'None' ||
    val === '<NA>' ||
    val === 2147483647 ||
    val === '2147483647' ||
    (typeof val === 'number' && isNaN(val))
  ) {
    return '—';
  }
  if (typeof val === 'number') {
    return `${val.toFixed(decimals)} ${unit}`.trim();
  }
  const parsed = Number(val);
  if (!isNaN(parsed) && typeof val === 'string' && val.trim() !== '') {
    return `${parsed.toFixed(decimals)} ${unit}`.trim();
  }
  return `${val} ${unit}`.trim();
}

export function calcDelta(
  curr: unknown,
  prev: unknown,
  decimals: number = 1
): string | null {
  if (
    curr === null ||
    curr === undefined ||
    prev === null ||
    prev === undefined ||
    curr === 2147483647 ||
    prev === 2147483647
  ) {
    return null;
  }
  const c = Number(curr);
  const p = Number(prev);
  if (isNaN(c) || isNaN(p)) return null;

  const diff = c - p;
  const sign = diff >= 0 ? '+' : '';
  return `${sign}${diff.toFixed(decimals)}`;
}

export const Overview: React.FC<OverviewProps> = ({
  currentSample,
  prevSample,
  events = [],
  connectionState = 'REPLAY-SOURCE',
  sampleAgeText,
  activeAlert = null,
  onAcknowledgeAlert,
}) => {
  const [alertDismissed, setAlertDismissed] = useState<boolean>(false);

  // 1. Connection-specific empty or error states
  if (connectionState === 'WAITING' && !currentSample) {
    return (
      <div
        data-testid="overview-waiting-state"
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          background: 'var(--color-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text-muted)',
        }}
      >
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
        <h3 style={{ fontSize: '18px', margin: '0 0 8px 0', color: 'var(--color-text)' }}>
          Waiting for Initial Phone Stream
        </h3>
        <p style={{ fontSize: '14px', margin: 0 }}>
          Connected to ingest server. Start collection on your Android device or pair via QR code.
        </p>
      </div>
    );
  }

  if (connectionState === 'DISCONNECTED' && !currentSample) {
    return (
      <div
        data-testid="overview-disconnected-state"
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          background: 'var(--color-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text-muted)',
        }}
      >
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚪</div>
        <h3 style={{ fontSize: '18px', margin: '0 0 8px 0', color: 'var(--color-text)' }}>
          Disconnected from Telemetry Server
        </h3>
        <p style={{ fontSize: '14px', margin: 0 }}>
          No active connection. Check your network or verify the backend service is running.
        </p>
      </div>
    );
  }

  if (!currentSample) {
    return (
      <div
        data-testid="overview-empty-state"
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          background: 'var(--color-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text-muted)',
        }}
      >
        <p style={{ fontSize: '16px', margin: 0 }}>
          No sample selected at current replay position.
        </p>
      </div>
    );
  }

  // 2. Anomaly Status & Severity (1_Overview.py L47-52)
  let isAnom = Boolean(currentSample.is_anom);
  if (!isAnom) {
    const anomalyType = String(currentSample.anomaly_type || 'NORMAL');
    isAnom = !['NORMAL', 'CELL_TRANSITION', 'NETWORK_STATE_TRANSITION'].includes(
      anomalyType
    );
  }
  const severity = String(currentSample.severity || 'LOW').toUpperCase();

  const isStatisticalOnly = currentSample.anomaly_type === 'STATISTICAL_ONLY';

  // 3. Metric Calculations
  const rsrpVal = currentSample.ss_rsrp;
  const prevRsrp = prevSample?.ss_rsrp;
  const rsrpDelta = calcDelta(rsrpVal, prevRsrp, 1);

  const rsrqVal = currentSample.ss_rsrq;
  const prevRsrq = prevSample?.ss_rsrq;
  const rsrqDelta = calcDelta(rsrqVal, prevRsrq, 1);

  const sinrVal = currentSample.ss_sinr;
  const prevSinr = prevSample?.ss_sinr;
  const sinrDelta = calcDelta(sinrVal, prevSinr, 1);

  const pciVal = currentSample.pci;
  const nciVal = currentSample.nci;
  const nrarfcnVal = currentSample.nrarfcn;

  // 4. Deployment Mode & Device State
  const depModeRaw = String(currentSample.deployment_mode || 'UNKNOWN');
  const depModeDisp =
    depModeRaw === 'UNKNOWN'
      ? 'Unknown (not exposed by this device)'
      : depModeRaw;

  let regDisp = '—';
  if (currentSample.registered === true || currentSample.registered === 1) {
    regDisp = 'Yes';
  } else if (
    currentSample.registered === false ||
    currentSample.registered === 0
  ) {
    regDisp = 'No';
  }

  // 5. Score Block
  const ifScore = currentSample.if_score;
  const zMax = currentSample.baseline_z_max;
  const baseFlag = Boolean(currentSample.baseline_flag);
  const ifFlag = Boolean(currentSample.if_flag);

  // 6. Diagnostics, Matching Event, and Provisional / Final Status
  const currTs = currentSample.timestamp ? String(currentSample.timestamp) : null;
  let matchingEvent: EventRecord | undefined = undefined;
  if (currTs && events.length > 0) {
    matchingEvent = events.find((evt) => {
      const startTs = String(evt.start);
      const endTs = String(evt.end);
      return startTs <= currTs && currTs <= endTs;
    });
  }

  const isProvisional =
    currentSample.event_status === 'PROVISIONAL' ||
    matchingEvent?.status === 'PROVISIONAL' ||
    (isAnom && !matchingEvent?.end && currentSample.is_open === true);

  const isFinal =
    matchingEvent?.status === 'FINAL' ||
    currentSample.event_status === 'FINAL';

  const anomType = String(currentSample.anomaly_type || 'NORMAL');

  // Diagnosis, evidence, recommendation with provisional prefix if open
  const diagData = matchingEvent?.diagnosis as Record<string, unknown> | undefined;
  const rawDiagSummary = diagData ? String(diagData.summary || '') : '';
  const diagSummary =
    isProvisional && rawDiagSummary && !rawDiagSummary.startsWith('Provisional —')
      ? `Provisional — ${rawDiagSummary}`
      : rawDiagSummary;

  const recData = matchingEvent?.recommendation as Record<string, unknown> | undefined;
  const rawRecText = recData ? String(recData.text || '') : '';
  const recText =
    isProvisional && rawRecText && !rawRecText.startsWith('Provisional —')
      ? `Provisional — ${rawRecText}`
      : rawRecText || 'Continue standard monitoring.';

  const handleAcknowledge = () => {
    setAlertDismissed(true);
    const alertId = activeAlert?.id || activeAlert?.alert_id || '';
    if (onAcknowledgeAlert && alertId) {
      onAcknowledgeAlert(alertId);
    }
  };

  const hasUnackAlert =
    Boolean(activeAlert) &&
    !activeAlert?.acknowledged &&
    !alertDismissed;

  return (
    <div
      data-testid="overview-page"
      style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
    >
      {/* Alert Banner (Conditional: Unacknowledged Alert) */}
      {hasUnackAlert && activeAlert && (
        <section
          data-testid="overview-alert-banner"
          role="alert"
          style={{
            padding: '12px 18px',
            borderRadius: '8px',
            backgroundColor: '#fee2e2',
            border: '1px solid #ef4444',
            color: '#991b1b',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              data-testid="alert-severity-chip"
              style={{
                backgroundColor: '#dc2626',
                color: '#ffffff',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.05em',
              }}
            >
              {String(activeAlert.severity || 'CRITICAL').toUpperCase()}
            </span>
            <span style={{ fontSize: '14px', fontWeight: 600 }}>
              {activeAlert.summary || activeAlert.message || 'Active network anomaly detected'}
            </span>
            {activeAlert.timestamp && (
              <span style={{ fontSize: '12px', opacity: 0.8 }}>
                ({activeAlert.timestamp} device local time)
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              data-testid="acknowledge-alert-button"
              onClick={handleAcknowledge}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                border: '1px solid #b91c1c',
                backgroundColor: '#dc2626',
                color: '#ffffff',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Acknowledge
            </button>
            <a
              href="#/events"
              style={{
                fontSize: '13px',
                color: '#991b1b',
                fontWeight: 600,
                textDecoration: 'underline',
              }}
            >
              Events & Alerts →
            </a>
          </div>
        </section>
      )}

      {/* Reconnecting State Notification */}
      {connectionState === 'RECONNECTING' && (
        <div
          data-testid="reconnecting-banner"
          style={{
            padding: '10px 16px',
            borderRadius: '6px',
            backgroundColor: 'rgba(37, 99, 235, 0.1)',
            border: '1px solid #2563eb',
            color: '#1d4ed8',
            fontSize: '13px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>🔄</span>
          <span>Reconnecting to live telemetry stream... attempting to resume session.</span>
        </div>
      )}

      {/* STALE State Notification Banner */}
      {connectionState === 'STALE' && (
        <div
          data-testid="stale-banner"
          style={{
            padding: '10px 16px',
            borderRadius: '6px',
            backgroundColor: '#fef3c7',
            border: '1px solid #d97706',
            color: '#92400e',
            fontSize: '13px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>⚠️</span>
          <span>
            STALE: Showing last known values
            {sampleAgeText ? ` (last sample received ${sampleAgeText})` : ' (telemetry delayed)'}
          </span>
        </div>
      )}

      {/* ML-Only Statistical Notice Line (amber bordered) */}
      {isStatisticalOnly && (
        <div
          data-testid="ml-only-banner"
          style={{
            padding: '10px 16px',
            borderRadius: '6px',
            backgroundColor: '#fffbeb',
            border: '1px solid #f59e0b',
            color: '#b45309',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          Statistically unusual — no rule-based evidence (no alert)
        </div>
      )}

      {/* Row 1: Status Banner */}
      <section
        data-testid="status-banner"
        style={{
          padding: '16px 20px',
          borderRadius: '8px',
          color: '#ffffff',
          backgroundColor: isAnom
            ? severity === 'HIGH' || severity === 'CRITICAL'
              ? '#dc2626'
              : '#d97706'
            : '#16a34a',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>
            {isAnom ? '⚠️ ANOMALY DETECTED' : '✅ NORMAL OPERATING CONDITIONS'}
          </h2>

          {/* Provisional badge */}
          {isProvisional && (
            <span
              data-testid="provisional-badge"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.25)',
                border: '1px dashed #ffffff',
                padding: '3px 10px',
                borderRadius: '12px',
                fontWeight: 700,
                fontSize: '12px',
                letterSpacing: '0.05em',
              }}
            >
              PROVISIONAL
            </span>
          )}

          {/* Final badge */}
          {isFinal && (
            <span
              data-testid="final-badge"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                border: '1px solid #ffffff',
                padding: '3px 10px',
                borderRadius: '12px',
                fontWeight: 700,
                fontSize: '12px',
                letterSpacing: '0.05em',
              }}
            >
              FINAL
            </span>
          )}
        </div>

        <span
          data-testid="severity-badge"
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.25)',
            padding: '4px 12px',
            borderRadius: '12px',
            fontWeight: 700,
            fontSize: '14px',
          }}
        >
          {isAnom ? `Severity: ${severity}` : 'Status: OK'}
        </span>
      </section>

      {/* Row 2: Network-State Card (4 col) & Metric Cards (8 col) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '20px',
        }}
      >
        {/* Network & Device State Card */}
        <section
          data-testid="network-device-card"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.05em',
                color: 'var(--color-text-muted)',
              }}
            >
              NETWORK & DEVICE STATE
            </span>
            {connectionState === 'STALE' && (
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#d97706',
                  backgroundColor: 'rgba(217, 119, 6, 0.1)',
                  padding: '2px 6px',
                  borderRadius: '4px',
                }}
              >
                (last known)
              </span>
            )}
          </div>

          <div style={{ fontSize: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div>
              <span style={{ fontWeight: 600 }}>Device:</span>{' '}
              <span>{String(currentSample.device || 'Unknown')}</span>
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Operator:</span>{' '}
              <span>{String(currentSample.operator || 'Unknown')}</span>
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Network Type:</span>{' '}
              <code style={{ fontSize: '13px' }}>
                {String(currentSample.network_type || 'Unknown')}
              </code>
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Deployment Mode:</span>{' '}
              <code style={{ fontSize: '13px' }}>{depModeDisp}</code>
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Registered:</span>{' '}
              <span>{regDisp}</span>
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Source:</span>{' '}
              <span>
                {connectionState === 'REPLAY-SOURCE' ? 'Replay / Demo' : 'Phone live stream'}
              </span>
            </div>
            {currTs && (
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                Time: {currTs} (device local time, no timezone recorded)
              </div>
            )}
          </div>
        </section>

        {/* Signal & Cell Metrics Cards */}
        <section
          data-testid="metrics-card"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.05em',
                color: 'var(--color-text-muted)',
              }}
            >
              SIGNAL & CELL METRICS
            </span>
            {connectionState === 'STALE' && (
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#d97706',
                  backgroundColor: 'rgba(217, 119, 6, 0.1)',
                  padding: '2px 6px',
                  borderRadius: '4px',
                }}
              >
                (last known values)
              </span>
            )}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))',
              gap: '12px',
            }}
          >
            {/* Metric 1: SS-RSRP */}
            <div data-testid="metric-rsrp" style={{ minWidth: 0, overflow: 'visible' }}>
              <div
                style={{
                  fontSize: '12px',
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}
              >
                SS-RSRP
              </div>
              <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {formatVal(rsrpVal, 'dBm', 1)}
              </div>
              {rsrpDelta && (
                <div
                  style={{
                    fontSize: '12px',
                    color: rsrpDelta.startsWith('+') ? '#16a34a' : '#dc2626',
                  }}
                >
                  {rsrpDelta}
                </div>
              )}
            </div>

            {/* Metric 2: SS-RSRQ */}
            <div data-testid="metric-rsrq" style={{ minWidth: 0, overflow: 'visible' }}>
              <div
                style={{
                  fontSize: '12px',
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}
              >
                SS-RSRQ
              </div>
              <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {formatVal(rsrqVal, 'dB', 1)}
              </div>
              {rsrqDelta && (
                <div
                  style={{
                    fontSize: '12px',
                    color: rsrqDelta.startsWith('+') ? '#16a34a' : '#dc2626',
                  }}
                >
                  {rsrqDelta}
                </div>
              )}
            </div>

            {/* Metric 3: SS-SINR */}
            <div data-testid="metric-sinr" style={{ minWidth: 0, overflow: 'visible' }}>
              <div
                style={{
                  fontSize: '12px',
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}
              >
                SS-SINR
              </div>
              <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {formatVal(sinrVal, 'dB', 1)}
              </div>
              {sinrDelta && (
                <div
                  style={{
                    fontSize: '12px',
                    color: sinrDelta.startsWith('+') ? '#16a34a' : '#dc2626',
                  }}
                >
                  {sinrDelta}
                </div>
              )}
            </div>

            {/* Metric 4: PCI */}
            <div data-testid="metric-pci" style={{ minWidth: 0, overflow: 'visible' }}>
              <div
                style={{
                  fontSize: '12px',
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}
              >
                PCI (Cell ID)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {formatVal(pciVal, '', 0)}
              </div>
            </div>

            {/* Metric 5: NCI */}
            <div data-testid="metric-nci" style={{ minWidth: 0, overflow: 'visible' }}>
              <div
                style={{
                  fontSize: '12px',
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}
              >
                NCI (5G Cell)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {formatVal(nciVal, '', 0)}
              </div>
            </div>

            {/* Metric 6: NRARFCN */}
            <div data-testid="metric-nrarfcn" style={{ minWidth: 0, overflow: 'visible' }}>
              <div
                style={{
                  fontSize: '12px',
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}
              >
                NRARFCN (Freq)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {formatVal(nrarfcnVal, '', 0)}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Row 3: Detection Scores (4 col) & Diagnostics / Recommendations (8 col) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '20px',
        }}
      >
        {/* Detection Scores Card */}
        <section
          data-testid="scores-card"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div
            style={{
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              color: 'var(--color-text-muted)',
            }}
          >
            ANOMALY DETECTION SCORES
          </div>

          <div style={{ fontSize: '18px', fontWeight: 700 }}>
            {ifScore !== null && ifScore !== undefined && !isNaN(Number(ifScore)) ? (
              <span>
                IF Anomaly Score: <strong>{Number(ifScore).toFixed(3)}</strong> / 1.000
              </span>
            ) : (
              <span>IF Anomaly Score: <em>N/A (Ineligible)</em></span>
            )}
          </div>

          {isStatisticalOnly && (
            <div
              style={{
                fontSize: '12px',
                padding: '4px 8px',
                borderRadius: '4px',
                background: '#fef3c7',
                color: '#92400e',
                fontWeight: 600,
              }}
            >
              ML-Only Statistical Flag (No Domain Rule Corroboration)
            </div>
          )}

          <div style={{ fontSize: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div>
              <span style={{ fontWeight: 600 }}>Baseline Max |Z| Score:</span>{' '}
              <code>{formatVal(zMax, '', 2)}</code>
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Baseline Flag:</span>{' '}
              <code>{baseFlag ? 'TRUE 🚩' : 'False'}</code>
              {' | '}
              <span style={{ fontWeight: 600 }}>IF Flag:</span>{' '}
              <code>{ifFlag ? 'TRUE 🚩' : 'False'}</code>
            </div>
          </div>
        </section>

        {/* Diagnostics & Recommendations Card */}
        <section
          data-testid="diagnostics-card"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.05em',
                color: 'var(--color-text-muted)',
              }}
            >
              DIAGNOSTICS & RECOMMENDATIONS
            </span>
            {isProvisional && (
              <span
                data-testid="event-status-badge"
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: '#d97706',
                  backgroundColor: '#fef3c7',
                  border: '1px dashed #d97706',
                  padding: '2px 8px',
                  borderRadius: '4px',
                }}
              >
                PROVISIONAL (open)
              </span>
            )}
            {isFinal && (
              <span
                data-testid="event-status-badge"
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: '#16a34a',
                  backgroundColor: '#dcfce7',
                  border: '1px solid #16a34a',
                  padding: '2px 8px',
                  borderRadius: '4px',
                }}
              >
                FINAL (closed)
              </span>
            )}
          </div>

          <div style={{ fontSize: '14px' }}>
            <span style={{ fontWeight: 600 }}>Detected Event Type:</span>{' '}
            <code>{anomType}</code>
          </div>

          {diagSummary ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>
                <strong>Diagnosis:</strong> <span>{diagSummary}</span>
              </div>
              {Array.isArray(diagData?.evidence) && (
                <div>
                  <strong>Evidence:</strong>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                    {(diagData.evidence as string[]).map((ev, i) => (
                      <li key={i}>{String(ev)}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div
                style={{
                  marginTop: '8px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  background: 'var(--color-bg)',
                  border: '1px solid var(--color-border)',
                  fontSize: '13px',
                }}
              >
                💡 <strong>Recommendation [{String(recData?.kind || 'MONITORING')}]:</strong>{' '}
                <span>{recText}</span>
              </div>
            </div>
          ) : anomType === 'NORMAL' ? (
            <div
              style={{
                padding: '8px 12px',
                borderRadius: '6px',
                background: '#dcfce7',
                color: '#166534',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              Normal network operating conditions. No active anomaly event.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>
                Status: {anomType} observed at timestamp <code>{currTs}</code>.
              </div>
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  background: 'var(--color-bg)',
                  border: '1px solid var(--color-border)',
                  fontSize: '13px',
                }}
              >
                💡 <strong>Recommendation [MONITORING]:</strong> Continue standard metric monitoring.
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
