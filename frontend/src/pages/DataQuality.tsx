/**
 * Data Quality Page Component (T16-014).
 *
 * Implements:
 * - Missing-value counts per column and device (ss_rsrp, ss_rsrq, ss_sinr, csi_*,
 *   pci, nci, nrarfcn)
 * - CSI signal availability per device with hardware explanation
 * - Deployment mode distribution with verbatim UNKNOWN copy rule note
 * - Raw vs processed row counts and preprocessing rejection audit log
 * - Synthetic data banner when is_synthetic rows are present
 * - Strict Guardrail G30 compliance: zero client-side ML or transition computations
 */

import { useMemo } from 'react';
import { useData } from '../data/useData';
import { DemoBundle } from '../types/contracts';

export interface DataQualityProps {
  bundleOverride?: DemoBundle;
  samplesOverride?: Record<string, unknown>[];
}

interface MissingStats {
  device: string;
  total: number;
  ss_rsrp: { count: number; pct: number };
  ss_rsrq: { count: number; pct: number };
  ss_sinr: { count: number; pct: number };
  csi_rsrp: { count: number; pct: number };
  csi_rsrq: { count: number; pct: number };
  csi_sinr: { count: number; pct: number };
  pci: { count: number; pct: number };
  nci: { count: number; pct: number };
  nrarfcn: { count: number; pct: number };
}

interface DeploymentStats {
  device: string;
  nsa: number;
  sa: number;
  unknown: number;
  total: number;
}

