/**
 * Signal Explorer Page Component (T16-011 / T17-004).
 *
 * Implements:
 * - Four stacked panels (RSRP, RSRQ, SINR, and IF score with 0.60 threshold line)
 * - Flag overlay toggles (both / baseline / IF / hide)
 * - Rolling-mean toggle and dashed overlay line
 * - One-session-at-a-time with session tabs and navigation
 * - Line segments strictly break at gaps and NA values (never bridging missing points)
 * - Shaded gap bands marking intervals with no data received (>15s)
 * - Rolling 5 / 15 / 60 min window selector
 * - Stream Pause / Resume freeze toggle without losing data
 * - Distinct '×' shape anomaly markers with tooltip
 * - Signal Summary sentence matching Streamlit min/max/mean
 * - Expandable data table fallback with '—' for missing values
 */

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useData } from '../data/useData';
import { useReplay } from '../data/ReplayContext';
import { formatVal } from './Overview';

export type FlagFilter = 'both' | 'baseline' | 'if' | 'none';
export type RollingWindow = '5m' | '15m' | '60m' | 'all';

export interface SignalSummaryStats {
  min: number;
  max: number;
  mean: number;
  count: number;
}

export function computeSummary(
  samples: Record<string, unknown>[],
  key: string
): SignalSummaryStats | null {
  const nums: number[] = [];
  for (const s of samples) {
    const raw = s[key];
    if (
      raw !== null &&
      raw !== undefined &&
      raw !== '' &&
      raw !== 2147483647 &&
      raw !== '2147483647' &&
      raw !== 'NA' &&
      raw !== '<NA>' &&
      raw !== 'nan'
    ) {
      const val = Number(raw);
      if (!isNaN(val)) {
        nums.push(val);
      }
    }
  }

  if (nums.length === 0) return null;

  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const sum = nums.reduce((acc, curr) => acc + curr, 0);
  const mean = sum / nums.length;

  return { min, max, mean, count: nums.length };
}

export function formatSummary(
  stats: SignalSummaryStats | null,
  name: string,
  unit: string
): string {
  if (!stats) {
    return `${name}: No valid measurements available in window.`;
  }
  return (
    `${name}: min ${stats.min.toFixed(1)} ${unit}, ` +
    `max ${stats.max.toFixed(1)} ${unit}, ` +
    `mean ${stats.mean.toFixed(1)} ${unit}.`
  );
}

interface GapInterval {
  startIdx: number;
  endIdx: number;
  durationSec: number;
}

interface PanelProps {
  title: string;
  unit: string;
  field: string;
  rollingField?: string;
  samples: Record<string, unknown>[];
  flagFilter: FlagFilter;
  showRolling: boolean;
  thresholdLine?: number;
  height?: number;
  color?: string;
  activeSampleIndex: number;
  onSelectSample: (index: number) => void;
}

