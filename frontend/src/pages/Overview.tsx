/**
 * Overview Page Component (T16-009).
 *
 * Implements:
 * - Status banner (anomaly rule from 1_Overview.py L47-52)
 * - Network & device state card (UNKNOWN displayed as 'Unknown (not exposed by this device)')
 * - Six metric cards with deltas that never truncate at 1280px or 375px
 * - Score block (separate baseline and IF scores, distinct ML-only flag)
 * - Event diagnosis, evidence list, and recommendations
 * - Clean empty state when no samples are loaded
 * - Missing values displayed as '—', never 0
 */

import React from 'react';
import { EventRecord } from '../types/contracts';

export interface OverviewProps {
  currentSample?: Record<string, unknown> | null;
  prevSample?: Record<string, unknown> | null;
  events?: EventRecord[];
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
}) => {
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

  // 1. Anomaly Status & Severity (1_Overview.py L47-52)
  let isAnom = Boolean(currentSample.is_anom);
  if (!isAnom) {
    const anomalyType = String(currentSample.anomaly_type || 'NORMAL');
    isAnom = !['NORMAL', 'CELL_TRANSITION', 'NETWORK_STATE_TRANSITION'].includes(
      anomalyType
    );
  }
  const severity = String(currentSample.severity || 'LOW').toUpperCase();

  const isStatisticalOnly = currentSample.anomaly_type === 'STATISTICAL_ONLY';

  // 2. Metric Calculations
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

  // 3. Deployment Mode & Device State
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

  // 4. Score Block
  const ifScore = currentSample.if_score;
  const zMax = currentSample.baseline_z_max;
  const baseFlag = Boolean(currentSample.baseline_flag);
  const ifFlag = Boolean(currentSample.if_flag);

  // 5. Diagnostics & Matching Event
  const currTs = currentSample.timestamp ? String(currentSample.timestamp) : null;
  let matchingEvent: EventRecord | undefined = undefined;
  if (currTs && events.length > 0) {
    matchingEvent = events.find((evt) => {
      const startTs = String(evt.start);
      const endTs = String(evt.end);
      return startTs <= currTs && currTs <= endTs;
    });
  }

  const anomType = String(currentSample.anomaly_type || 'NORMAL');

  return (
    <div
      data-testid="overview-page"
      style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
    >
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>
            {isAnom ? '⚠️ ANOMALY DETECTED' : '✅ NORMAL OPERATING CONDITIONS'}
          </h2>
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
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              color: 'var(--color-text-muted)',
            }}
          >
            NETWORK & DEVICE STATE
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
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              color: 'var(--color-text-muted)',
            }}
          >
            SIGNAL & CELL METRICS
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
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              color: 'var(--color-text-muted)',
            }}
          >
            DIAGNOSTICS & RECOMMENDATIONS
          </div>

          <div style={{ fontSize: '14px' }}>
            <span style={{ fontWeight: 600 }}>Detected Event Type:</span>{' '}
            <code>{anomType}</code>
          </div>

          {matchingEvent && matchingEvent.diagnosis ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>
                <strong>Diagnosis:</strong>{' '}
                {String(
                  (matchingEvent.diagnosis as Record<string, unknown>).summary ||
                    'No summary available.'
                )}
              </div>
              {Array.isArray((matchingEvent.diagnosis as Record<string, unknown>).evidence) && (
                <div>
                  <strong>Evidence:</strong>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                    {(
                      (matchingEvent.diagnosis as Record<string, unknown>)
                        .evidence as string[]
                    ).map((ev, i) => (
                      <li key={i}>{ev}</li>
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
                💡 <strong>
                  Recommendation [
                  {String(
                    (matchingEvent.recommendation as Record<string, unknown>)?.kind ||
                      'MONITORING'
                  )}
                  ]:
                </strong>{' '}
                <span>
                  {String(
                    (matchingEvent.recommendation as Record<string, unknown>)?.text ||
                      'Continue standard monitoring.'
                  )}
                </span>
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
