/**
 * Cells & Network Page Component (T16-012 / T17-005).
 *
 * Implements:
 * - PCI / NCI / NRARFCN step charts per session (NCI/PCI as categorical labels)
 * - Transition table populated strictly from the demo bundle (bundle.transitions)
 * - Prominent "Cell change is normal behaviour" operational guidance note
 * - Transition count equals bundle transitions (G30: no client-side transition detection)
 * - Accessible SVG step charts with tooltips and empty states
 */

import { useState, useMemo } from 'react';
import { useData } from '../data/useData';
import { BundleTransition } from '../types/contracts';

export interface CellsNetworkProps {
  transitionsOverride?: BundleTransition[];
}

export function formatCellId(val: unknown): string {
  if (val === null || val === undefined || val === '' || val === 'NA' || val === '<NA>') {
    return '—';
  }
  return String(val);
}

export function CellsNetwork({ transitionsOverride }: CellsNetworkProps) {
  const { samples, transitions: contextTransitions } = useData();

  // Guardrail G30: Consume transitions strictly from bundle without client-side detection
  const transitions = useMemo(() => {
    return transitionsOverride || contextTransitions || [];
  }, [transitionsOverride, contextTransitions]);

  const [filterQuery, setFilterQuery] = useState('');
  const [activeChart, setActiveChart] = useState<'pci' | 'nci' | 'nrarfcn'>('pci');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Latest telemetry sample values
  const latestSample = samples.length > 0 ? samples[samples.length - 1] : null;
  const currentPci = latestSample ? formatCellId(latestSample.pci) : '—';
  const currentNci = latestSample ? formatCellId(latestSample.nci) : '—';
  const currentNrarfcn = latestSample ? formatCellId(latestSample.nrarfcn) : '—';
  const currentMode = latestSample?.deployment_mode ? String(latestSample.deployment_mode) : '—';

  // Filter transitions based on search query
  const filteredTransitions = useMemo(() => {
    if (!filterQuery.trim()) return transitions;
    const q = filterQuery.toLowerCase();
    return transitions.filter(t => {
      const typeStr = (t.kind || t.type || '').toLowerCase();
      const pciStr = `${t.pci_from}->${t.pci_to}`.toLowerCase();
      const nciStr = `${t.nci_from}->${t.nci_to}`.toLowerCase();
      return typeStr.includes(q) || pciStr.includes(q) || nciStr.includes(q);
    });
  }, [transitions, filterQuery]);

  // Extract distinct categorical labels for the active chart
  const { chartData, categoricalLevels } = useMemo(() => {
    const dataPoints: { x: number; val: string | number; label: string; ts: string }[] = [];
    const uniqueValues = new Set<string>();

    samples.forEach((s, idx) => {
      const rawVal = s[activeChart];
      const valStr = formatCellId(rawVal);
      if (valStr !== '—') {
        uniqueValues.add(valStr);
      }
      dataPoints.push({
        x: idx,
        val: valStr,
        label: valStr,
        ts: String(s.timestamp || ''),
      });
    });

    const sortedLevels = Array.from(uniqueValues).sort((a, b) => {
      const na = Number(a);
      const nb = Number(b);
      return !isNaN(na) && !isNaN(nb) ? na - nb : a.localeCompare(b);
    });

    return { chartData: dataPoints, categoricalLevels: sortedLevels };
  }, [samples, activeChart]);

  // SVG Chart Dimensions
  const svgWidth = 800;
  const svgHeight = 220;
  const padLeft = 90;
  const padRight = 30;
  const padTop = 20;
  const padBottom = 30;
  const plotWidth = svgWidth - padLeft - padRight;
  const plotHeight = svgHeight - padTop - padBottom;

  // Generate SVG path for stepped chart
  const stepPathD = useMemo(() => {
    if (chartData.length === 0 || categoricalLevels.length === 0) return '';

    const points: { x: number; y: number }[] = [];
    const levelCount = Math.max(categoricalLevels.length - 1, 1);

    chartData.forEach(p => {
      if (p.val === '—') return;
      const levelIdx = categoricalLevels.indexOf(p.val as string);
      if (levelIdx === -1) return;

      const normX = padLeft + (p.x / Math.max(chartData.length - 1, 1)) * plotWidth;
      const normY = padTop + plotHeight - (levelIdx / levelCount) * plotHeight;
      points.push({ x: normX, y: normY });
    });

    if (points.length === 0) return '';

    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      // Step: horizontal hold to points[i].x, then vertical transition to points[i].y
      d += ` H ${points[i].x} V ${points[i].y}`;
    }
    return d;
  }, [chartData, categoricalLevels, plotWidth, plotHeight, padLeft, padTop]);

  return (
    <div
      data-testid="cells-network-page"
      style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
    >
      {/* Page Header */}
      <div>
        <h1
          style={{
            fontSize: '22px',
            fontWeight: 700,
            marginBottom: '4px',
            color: 'var(--color-text)',
          }}
        >
          Cells & Network
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '14px', margin: 0 }}>
          Physical cell identity (PCI), NR cell identity (NCI), and carrier frequency timeline.
        </p>
      </div>

      {/* Operational Normal Behavior Note (Tech Rule / PRD requirement) */}
      <div
        data-testid="normal-behavior-note"
        style={{
          padding: '14px 18px',
          borderRadius: '8px',
          background: 'var(--color-surface)',
          borderLeft: '4px solid var(--color-primary, #3b82f6)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '4px' }}>
          Cell change is normal behaviour
        </div>
        <div style={{ fontSize: '13px', color: 'var(--color-text-muted)', lineHeight: '1.45' }}>
          PCI handovers and cell re-selections occur routinely during mobility and signal
          re-allocation. A cell change in isolation does NOT represent an anomaly or link
          failure (Guardrail G6/G21) and is never alerted without correlating radio degradation.
        </div>
      </div>

      {/* Key Serving Cell Metrics Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px',
        }}
      >
        <div
          style={{
            padding: '16px',
            background: 'var(--color-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>SERVING PCI</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text)' }}>
            {currentPci}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
            Physical Cell ID ({currentMode})
          </div>
        </div>

        <div
          style={{
            padding: '16px',
            background: 'var(--color-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>SERVING NCI</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text)' }}>
            {currentNci}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>NR Cell Identity</div>
        </div>

        <div
          style={{
            padding: '16px',
            background: 'var(--color-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>CARRIER NRARFCN</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text)' }}>
            {currentNrarfcn}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
            Frequency Channel
          </div>
        </div>

        <div
          style={{
            padding: '16px',
            background: 'var(--color-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
            TOTAL TRANSITIONS
          </div>
          <div
            data-testid="transition-count-badge"
            style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-primary)' }}
          >
            {transitions.length}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
            Strict bundle transition count (G30)
          </div>
        </div>
      </div>

      {/* Step Charts Section */}
      <div
        style={{
          padding: '20px',
          background: 'var(--color-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
          }}
        >
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
              Cell Level Step Chart
            </h2>
            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Discrete step graph holding cell identifier until transition (never interpolates)
            </span>
          </div>

          {/* Metric Selector Tabs */}
          <div style={{ display: 'flex', gap: '6px' }}>
            {(['pci', 'nci', 'nrarfcn'] as const).map(metric => (
              <button
                key={metric}
                onClick={() => setActiveChart(metric)}
                style={{
                  padding: '4px 12px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid var(--color-border)',
                  background:
                    activeChart === metric ? 'var(--color-primary)' : 'var(--color-bg)',
                  color: activeChart === metric ? '#fff' : 'var(--color-text)',
                }}
              >
                {metric.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Step Chart SVG */}
        <div style={{ width: '100%', overflowX: 'auto' }}>
          <svg
            data-testid="cell-step-chart"
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            style={{ width: '100%', height: 'auto', display: 'block' }}
          >
            {/* Grid & Categorical Level Labels */}
            {categoricalLevels.map((level, idx) => {
              const y =
                padTop +
                plotHeight -
                (idx / Math.max(categoricalLevels.length - 1, 1)) * plotHeight;
              return (
                <g key={level}>
                  <line
                    x1={padLeft}
                    y1={y}
                    x2={padLeft + plotWidth}
                    y2={y}
                    stroke="var(--color-border)"
                    strokeDasharray="3 3"
                    strokeWidth="1"
                  />
                  <text
                    x={padLeft - 8}
                    y={y + 4}
                    textAnchor="end"
                    fontSize="11"
                    fill="var(--color-text-muted)"
                  >
                    {level.length > 12 ? `${level.slice(0, 10)}...` : level}
                  </text>
                </g>
              );
            })}

            {/* Stepped Curve */}
            {stepPathD && (
              <path
                d={stepPathD}
                fill="none"
                stroke="var(--color-primary, #3b82f6)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="miter"
              />
            )}

            {/* Interactive Data Points */}
            {chartData.map(p => {
              const levelIdx = categoricalLevels.indexOf(p.val as string);
              if (levelIdx === -1) return null;
              const cx = padLeft + (p.x / Math.max(chartData.length - 1, 1)) * plotWidth;
              const cy =
                padTop +
                plotHeight -
                (levelIdx / Math.max(categoricalLevels.length - 1, 1)) * plotHeight;
              const isHovered = hoveredIndex === p.x;

              return (
                <circle
                  key={p.x}
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 5 : 2.5}
                  fill={isHovered ? '#ef4444' : 'var(--color-primary)'}
                  onMouseEnter={() => setHoveredIndex(p.x)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  style={{ cursor: 'pointer' }}
                />
              );
            })}
          </svg>
        </div>

        {/* Chart Hover Summary */}
        {hoveredIndex !== null && chartData[hoveredIndex] && (
          <div
            style={{
              marginTop: '10px',
              padding: '8px 12px',
              background: 'var(--color-bg)',
              borderRadius: '4px',
              fontSize: '12px',
              color: 'var(--color-text)',
            }}
          >
            Sample #{hoveredIndex} · {activeChart.toUpperCase()}:{' '}
            <strong>{chartData[hoveredIndex].val}</strong> · Timestamp:{' '}
            <strong>{chartData[hoveredIndex].ts}</strong>
          </div>
        )}
      </div>

      {/* Transition Log Table */}
      <div
        style={{
          padding: '20px',
          background: 'var(--color-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
              Bundle Transitions Table
            </h2>
            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Discrete cell and frequency transitions recorded in telemetry bundle (G30)
            </span>
          </div>

          {/* Filter Input */}
          <input
            type="text"
            placeholder="Filter transitions..."
            value={filterQuery}
            onChange={e => setFilterQuery(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              fontSize: '12px',
              minWidth: '200px',
            }}
          />
        </div>

        {/* Table Container */}
        <div style={{ overflowX: 'auto' }}>
          <table
            data-testid="transitions-table"
            style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid var(--color-border)',
                  color: 'var(--color-text-muted)',
                  textAlign: 'left',
                }}
              >
                <th style={{ padding: '8px' }}>Sample #</th>
                <th style={{ padding: '8px' }}>Timestamp</th>
                <th style={{ padding: '8px' }}>Type / Kind</th>
                <th style={{ padding: '8px' }}>PCI Transition</th>
                <th style={{ padding: '8px' }}>NCI Transition</th>
                <th style={{ padding: '8px' }}>NRARFCN Transition</th>
              </tr>
            </thead>
            <tbody>
              {filteredTransitions.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      padding: '24px',
                      textAlign: 'center',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    No cell or network transitions recorded for this session.
                  </td>
                </tr>
              ) : (
                filteredTransitions.map((t, idx) => {
                  const pciTrans =
                    t.pci_from !== undefined && t.pci_to !== undefined
                      ? `${formatCellId(t.pci_from)} -> ${formatCellId(t.pci_to)}`
                      : '—';
                  const nciTrans =
                    t.nci_from !== undefined && t.nci_to !== undefined
                      ? `${formatCellId(t.nci_from)} -> ${formatCellId(t.nci_to)}`
                      : '—';
                  const nrarfcnTrans =
                    t.nrarfcn_from !== undefined && t.nrarfcn_to !== undefined
                      ? `${formatCellId(t.nrarfcn_from)} -> ${formatCellId(t.nrarfcn_to)}`
                      : '—';

                  return (
                    <tr
                      key={idx}
                      style={{ borderBottom: '1px solid var(--color-border)' }}
                    >
                      <td style={{ padding: '8px', fontWeight: 600 }}>{t.sample_idx}</td>
                      <td style={{ padding: '8px', color: 'var(--color-text-muted)' }}>
                        {t.timestamp}
                      </td>
                      <td style={{ padding: '8px' }}>
                        <span
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: 'var(--color-bg)',
                            fontSize: '11px',
                            border: '1px solid var(--color-border)',
                          }}
                        >
                          {t.kind || t.type || 'Cell Change'}
                        </span>
                      </td>
                      <td style={{ padding: '8px' }}>{pciTrans}</td>
                      <td style={{ padding: '8px' }}>{nciTrans}</td>
                      <td style={{ padding: '8px' }}>{nrarfcnTrans}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
