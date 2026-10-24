/**
 * Overview Page Component (T16-009 / T17-003).
 *
 * Implements dual-audience user experience:
 * 1. Plain-English diagnosis, causes, and practical actions for ordinary users.
 * 2. Complete expandable technical metrics, 3GPP identifiers, and detection scores for engineers.
 *
 * Preserves all contract requirements, connection states, and test assertions.
 */

import React, { useState } from 'react';
import { EventRecord, ConnectionState } from '../types/contracts';
import { isValidMeasurement, formatVal, calcDelta } from '../utils/measurement';
import { getAnomalyPresentation } from '../utils/anomalyExplanations';

export { isValidMeasurement, formatVal, calcDelta };

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
  if ((connectionState === 'WAITING' || connectionState === 'LIVE') && !currentSample) {
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
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>📱</div>
        <h3 style={{ fontSize: '18px', margin: '0 0 8px 0', color: 'var(--color-text)' }}>
          Waiting for Initial Phone Stream
        </h3>
        <p style={{ fontSize: '14px', margin: '0 auto', maxWidth: '520px', color: 'var(--color-text)', lineHeight: '1.6' }}>
          Connected to ingest server. In the <strong>5GNetworkTester</strong> app on your phone, tap <strong>&quot;Start Collection&quot;</strong> to begin streaming real-time 5G telemetry.
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
          border: '1px solid var(--color-danger, #ef4444)',
          color: 'var(--color-danger, #ef4444)',
        }}
      >
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
        <h3 style={{ fontSize: '18px', margin: '0 0 8px 0' }}>
          Disconnected from Telemetry Server
        </h3>
        <p style={{ fontSize: '14px', margin: 0, color: 'var(--color-text)' }}>
          Cannot receive live data. Ensure the 5G-NADS streaming daemon is running.
        </p>
      </div>
    );
  }

  // 2. Clean empty state
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
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>📡</div>
        <h3 style={{ fontSize: '18px', margin: '0 0 8px 0', color: 'var(--color-text)' }}>
          No sample selected at current replay position.
        </h3>
        <p style={{ fontSize: '14px', margin: 0 }}>
          Select a session or start playback to inspect measurements.
        </p>
      </div>
    );
  }

  // 3. Extract sample values
  const isAnom = Boolean(currentSample.is_anom);
  const rawSev = currentSample.severity;
  const severity = String(rawSev || (isAnom ? 'MEDIUM' : 'LOW')).toUpperCase();
  const anomType = String(currentSample.anomaly_type || 'NORMAL');
  const isStatisticalOnly = anomType === 'STATISTICAL_ONLY';

  const rsrpVal = currentSample.ss_rsrp;
  const rsrqVal = currentSample.ss_rsrq;
  const sinrVal = currentSample.ss_sinr;

  const rsrpDelta = calcDelta(rsrpVal, prevSample?.ss_rsrp);
  const rsrqDelta = calcDelta(rsrqVal, prevSample?.ss_rsrq);
  const sinrDelta = calcDelta(sinrVal, prevSample?.ss_sinr);

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

  // 5. Detection Scores
  const ifScore = currentSample.if_score;
  const zMax = currentSample.baseline_z_max;
  const baseFlag = Boolean(currentSample.baseline_flag);
  const ifFlag = Boolean(currentSample.if_flag);

  // 6. Matching Event and Provisional / Final Status
  const currTs = currentSample.timestamp ? String(currentSample.timestamp) : null;
  let matchingEvent: EventRecord | undefined = undefined;
  if (currTs && events.length > 0) {
    matchingEvent = events.find(evt => {
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

  // Diagnosis, evidence, recommendation
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
      : rawRecText;

  // Dynamic presentation derived deterministically from measurements & event evidence
  const presentation = getAnomalyPresentation({
    anomalyType: anomType,
    isAnom,
    severity,
    eventStatus: isProvisional ? 'PROVISIONAL' : isFinal ? 'FINAL' : undefined,
    isRecovered: !isAnom && (prevSample ? Boolean(prevSample.is_anom) : false),
    rsrp: typeof rsrpVal === 'number' ? rsrpVal : null,
    deltaRsrp: rsrpDelta ? parseFloat(rsrpDelta) : null,
    durationSec: matchingEvent ? 30 : null,
    previousPci: prevSample?.pci as number | string | undefined,
    currentPci: pciVal as number | string | undefined,
    previousNetwork: prevSample?.network_type as string | undefined,
    currentNetwork: currentSample.network_type as string | undefined,
    backendDiagnosis: diagSummary || null,
    backendRecommendation: recText || null,
  });

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

  // Connection health indicator
  const connectionHealthText =
    connectionState === 'DISCONNECTED'
      ? 'Connection unavailable'
      : connectionState === 'WAITING'
      ? 'Waiting for measurements'
      : connectionState === 'RECONNECTING'
      ? 'Reconnecting to stream'
      : connectionState === 'STALE'
      ? 'Telemetry delayed'
      : isAnom
      ? severity === 'HIGH' || severity === 'CRITICAL'
        ? 'Possible connectivity issue'
        : 'Signal quality degraded'
      : 'Monitoring normally';

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

      {/* ML-Only Statistical Notice Line */}
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

      {/* Row 1: Connection & Anomaly Status Banner */}
      <section
        data-testid="status-banner"
        style={{
          padding: '18px 22px',
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
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>
              {isAnom ? '⚠️ ANOMALY DETECTED' : '✅ NORMAL OPERATING CONDITIONS'}
            </h2>
            <div style={{ fontSize: '13px', opacity: 0.9, marginTop: '2px', fontWeight: 500 }}>
              Connection Status: {connectionHealthText}
            </div>
          </div>

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
            padding: '4px 14px',
            borderRadius: '12px',
            fontWeight: 700,
            fontSize: '14px',
          }}
        >
          {isAnom ? `Severity: ${severity}` : 'Status: OK'}
        </span>
      </section>

      {/* Above-The-Fold Main Section: 2-Column Responsive Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '20px',
          alignItems: 'stretch',
        }}
      >
        {/* Left Column: Live Signal Telemetry & Network Identity */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '16px' }}>📶</span>
                <span
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    letterSpacing: '0.05em',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  LIVE SIGNAL & CELL METRICS
                </span>
              </div>
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
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
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
                      fontWeight: 600,
                    }}
                  >
                    {rsrpDelta}
                  </div>
                )}
              </div>

              {/* Metric 2: SS-RSRQ */}
              <div data-testid="metric-rsrq" style={{ minWidth: 0, overflow: 'visible' }}>
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
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
                      fontWeight: 600,
                    }}
                  >
                    {rsrqDelta}
                  </div>
                )}
              </div>

              {/* Metric 3: SS-SINR */}
              <div data-testid="metric-sinr" style={{ minWidth: 0, overflow: 'visible' }}>
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
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
                      fontWeight: 600,
                    }}
                  >
                    {sinrDelta}
                  </div>
                )}
              </div>

              {/* Metric 4: PCI */}
              <div data-testid="metric-pci" style={{ minWidth: 0, overflow: 'visible' }}>
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                  PCI (Cell ID)
                </div>
                <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                  {formatVal(pciVal, '', 0)}
                </div>
              </div>

              {/* Metric 5: NCI */}
              <div data-testid="metric-nci" style={{ minWidth: 0, overflow: 'visible' }}>
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                  NCI (5G Cell)
                </div>
                <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                  {formatVal(nciVal, '', 0)}
                </div>
              </div>

              {/* Metric 6: NRARFCN */}
              <div data-testid="metric-nrarfcn" style={{ minWidth: 0, overflow: 'visible' }}>
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                  NRARFCN (Freq)
                </div>
                <div style={{ fontSize: '18px', fontWeight: 700, whiteSpace: 'nowrap' }}>
                  {formatVal(nrarfcnVal, '', 0)}
                </div>
              </div>
            </div>
          </section>

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
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '16px' }}>📱</span>
                <span
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    letterSpacing: '0.05em',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  NETWORK & DEVICE STATE
                </span>
              </div>
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

            <div style={{ fontSize: '13.5px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
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

          {/* Anomaly Detection Scores Card (placed on Left Column for balanced layout) */}
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
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div
              style={{
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.05em',
                color: 'var(--color-text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>🎯</span> ANOMALY DETECTION SCORES
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px' }}>
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
                    fontSize: '11px',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    background: '#fef3c7',
                    color: '#92400e',
                    fontWeight: 600,
                  }}
                >
                  ML-Only Statistical Flag (No Domain Rule Corroboration)
                </div>
              )}
            </div>

            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', margin: 0, lineHeight: 1.5 }}>
              ℹ️ <strong>What this means:</strong> The Isolation Forest machine learning model scans 11 network features every second. Scores below 0.60 indicate normal radio variations, while scores above 0.60 indicate an unusual pattern and trigger automated multi-agent diagnosis.
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '12px',
                paddingTop: '10px',
                borderTop: '1px solid var(--color-border-subtle)',
                fontSize: '13px',
              }}
            >
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>
                  Baseline Max |Z| Score
                </span>
                <strong style={{ fontSize: '15px' }}>{formatVal(zMax, '', 2)}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>
                  Baseline Flag
                </span>
                <strong style={{ fontSize: '14px', color: baseFlag ? '#dc2626' : '#16a34a' }}>
                  {baseFlag ? 'FLAGGED 🚩' : 'CLEAR'}
                </strong>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>
                  IF Score Flag
                </span>
                <strong style={{ fontSize: '14px', color: ifFlag ? '#dc2626' : '#16a34a' }}>
                  {ifFlag ? 'FLAGGED 🚩' : 'CLEAR'}
                </strong>
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: AI Multi-Agent Diagnostics & Recommendations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Prominent AI Diagnostics & Local LLM Recommendations Card */}
          <section
            data-testid="diagnostics-card"
          style={{
            background: 'var(--color-surface)',
            border: '1.5px solid var(--color-border)',
            borderRadius: '10px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: 'var(--shadow-md)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid var(--color-border-subtle)',
              paddingBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '20px' }}>🤖</span>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  letterSpacing: '0.06em',
                  color: 'var(--color-primary)',
                  textTransform: 'uppercase',
                }}
              >
                AI Multi-Agent & Local LLM Diagnosis
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
          </div>

          {/* Human-Facing Anomaly Title */}
          <div>
            <h3
              style={{
                fontSize: '20px',
                fontWeight: 700,
                color: isAnom ? 'var(--color-text)' : 'var(--color-normal)',
                margin: '0 0 6px 0',
              }}
            >
              {presentation.humanTitle}
            </h3>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Detected Event Type: <code>{anomType}</code>
            </div>
          </div>

          {/* What Happened Section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text)' }}>
              What happened:
            </span>
            <p style={{ fontSize: '14px', margin: 0, color: 'var(--color-text)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
              {diagSummary || presentation.whatHappened}
            </p>
          </div>

          {/* Direct Evidence (if matching event provided) */}
          {Array.isArray(diagData?.evidence) && diagData.evidence.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text)' }}>
                Direct evidence observed:
              </span>
              <ul style={{ margin: '4px 0 0 20px', padding: 0, fontSize: '13px', color: 'var(--color-text)' }}>
                {(diagData.evidence as string[]).map((ev, i) => (
                  <li key={i} style={{ marginBottom: '2px' }}>{String(ev)}</li>
                ))}
              </ul>
            </div>
          )}

          {/* What Might Have Caused It */}
          {isAnom && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: '6px',
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
                lineHeight: 1.5,
              }}
            >
              <strong style={{ color: 'var(--color-text)' }}>Plausible causes: </strong>
              <span style={{ color: 'var(--color-text-muted)' }}>
                {presentation.probableCauses}
              </span>
            </div>
          )}

          {/* Practical Recommendations: What you can do vs Technical follow-up */}
          <div
            style={{
              padding: '16px 18px',
              borderRadius: '8px',
              background: isAnom ? 'rgba(37, 99, 235, 0.06)' : 'rgba(22, 163, 74, 0.08)',
              border: isAnom ? '1.5px solid var(--color-primary)' : '1.5px solid #16a34a',
              fontSize: '13.5px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '20px' }}>💡</span>
                <strong style={{ fontSize: '14px', color: isAnom ? 'var(--color-primary)' : '#166534' }}>
                  Local LLM Actionable Recommendation:
                </strong>
              </div>
              <div style={{ color: 'var(--color-text)', whiteSpace: 'pre-line', lineHeight: '1.65' }}>
                {recText || presentation.userAction}
              </div>
            </div>

            {isAnom && (
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', borderTop: '1px dashed var(--color-border)', paddingTop: '8px' }}>
                <strong style={{ color: 'var(--color-text)' }}>Technical follow-up: </strong>
                <div style={{ whiteSpace: 'pre-line', lineHeight: '1.5', marginTop: '2px' }}>
                  {presentation.technicalAction}
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  </div>
);
};
