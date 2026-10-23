/**
 * About & Limitations Page Component (Phase 13 / T16-015).
 *
 * Implements:
 * 1. About 5G-NADS
 * 2. How It Works (Passive telemetry, dual-tier processing)
 * 3. Data and Privacy (G27, G28, G29 compliance)
 * 4. Detection Methods (Isolation Forest + Rolling Z-Score explained simply with technical expanders)
 * 5. System Limitations & 13 Explicit Non-Claims (PRD_v2 / TECH_RULES_v2)
 * 6. Technical Information & Reconciled Dataset Sample Counts
 *
 * Reconciled sample counts:
 * - 5,528: Total Evaluation Dataset across academic research experiments (3,756 Redmi + 1,772 Samsung)
 * - Loaded Session: Dynamic sample count currently in frontend memory
 */

import { useData } from '../data/useData';
import { DemoBundle } from '../types/contracts';

export interface AboutProps {
  bundleOverride?: DemoBundle;
}

export function About({ bundleOverride }: AboutProps) {
  const { bundle: contextBundle, samples, currentSession } = useData();
  const bundle = bundleOverride || contextBundle;

  const modelMeta = bundle?.model_meta as Record<string, unknown> | undefined;
  const privacy = bundle?.privacy;

  const activeLoadedCount = currentSession?.n ?? samples.length;

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
          aria-label="7. About & Limitations"
        >
          7. About & Limitations
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '14px', margin: 0 }}>
          Research positioning, system non-claims, privacy architecture, and model metadata.
        </p>
      </div>

      {/* Mandatory Research Prototype Callout (Guardrail G31) */}
      <div
        role="region"
        aria-label="Research prototype notice"
        style={{
          padding: '16px 20px',
          borderRadius: '8px',
          background: 'rgba(59, 130, 246, 0.1)',
          border: '1px solid var(--color-primary, #3b82f6)',
          color: 'var(--color-text)',
          fontSize: '14px',
          lineHeight: '1.6',
        }}
      >
        <strong>Research Prototype Statement (G31):</strong> 5G-NADS is an exploratory academic
        research prototype developed at Anna University. It is <em>not</em> an operator-grade,
        commercial, or operational network detector. It performs passive, near-real-time monitoring
        of User Equipment (UE) side metrics with no hard latency guarantee, and cannot control or
        modify the cellular operator network in any way.
      </div>

      {/* Section 1: About 5G-NADS */}
      <section
        aria-label="About 5G-NADS overview"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '8px' }}>
          1. About 5G-NADS
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--color-text-secondary, var(--color-text))', lineHeight: '1.6', margin: 0 }}>
          5G Network Anomaly Detection and Diagnosis System (5G-NADS) is an end-to-end framework designed to diagnose
          and explain radio degradation and connectivity anomalies using non-intrusive mobile measurements. It provides
          both everyday users with clear, jargon-free explanations of their mobile connection quality, and telecom researchers
          with deep 3GPP telemetry evidence.
        </p>
      </section>

      {/* Section 2: How It Works */}
      <section
        aria-label="How it works"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '12px' }}>
          2. How It Works
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
          <div style={{ padding: '14px', background: 'var(--color-bg)', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text)', marginBottom: '6px' }}>
              📡 1. Passive Telemetry Capture
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
              The Android client collects standard 3GPP radio metrics (SS-RSRP, SS-RSRQ, SS-SINR, PCI, NCI) at 1 Hz intervals via standard public telephony APIs.
            </div>
          </div>
          <div style={{ padding: '14px', background: 'var(--color-bg)', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text)', marginBottom: '6px' }}>
              🧠 2. Dual-Layer Anomaly Detection
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
              Telemetry passes through a server-side statistical rolling Z-score baseline filter and a pre-trained unsupervised Isolation Forest model in near-real-time.
            </div>
          </div>
          <div style={{ padding: '14px', background: 'var(--color-bg)', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text)', marginBottom: '6px' }}>
              📋 3. Deterministic Diagnosis & Plain English
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
              A 5-agent diagnosis pipeline analyzes temporal windows and cell transitions, transforming technical anomalies into actionable plain-English user recommendations.
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Data and Privacy */}
      <section
        aria-label="Privacy architecture note"
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
          3. Privacy & Data Minimization Architecture (G27, G28)
        </h2>
        <ul
          style={{
            fontSize: '13px',
            color: 'var(--color-text-muted)',
            lineHeight: '1.7',
            paddingLeft: '20px',
            margin: 0,
          }}
        >
          <li>
            <strong>Zero PII Collection:</strong> No phone numbers, subscriber IMSI/IMEI, call logs,
            browsing traffic, or precise GPS coordinates are ever collected or stored.
          </li>
          <li>
            <strong>Cell Identifier Anonymization:</strong> In public demo mode, physical cell
            identities (PCI, NCI) are cryptographically salted and HMAC-hashed
            ({privacy?.cell_ids === 'hashed' ? 'Active' : 'Configured'}),
            and mapped to human-friendly pseudonyms (e.g. <code>Cell-A</code>).
          </li>
          <li>
            <strong>Timezone Scrubbing:</strong> Sample timestamps are stored in device-local time
            without geographical timezone offsets to prevent geolocation correlation.
          </li>
          <li>
            <strong>Zero Public Disk Retention (G29):</strong> In public paired mode, telemetry is
            processed in-memory and purged immediately upon session teardown.
          </li>
        </ul>
      </section>

      {/* Section 4: Detection Methods (Simplified + Expandable) */}
      <section
        aria-label="Detection methods"
        style={{
          background: 'var(--color-surface)',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '12px' }}>
          4. Detection Methods
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
          <div style={{ padding: '12px', background: 'var(--color-bg)', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: '4px' }}>
              🌲 Isolation Forest (Machine Learning)
            </div>
            <p style={{ margin: 0, color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
              <strong>Plain language:</strong> An intelligent algorithm that learns what normal signal measurements look like and flags unusual combinations that deviate from standard behavior.
            </p>
            <details style={{ marginTop: '8px' }}>
              <summary style={{ cursor: 'pointer', color: 'var(--color-primary, #3b82f6)', fontSize: '12px', fontWeight: 500 }}>
                Expand technical details
              </summary>
              <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
                Unsupervised ensemble of isolation decision trees trained on normalized 3GPP radio features (SS-RSRP, SS-RSRQ, SS-SINR). Points requiring fewer partition splits to isolate receive higher anomaly scores. Target contamination factor: 5%.
              </div>
            </details>
          </div>

          <div style={{ padding: '12px', background: 'var(--color-bg)', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: '4px' }}>
              📊 Rolling Z-Score (Statistical Baseline)
            </div>
            <p style={{ margin: 0, color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
              <strong>Plain language:</strong> Continuously checks if current signal strength drops rapidly compared to your phone&apos;s recent average readings over the last several seconds.
            </p>
            <details style={{ marginTop: '8px' }}>
              <summary style={{ cursor: 'pointer', color: 'var(--color-primary, #3b82f6)', fontSize: '12px', fontWeight: 500 }}>
                Expand technical details
              </summary>
              <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
                Computes running mean (μ) and standard deviation (σ) over rolling 30-sample sliding windows. Identifies sharp localized drops exceeding <code>Z &gt; 2.5</code> standard deviations from the moving baseline.
              </div>
            </details>
          </div>
        </div>
      </section>

      {/* Section 5: System Limitations & Explicit Non-Claims */}
      <section
        aria-label="Explicit non-claims list"
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
            marginBottom: '12px',
          }}
        >
          ⚠️ 5. System Limitations & Explicit Non-Claims (PRD_v2 & TECH_RULES_v2)
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
          5G-NADS explicitly does not claim to provide any of the following capabilities:
        </p>

        <ol
          style={{
            fontSize: '13px',
            color: 'var(--color-text)',
            lineHeight: '1.8',
            paddingLeft: '20px',
            margin: 0,
          }}
        >
          <li>
            <strong>Not Universal 5G Detection:</strong> Detection capabilities are bounded to the
            evaluated scenarios and devices, not guaranteed across all global 5G deployments.
          </li>
          <li>
            <strong>No Guaranteed Root Cause:</strong> Attributions are correlation-based hypotheses
            derived from UE measurements; correlation does not imply causality.
          </li>
          <li>
            <strong>No Inferred Architecture:</strong> If Android reports network mode as{' '}
            <code>UNKNOWN</code>, it remains <code>UNKNOWN</code>. It is never inferred to be SA.
          </li>
          <li>
            <strong>No Operator Network Control:</strong> The system strictly performs passive
            monitoring and does not optimize, manipulate, or modify cellular network parameters.
          </li>
          <li>
            <strong>No Universal Thresholds:</strong> Radio degradation boundaries reflect the local
            environment and are not universal physical laws across carriers.
          </li>
          <li>
            <strong>Not Every Cell Transition is Anomalous:</strong> Routine cell reselection,
            handover, and secondary cell additions are normal cellular network management events.
          </li>
          <li>
            <strong>Measurement Path Performs No Heavy ML:</strong> Android collection is
            deterministic; on-device edge scoring is advisory, with server analysis authoritative.
          </li>
          <li>
            <strong>No Hard Latency Guarantees:</strong> Monitoring operates near-real-time;
            reported latency metrics represent empirical figures on tested hardware setups.
          </li>
          <li>
            <strong>Not a Safety or Outage Notification System:</strong> Generated alerts are not
            designed for emergency communications or life-safety critical workflows.
          </li>
          <li>
            <strong>No Carrier Infrastructure Visibility:</strong> The system has no access to
            gNodeB internals, AMF/UPF logs, or fiber backhaul states.
          </li>
          <li>
            <strong>Live Results are Provisional:</strong> Real-time in-flight events remain
            provisional until an event window closes and complete temporal context is assembled.
          </li>
          <li>
            <strong>External Protocols Not Implemented:</strong> O-RAN xApps, iOS collection,
            and SMS alerts are explicitly <strong>NOT IMPLEMENTED</strong>.
          </li>
          <li>
            <strong>Academic Research Prototype:</strong> Designed for scientific evaluation and
            coursework, not commercial deployment.
          </li>
        </ol>
      </section>

      {/* Section 6: Technical Information & Reconciled Dataset Metrics */}
      <section
        aria-label="Dataset summary"
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
            marginBottom: '12px',
          }}
        >
          6. Technical Information & Reconciled Dataset Metrics
        </h2>
        <p
          style={{
            fontSize: '13px',
            color: 'var(--color-text-muted)',
            lineHeight: '1.6',
            marginBottom: '16px',
          }}
        >
          To maintain honest data reporting (Phase 13.1), evaluation dataset counts are distinguished
          from currently active in-memory session frames:
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
          }}
        >
          <div
            style={{
              padding: '14px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Total Valid Samples (Research Evaluation)
            </div>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginTop: '4px',
              }}
            >
              5,528
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              Redmi (3,756) · Samsung (1,772)
            </div>
          </div>

          <div
            style={{
              padding: '14px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Hardware Diversity
            </div>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginTop: '4px',
              }}
            >
              2 Phones
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              Xiaomi Redmi 13 5G · Samsung A15 5G
            </div>
          </div>

          <div
            style={{
              padding: '14px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Carrier Environment
            </div>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginTop: '4px',
              }}
            >
              Airtel 5G NSA
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              Band n78 (3500 MHz) · NR-ARFCN 629952
            </div>
          </div>

          <div
            style={{
              padding: '14px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Current Loaded Session Samples
            </div>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 700,
                color: 'var(--color-primary, #3b82f6)',
                marginTop: '4px',
              }}
            >
              {activeLoadedCount.toLocaleString()}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              Active in frontend memory
            </div>
          </div>
        </div>

        {/* Model metadata region */}
        <div
          role="region"
          aria-label="Model metadata"
          style={{
            marginTop: '16px',
            paddingTop: '16px',
            borderTop: '1px solid var(--color-border)',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px',
            fontSize: '13px',
          }}
        >
          <div
            style={{
              padding: '12px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ color: 'var(--color-text-muted)' }}>Model Architecture:</span>{' '}
            <strong style={{ color: 'var(--color-text)' }}>
              {String(modelMeta?.model_name || 'if_v1')}
            </strong>
          </div>

          <div
            style={{
              padding: '12px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ color: 'var(--color-text-muted)' }}>Contamination Factor:</span>{' '}
            <strong style={{ color: 'var(--color-text)' }}>
              {String(modelMeta?.contamination ?? '0.05')}
            </strong>
          </div>

          <div
            style={{
              padding: '12px',
              borderRadius: '6px',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ color: 'var(--color-text-muted)' }}>Diagnostic Agents:</span>{' '}
            <strong style={{ color: 'var(--color-text)' }}>
              5 Deterministic Agents (Zero LLM in runtime path)
            </strong>
          </div>
        </div>
      </section>
    </div>
  );
}