export function DataQuality({ bundleOverride, samplesOverride }: DataQualityProps) {
  const { bundle: contextBundle, samples: contextSamples } = useData();

  const bundle = bundleOverride || contextBundle;

  // Extract all samples from bundle when available for full dataset quality view
  const samples = useMemo(() => {
    if (samplesOverride) return samplesOverride;
    if (bundle?.samples?.columns && bundle?.samples?.rows) {
      const cols = bundle.samples.columns;
      return bundle.samples.rows.map(row => {
        const obj: Record<string, unknown> = {};
        for (let i = 0; i < cols.length; i++) {
          obj[cols[i]] = row[i];
        }
        return obj;
      });
    }
    return contextSamples;
  }, [samplesOverride, bundle, contextSamples]);

  // Check if synthetic fixture rows are present in active selection
  const hasSynthetic = useMemo(() => {
    return samples.some(s => Boolean(s.is_synthetic));
  }, [samples]);

  // Aggregate missing values per device
  const missingByDevice = useMemo(() => {
    const devices = Array.from(new Set(samples.map(s => String(s.device || 'Unknown'))));
    const results: MissingStats[] = [];

    for (const dev of devices) {
      const devSamples = samples.filter(s => String(s.device || 'Unknown') === dev);
      const total = devSamples.length;

      const calcMissing = (col: string) => {
        const count = devSamples.filter(s => {
          const val = s[col];
          return val === null || val === undefined || val === '' || val === 'NA' || val === '<NA>';
        }).length;
        const pct = total > 0 ? (count / total) * 100 : 0;
        return { count, pct };
      };

      results.push({
        device: dev,
        total,
        ss_rsrp: calcMissing('ss_rsrp'),
        ss_rsrq: calcMissing('ss_rsrq'),
        ss_sinr: calcMissing('ss_sinr'),
        csi_rsrp: calcMissing('csi_rsrp'),
        csi_rsrq: calcMissing('csi_rsrq'),
        csi_sinr: calcMissing('csi_sinr'),
        pci: calcMissing('pci'),
        nci: calcMissing('nci'),
        nrarfcn: calcMissing('nrarfcn'),
      });
    }

    return results;
  }, [samples]);

  // CSI Availability per device
  const csiStats = useMemo(() => {
    const devices = Array.from(new Set(samples.map(s => String(s.device || 'Unknown'))));
    return devices.map(dev => {
      const devSamples = samples.filter(s => String(s.device || 'Unknown') === dev);
      const total = devSamples.length;
      const csiCount = devSamples.filter(s => {
        return s.csi_available === true || s.csi_rsrp !== null || s.csi_sinr !== null;
      }).length;
      const pct = total > 0 ? (csiCount / total) * 100 : 0;
      return { device: dev, total, csiCount, pct };
    });
  }, [samples]);

  // Deployment mode distribution
  const deploymentStats = useMemo(() => {
    const devices = Array.from(new Set(samples.map(s => String(s.device || 'Unknown'))));
    const stats: DeploymentStats[] = [];

    for (const dev of devices) {
      const devSamples = samples.filter(s => String(s.device || 'Unknown') === dev);
      let nsa = 0;
      let sa = 0;
      let unknown = 0;

      for (const s of devSamples) {
        const mode = String(s.deployment_mode || '').toUpperCase();
        if (mode === 'NSA') nsa++;
        else if (mode === 'SA') sa++;
        else unknown++;
      }

      stats.push({
        device: dev,
        nsa,
        sa,
        unknown,
        total: devSamples.length,
      });
    }

    return stats;
  }, [samples]);

  // Preprocessing audit log metrics
  const qualityBlock = bundle?.quality as Record<string, unknown> | undefined;
  const prepLog = qualityBlock?.preprocess_log as Record<string, unknown> | undefined;

  const rawRowsLoaded = (prepLog?.total_raw as number) ?? samples.length;
  const validRowsKept = (prepLog?.clean_rows as number) ?? samples.length;
  const invalidDropped = (prepLog?.dropped as number) ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1
          style={{
            fontSize: '22px',
            fontWeight: 700,
            color: 'var(--color-text)',
            marginBottom: '4px',
          }}
        >
          6. Data Quality
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '14px', margin: 0 }}>
          Inspect missing metrics, device quirks, deployment modes, and preprocessing logs.
        </p>
      </div>

      {/* Synthetic Data Banner */}
      {hasSynthetic && (
        <div
          role="alert"
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            background: 'rgba(234, 179, 8, 0.15)',
            border: '1px solid var(--color-warning, #eab308)',
            color: 'var(--color-text)',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>⚠️</span>
          <div>
            <strong>Synthetic Data Banner:</strong> This selection contains synthetic edge-case
            fixture rows (<code>is_synthetic = True</code>).
          </div>
        </div>
      )}

      {/* 1. Preprocessing Summary Metrics */}
      <section
        aria-label="Preprocessing log metrics"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: 'var(--color-text)',
            marginBottom: '16px',
          }}
        >
          Preprocessing Audit Log
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
          }}
        >
          <div
            style={{
              padding: '16px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Raw Rows Loaded
            </div>
            <div
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginTop: '4px',
              }}
            >
              {rawRowsLoaded.toLocaleString()}
            </div>
          </div>

          <div
            style={{
              padding: '16px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Valid Rows Kept
            </div>
            <div
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: 'var(--color-success, #22c55e)',
                marginTop: '4px',
              }}
            >
              {validRowsKept.toLocaleString()}
            </div>
          </div>

          <div
            style={{
              padding: '16px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Invalid Rows Dropped
            </div>
            <div
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color:
                  invalidDropped > 0 ? 'var(--color-danger, #ef4444)' : 'var(--color-text-muted)',
                marginTop: '4px',
              }}
            >
              {invalidDropped.toLocaleString()}
            </div>
          </div>
        </div>
      </section>

      {/* 2. Missing Value Counts per Column & Device */}
      <section
        aria-label="Missing value counts table"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: 'var(--color-text)',
            marginBottom: '8px',
          }}
        >
          Missing-Value Counts per Column & Device
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
          Unreported readings (NA or sentinel 2147483647) are strictly preserved as missing and
          never imputed as zero.
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px',
              textAlign: 'left',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>Device</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>Samples</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>SS-RSRP</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>SS-RSRQ</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>SS-SINR</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>CSI-RSRP</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>CSI-RSRQ</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>CSI-SINR</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>PCI</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>NCI</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>NRARFCN</th>
              </tr>
            </thead>
            <tbody>
              {missingByDevice.map(row => (
                <tr key={row.device} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text)' }}>
                    {row.device}
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.total.toLocaleString()}
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.ss_rsrp.count} ({row.ss_rsrp.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.ss_rsrq.count} ({row.ss_rsrq.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.ss_sinr.count} ({row.ss_sinr.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.csi_rsrp.count} ({row.csi_rsrp.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.csi_rsrq.count} ({row.csi_rsrq.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.csi_sinr.count} ({row.csi_sinr.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.pci.count} ({row.pci.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.nci.count} ({row.nci.pct.toFixed(1)}%)
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.nrarfcn.count} ({row.nrarfcn.pct.toFixed(1)}%)
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 3. CSI Signal Availability */}
      <section
        aria-label="CSI availability breakdown"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: 'var(--color-text)',
            marginBottom: '8px',
          }}
        >
          CSI Signal Availability
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
          Channel State Information (CSI) is optional in Android telephony and unsupported by some
          modems. CSI presence is tracked for diagnostic reporting, but is strictly excluded from
          anomaly detection features.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px',
          }}
        >
          {csiStats.map(item => (
            <div
              key={item.device}
              style={{
                padding: '16px',
                borderRadius: '6px',
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: '8px' }}>
                {item.device}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>CSI Available:</span>
                <strong style={{ color: 'var(--color-text)' }}>{item.pct.toFixed(1)}%</strong>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  marginTop: '4px',
                }}
              >
                <span style={{ color: 'var(--color-text-muted)' }}>Valid Samples:</span>
                <span style={{ color: 'var(--color-text-muted)' }}>
                  {item.csiCount} / {item.total}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. Deployment Mode Distribution with Copy Rule Note */}
      <section
        aria-label="Deployment mode distribution"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: 'var(--color-text)',
            marginBottom: '8px',
          }}
        >
          Deployment Mode Distribution
        </h2>

        {/* Verbatim Copy Rule Note (Acceptance Criteria) */}
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '6px',
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid var(--color-primary, #3b82f6)',
            color: 'var(--color-text)',
            fontSize: '13px',
            marginBottom: '16px',
          }}
        >
          💡 <strong>Copy Rule Note:</strong> UNKNOWN means Android did not expose enough
          information. It does not mean SA.
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px',
              textAlign: 'left',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>Device</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>NSA</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>SA</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>UNKNOWN</th>
                <th style={{ padding: '8px 12px', color: 'var(--color-text-muted)' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {deploymentStats.map(row => (
                <tr key={row.device} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text)' }}>
                    {row.device}
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.nsa.toLocaleString()}
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.sa.toLocaleString()}
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-text)' }}>
                    {row.unknown.toLocaleString()}
                  </td>
                  <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text)' }}>
                    {row.total.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