export const SignalChartPanel: React.FC<PanelProps> = ({
  title,
  unit,
  field,
  rollingField,
  samples,
  flagFilter,
  showRolling,
  thresholdLine,
  height = 140,
  color = '#2563eb',
  activeSampleIndex,
  onSelectSample,
}) => {
  const width = 800;
  const padding = { top: 20, right: 30, bottom: 25, left: 55 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const { points, rollingPoints, yMin, yMax, anomPoints, gapBands } = useMemo(() => {
    let minVal = Infinity;
    let maxVal = -Infinity;

    if (thresholdLine !== undefined) {
      minVal = Math.min(minVal, thresholdLine - 0.1);
      maxVal = Math.max(maxVal, thresholdLine + 0.1);
    }

    const pts: { idx: number; val: number | null; timestamp: string }[] = [];
    const anoms: { idx: number; val: number; timestamp: string; flags: string }[] = [];
    const gaps: GapInterval[] = [];

    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      const raw = s[field];
      const ts = String(s.timestamp || '');
      let val: number | null = null;

      if (
        raw !== null &&
        raw !== undefined &&
        raw !== '' &&
        raw !== 2147483647 &&
        raw !== '2147483647' &&
        raw !== 'NA' &&
        raw !== '<NA>' &&
        raw !== 'nan'
      ) {
        const num = Number(raw);
        if (!isNaN(num)) {
          val = num;
          if (val < minVal) minVal = val;
          if (val > maxVal) maxVal = val;
        }
      }

      pts.push({ idx: i, val, timestamp: ts });

      // Detect timestamp gaps (> 15s)
      if (i > 0) {
        const prevTs = new Date(String(samples[i - 1].timestamp || '')).getTime();
        const currTs = new Date(ts).getTime();
        if (!isNaN(prevTs) && !isNaN(currTs)) {
          const diffSec = (currTs - prevTs) / 1000;
          if (diffSec > 15) {
            gaps.push({ startIdx: i - 1, endIdx: i, durationSec: diffSec });
          }
        }
      }

      // Anomaly detection flags check
      const baseFlag = Boolean(s.baseline_flag);
      const ifFlag = Boolean(s.if_flag);
      let isFlagged = false;
      const activeFlags: string[] = [];

      if (flagFilter === 'both' && (baseFlag || ifFlag)) {
        isFlagged = true;
        if (baseFlag) activeFlags.push('Baseline');
        if (ifFlag) activeFlags.push('IF');
      } else if (flagFilter === 'baseline' && baseFlag) {
        isFlagged = true;
        activeFlags.push('Baseline');
      } else if (flagFilter === 'if' && ifFlag) {
        isFlagged = true;
        activeFlags.push('IF');
      }

      if (isFlagged && val !== null) {
        anoms.push({
          idx: i,
          val,
          timestamp: ts,
          flags: activeFlags.join(' + '),
        });
      }
    }

    if (minVal === Infinity) minVal = 0;
    if (maxVal === -Infinity) maxVal = 1;

    // Rolling points
    const rollPts: { idx: number; val: number | null }[] = [];
    if (showRolling) {
      const windowSize = 5;
      for (let i = 0; i < samples.length; i++) {
        let rVal: number | null = null;
        if (rollingField && samples[i][rollingField] !== undefined) {
          const rawR = samples[i][rollingField];
          const numR = Number(rawR);
          if (!isNaN(numR)) rVal = numR;
        } else {
          let sum = 0;
          let count = 0;
          const start = Math.max(0, i - windowSize + 1);
          for (let j = start; j <= i; j++) {
            const v = pts[j].val;
            if (v !== null) {
              sum += v;
              count++;
            }
          }
          if (count > 0) {
            rVal = sum / count;
          }
        }
        rollPts.push({ idx: i, val: rVal });
      }
    }

    return {
      points: pts,
      rollingPoints: rollPts,
      yMin: minVal,
      yMax: maxVal,
      anomPoints: anoms,
      gapBands: gaps,
    };
  }, [samples, field, rollingField, thresholdLine, flagFilter, showRolling]);

  const getY = (val: number) => {
    const range = yMax - yMin;
    if (range === 0) return padding.top + innerH / 2;
    const normalized = (val - yMin) / range;
    return padding.top + (1 - normalized) * innerH;
  };

  const getX = (idx: number) => {
    if (samples.length <= 1) return padding.left;
    return padding.left + (idx / (samples.length - 1)) * innerW;
  };

  // Build SVG path string that breaks whenever a value is null OR across gaps
  const linePath = useMemo(() => {
    let d = '';
    let inSubpath = false;

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      if (p.val === null) {
        inSubpath = false;
        continue;
      }
      // Check for timestamp gap from previous sample
      if (i > 0) {
        const prevTs = new Date(points[i - 1].timestamp).getTime();
        const currTs = new Date(p.timestamp).getTime();
        if (!isNaN(prevTs) && !isNaN(currTs) && (currTs - prevTs) / 1000 > 15) {
          inSubpath = false;
        }
      }

      const x = getX(p.idx);
      const y = getY(p.val);
      if (!inSubpath) {
        d += `M ${x.toFixed(1)} ${y.toFixed(1)} `;
        inSubpath = true;
      } else {
        d += `L ${x.toFixed(1)} ${y.toFixed(1)} `;
      }
    }
    return d;
  }, [points, yMin, yMax, samples.length]);

  // Build rolling average path string
  const rollingPath = useMemo(() => {
    if (!showRolling || rollingPoints.length === 0) return '';
    let d = '';
    let inSubpath = false;

    for (let i = 0; i < rollingPoints.length; i++) {
      const p = rollingPoints[i];
      if (p.val === null) {
        inSubpath = false;
        continue;
      }
      if (i > 0 && points[i] && points[i - 1]) {
        const prevTs = new Date(points[i - 1].timestamp).getTime();
        const currTs = new Date(points[i].timestamp).getTime();
        if (!isNaN(prevTs) && !isNaN(currTs) && (currTs - prevTs) / 1000 > 15) {
          inSubpath = false;
        }
      }
      const x = getX(p.idx);
      const y = getY(p.val);
      if (!inSubpath) {
        d += `M ${x.toFixed(1)} ${y.toFixed(1)} `;
        inSubpath = true;
      } else {
        d += `L ${x.toFixed(1)} ${y.toFixed(1)} `;
      }
    }
    return d;
  }, [rollingPoints, points, showRolling, yMin, yMax, samples.length]);

  return (
    <div
      data-testid={`signal-panel-${field}`}
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--color-text)',
        }}
      >
        <span>
          {title} ({unit})
        </span>
        {activeSampleIndex >= 0 && activeSampleIndex < samples.length && (
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
            Selected:{' '}
            <strong style={{ color }}>
              {formatVal(samples[activeSampleIndex][field], unit, 1)}
            </strong>
          </span>
        )}
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: `${height}px`, overflow: 'visible' }}
        role="img"
        aria-label={`${title} time-series chart`}
      >
        <desc>{`${title} time-series chart showing ${points.length} measurements in ${unit} ranging from ${yMin.toFixed(1)} to ${yMax.toFixed(1)}.`}</desc>
        {/* Shaded Gap Bands (intervals > 15s) */}
        {gapBands.map((gap, i) => {
          const x1 = getX(gap.startIdx);
          const x2 = getX(gap.endIdx);
          const bandW = Math.max(x2 - x1, 6);
          return (
            <g key={i} data-testid="gap-band">
              <rect
                x={x1}
                y={padding.top}
                width={bandW}
                height={innerH}
                fill="rgba(148, 163, 184, 0.22)"
                stroke="#94a3b8"
                strokeWidth="1"
                strokeDasharray="3,3"
              />
              <title>{`No data gap: ${Math.round(gap.durationSec)}s missing`}</title>
            </g>
          );
        })}

        {/* Y Axis Grid Lines & Labels */}
        <line
          x1={padding.left}
          y1={padding.top}
          x2={width - padding.right}
          y2={padding.top}
          stroke="var(--color-border)"
          strokeDasharray="2,2"
        />
        <text
          x={padding.left - 6}
          y={padding.top + 4}
          textAnchor="end"
          fontSize="10"
          fill="var(--color-text-muted)"
        >
          {yMax.toFixed(1)}
        </text>

        <line
          x1={padding.left}
          y1={padding.top + innerH / 2}
          x2={width - padding.right}
          y2={padding.top + innerH / 2}
          stroke="var(--color-border)"
          strokeDasharray="2,2"
        />
        <text
          x={padding.left - 6}
          y={padding.top + innerH / 2 + 4}
          textAnchor="end"
          fontSize="10"
          fill="var(--color-text-muted)"
        >
          {((yMin + yMax) / 2).toFixed(1)}
        </text>

        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          stroke="var(--color-border)"
        />
        <text
          x={padding.left - 6}
          y={height - padding.bottom + 4}
          textAnchor="end"
          fontSize="10"
          fill="var(--color-text-muted)"
        >
          {yMin.toFixed(1)}
        </text>

        {/* Optional Threshold Line (e.g. 0.60 on IF score) */}
        {thresholdLine !== undefined && (
          <g data-testid="threshold-line-group">
            <line
              x1={padding.left}
              y1={getY(thresholdLine)}
              x2={width - padding.right}
              y2={getY(thresholdLine)}
              stroke="#dc2626"
              strokeWidth="1.2"
              strokeDasharray="4,4"
            />
            <text
              x={width - padding.right}
              y={getY(thresholdLine) - 4}
              textAnchor="end"
              fontSize="10"
              fontWeight="600"
              fill="#dc2626"
            >
              Threshold ({thresholdLine.toFixed(2)})
            </text>
          </g>
        )}

        {/* Rolling Average Line */}
        {showRolling && rollingPath && (
          <path
            d={rollingPath}
            fill="none"
            stroke={color}
            strokeWidth="1.2"
            strokeDasharray="4,3"
            opacity={0.7}
          />
        )}

        {/* Main Metric Line */}
        {linePath && (
          <path
            d={linePath}
            fill="none"
            stroke={color}
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* Distinct '×' Shape Anomaly Markers */}
        {anomPoints.map(anom => {
          const cx = getX(anom.idx);
          const cy = getY(anom.val);
          const s = 4.5;
          return (
            <g
              key={anom.idx}
              data-testid="anomaly-marker"
              tabIndex={0}
              role="button"
              aria-label={`Anomaly marker at ${anom.timestamp}: ${anom.val.toFixed(1)} ${unit}`}
              onClick={() => onSelectSample(anom.idx)}
              style={{ cursor: 'pointer' }}
            >
              <line
                x1={cx - s}
                y1={cy - s}
                x2={cx + s}
                y2={cy + s}
                stroke="#dc2626"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
              <line
                x1={cx - s}
                y1={cy + s}
                x2={cx + s}
                y2={cy - s}
                stroke="#dc2626"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
              <title>
                {`Anomaly Flagged (${anom.flags})\n` +
                  `Time: ${anom.timestamp}\n` +
                  `Value: ${anom.val.toFixed(1)} ${unit}`}
              </title>
            </g>
          );
        })}

        {/* Active Selected Sample Scrubber Indicator */}
        {activeSampleIndex >= 0 && activeSampleIndex < samples.length && (
          <line
            x1={getX(activeSampleIndex)}
            y1={padding.top}
            x2={getX(activeSampleIndex)}
            y2={height - padding.bottom}
            stroke="var(--color-primary)"
            strokeWidth="1.5"
            strokeDasharray="2,2"
          />
        )}
      </svg>
    </div>
  );
};

export const SignalExplorer: React.FC = () => {
  const { samples, sessions, selectedSessionId, setSelectedSessionId } = useData();
  const { currentIndex, setCurrentIndex } = useReplay();

  const [flagFilter, setFlagFilter] = useState<FlagFilter>('both');
  const [showRolling, setShowRolling] = useState<boolean>(true);
  const [showTable, setShowTable] = useState<boolean>(false);
  const [rollingWindow, setRollingWindow] = useState<RollingWindow>('all');
  const [isPaused, setIsPaused] = useState<boolean>(false);

  // Freeze snapshot when paused to avoid losing incoming data
  const frozenSamplesRef = useRef<Record<string, unknown>[]>(samples);
  useEffect(() => {
    if (!isPaused) {
      frozenSamplesRef.current = samples;
    }
  }, [samples, isPaused]);

  const activeSamples = isPaused ? frozenSamplesRef.current : samples;

  // Filter samples based on rolling window (5m, 15m, 60m, or all)
  const windowedSamples = useMemo(() => {
    if (rollingWindow === 'all' || activeSamples.length === 0) {
      return activeSamples;
    }

    const windowSec =
      rollingWindow === '5m' ? 300 : rollingWindow === '15m' ? 900 : 3600;

    // Use latest timestamp
    let maxTsMs = -Infinity;
    for (const s of activeSamples) {
      const ts = s.timestamp ? new Date(String(s.timestamp)).getTime() : NaN;
      if (!isNaN(ts) && ts > maxTsMs) {
        maxTsMs = ts;
      }
    }

    if (maxTsMs === -Infinity) {
      // Fallback: take last N points
      const n = Math.min(activeSamples.length, windowSec);
      return activeSamples.slice(-n);
    }

    const cutoffMs = maxTsMs - windowSec * 1000;
    return activeSamples.filter(s => {
      const ts = s.timestamp ? new Date(String(s.timestamp)).getTime() : NaN;
      return isNaN(ts) || ts >= cutoffMs;
    });
  }, [activeSamples, rollingWindow]);

  // Summaries computed over windowed samples
  const rsrpSummary = useMemo(
    () => computeSummary(windowedSamples, 'ss_rsrp'),
    [windowedSamples]
  );
  const rsrqSummary = useMemo(
    () => computeSummary(windowedSamples, 'ss_rsrq'),
    [windowedSamples]
  );
  const sinrSummary = useMemo(
    () => computeSummary(windowedSamples, 'ss_sinr'),
    [windowedSamples]
  );

  const activeSessionIdx = sessions.findIndex(s => s.session_id === selectedSessionId);

  const handlePrevSession = () => {
    if (activeSessionIdx > 0) {
      setSelectedSessionId(sessions[activeSessionIdx - 1].session_id);
    }
  };

  const handleNextSession = () => {
    if (activeSessionIdx >= 0 && activeSessionIdx < sessions.length - 1) {
      setSelectedSessionId(sessions[activeSessionIdx + 1].session_id);
    }
  };

  const togglePause = () => {
    if (!isPaused) {
      frozenSamplesRef.current = samples;
      setIsPaused(true);
    } else {
      setIsPaused(false);
    }
  };

  if (!samples || samples.length === 0) {
    return (
      <div
        data-testid="signal-empty-state"
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
          No valid samples for the selected device/session.
        </p>
      </div>
    );
  }

  return (
    <div
      data-testid="signal-explorer-page"
      style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
    >
      {/* Session Switcher Strip & Controls */}
      <section
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'var(--color-surface)',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        {/* Session Tabs & Prev/Next */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
            Session:
          </span>
          <button
            onClick={handlePrevSession}
            disabled={activeSessionIdx <= 0}
            aria-label="Prev session"
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              cursor: activeSessionIdx <= 0 ? 'not-allowed' : 'pointer',
              opacity: activeSessionIdx <= 0 ? 0.5 : 1,
              fontSize: '12px',
            }}
          >
            ◀ Prev
          </button>
          <div style={{ display: 'flex', gap: '4px' }}>
            {sessions.map(s => {
              const isSelected = s.session_id === selectedSessionId;
              return (
                <button
                  key={s.session_id}
                  onClick={() => setSelectedSessionId(s.session_id)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '4px',
                    border: isSelected
                      ? '1px solid var(--color-primary)'
                      : '1px solid var(--color-border)',
                    background: isSelected ? 'var(--color-primary)' : 'var(--color-bg)',
                    color: isSelected ? '#ffffff' : 'var(--color-text)',
                    fontSize: '12px',
                    fontWeight: isSelected ? 700 : 400,
                    cursor: 'pointer',
                  }}
                >
                  {s.session_id}
                </button>
              );
            })}
          </div>
          <button
            onClick={handleNextSession}
            disabled={activeSessionIdx >= sessions.length - 1}
            aria-label="Next session"
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              cursor: activeSessionIdx >= sessions.length - 1 ? 'not-allowed' : 'pointer',
              opacity: activeSessionIdx >= sessions.length - 1 ? 0.5 : 1,
              fontSize: '12px',
            }}
          >
            Next ▶
          </button>
        </div>

        {/* Window Selector, Pause/Resume, Flag & Rolling Toggles */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          {/* Pause / Resume Button */}
          <button
            type="button"
            data-testid="pause-resume-button"
            onClick={togglePause}
            aria-label={isPaused ? 'Resume Stream' : 'Pause Stream'}
            style={{
              padding: '4px 10px',
              borderRadius: '4px',
              border: isPaused ? '1px solid #16a34a' : '1px solid var(--color-border)',
              background: isPaused ? 'rgba(22, 163, 74, 0.15)' : 'var(--color-bg)',
              color: isPaused ? '#16a34a' : 'var(--color-text)',
              fontWeight: 600,
              fontSize: '12px',
              cursor: 'pointer',
            }}
          >
            {isPaused ? '▶️ Resume Stream' : '⏸️ Pause Stream'}
          </button>

          {isPaused && (
            <span
              data-testid="pause-badge"
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: '#d97706',
                background: '#fef3c7',
                padding: '2px 8px',
                borderRadius: '4px',
              }}
            >
              PAUSED (view frozen)
            </span>
          )}

          {/* Rolling Window Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
              Window:
            </span>
            <select
              value={rollingWindow}
              onChange={e => setRollingWindow(e.target.value as RollingWindow)}
              aria-label="Time Window Range"
              style={{
                padding: '4px 8px',
                borderRadius: '4px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-bg)',
                color: 'var(--color-text)',
                fontSize: '12px',
              }}
            >
              <option value="all">All Session</option>
              <option value="5m">Last 5 min</option>
              <option value="15m">Last 15 min</option>
              <option value="60m">Last 60 min</option>
            </select>
          </div>

          {/* Flags Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
              Flags:
            </span>
            <select
              value={flagFilter}
              onChange={e => setFlagFilter(e.target.value as FlagFilter)}
              aria-label="Anomaly Marker Overlay"
              style={{
                padding: '4px 8px',
                borderRadius: '4px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-bg)',
                color: 'var(--color-text)',
                fontSize: '12px',
              }}
            >
              <option value="both">Both Flags (Baseline & IF)</option>
              <option value="baseline">Baseline Flags Only</option>
              <option value="if">IF Flags Only</option>
              <option value="none">Hide Flags</option>
            </select>
          </div>

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: 'var(--color-text)',
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={showRolling}
              onChange={e => setShowRolling(e.target.checked)}
            />
            Show Rolling Mean Overlay
          </label>
        </div>
      </section>

      {/* Signal Summary Sentences */}
      <section
        data-testid="signal-summary"
        style={{
          background: 'var(--color-surface)',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h3 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 600 }}>
          Signal Summary
        </h3>
        <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: '1.6' }}>
          <li>{formatSummary(rsrpSummary, 'SS-RSRP', 'dBm')}</li>
          <li>{formatSummary(rsrqSummary, 'SS-RSRQ', 'dB')}</li>
          <li>{formatSummary(sinrSummary, 'SS-SINR', 'dB')}</li>
        </ul>
      </section>

      {/* Four Stacked Charts */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Panel 1: RSRP */}
        <SignalChartPanel
          title="SS-RSRP"
          unit="dBm"
          field="ss_rsrp"
          rollingField="rolling_mean_ss_rsrp"
          samples={windowedSamples}
          flagFilter={flagFilter}
          showRolling={showRolling}
          color="#0284c7"
          activeSampleIndex={currentIndex}
          onSelectSample={setCurrentIndex}
        />

        {/* Panel 2: RSRQ */}
        <SignalChartPanel
          title="SS-RSRQ"
          unit="dB"
          field="ss_rsrq"
          rollingField="rolling_mean_ss_rsrq"
          samples={windowedSamples}
          flagFilter={flagFilter}
          showRolling={showRolling}
          color="#16a34a"
          activeSampleIndex={currentIndex}
          onSelectSample={setCurrentIndex}
        />

        {/* Panel 3: SINR */}
        <SignalChartPanel
          title="SS-SINR"
          unit="dB"
          field="ss_sinr"
          rollingField="rolling_mean_ss_sinr"
          samples={windowedSamples}
          flagFilter={flagFilter}
          showRolling={showRolling}
          color="#9333ea"
          activeSampleIndex={currentIndex}
          onSelectSample={setCurrentIndex}
        />

        {/* Panel 4: IF Score & 0.60 Threshold Line */}
        <SignalChartPanel
          title="Anomaly Score (Isolation Forest)"
          unit="Score"
          field="if_score"
          samples={windowedSamples}
          flagFilter={flagFilter}
          showRolling={false}
          thresholdLine={0.6}
          color="#d97706"
          activeSampleIndex={currentIndex}
          onSelectSample={setCurrentIndex}
        />
      </div>

      {/* Data Table Expander (Tabular Fallback) */}
      <section
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        <button
          data-testid="toggle-table-button"
          onClick={() => setShowTable(prev => !prev)}
          style={{
            width: '100%',
            textAlign: 'left',
            padding: '12px 16px',
            background: 'none',
            border: 'none',
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--color-text)',
            cursor: 'pointer',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>📋 Show Data Table Fallback ({windowedSamples.length} rows)</span>
          <span>{showTable ? '▲ Collapse' : '▼ Expand'}</span>
        </button>

        {showTable && (
          <div
            data-testid="signal-data-table"
            style={{
              overflowX: 'auto',
              maxHeight: '360px',
              borderTop: '1px solid var(--color-border)',
            }}
          >
            <table
              aria-label="Signal metrics tabular fallback"
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '12px',
                textAlign: 'left',
              }}
            >
              <thead style={{ background: 'var(--color-bg)', position: 'sticky', top: 0 }}>
                <tr>
                  <th style={{ padding: '8px 12px' }}>Timestamp</th>
                  <th style={{ padding: '8px 12px' }}>RSRP</th>
                  <th style={{ padding: '8px 12px' }}>RSRQ</th>
                  <th style={{ padding: '8px 12px' }}>SINR</th>
                  <th style={{ padding: '8px 12px' }}>PCI</th>
                  <th style={{ padding: '8px 12px' }}>NCI</th>
                  <th style={{ padding: '8px 12px' }}>IF Score</th>
                  <th style={{ padding: '8px 12px' }}>Base Flag</th>
                  <th style={{ padding: '8px 12px' }}>IF Flag</th>
                  <th style={{ padding: '8px 12px' }}>Type</th>
                </tr>
              </thead>
              <tbody>
                {windowedSamples.map((s, idx) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid var(--color-border)',
                      background:
                        idx === currentIndex ? 'rgba(37, 99, 235, 0.08)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '6px 12px' }}>{String(s.timestamp || '—')}</td>
                    <td style={{ padding: '6px 12px' }}>{formatVal(s.ss_rsrp, 'dBm', 1)}</td>
                    <td style={{ padding: '6px 12px' }}>{formatVal(s.ss_rsrq, 'dB', 1)}</td>
                    <td style={{ padding: '6px 12px' }}>{formatVal(s.ss_sinr, 'dB', 1)}</td>
                    <td style={{ padding: '6px 12px' }}>{formatVal(s.pci, '', 0)}</td>
                    <td style={{ padding: '6px 12px' }}>{formatVal(s.nci, '', 0)}</td>
                    <td style={{ padding: '6px 12px' }}>{formatVal(s.if_score, '', 3)}</td>
                    <td style={{ padding: '6px 12px' }}>
                      {s.baseline_flag ? 'True' : 'False'}
                    </td>
                    <td style={{ padding: '6px 12px' }}>
                      {s.if_flag ? 'True' : 'False'}
                    </td>
                    <td style={{ padding: '6px 12px' }}>{String(s.anomaly_type || 'NORMAL')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
