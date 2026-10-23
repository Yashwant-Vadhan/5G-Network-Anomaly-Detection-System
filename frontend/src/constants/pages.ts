export interface PageConfig {
  path: string;
  label: string;
  desc: string;
  group: 'MONITORING' | 'NETWORK DETAILS' | 'ADVANCED DIAGNOSTICS';
}

export const PAGES: PageConfig[] = [
  {
    path: '/overview',
    label: 'Overview',
    desc: 'Connection status, diagnosis, and practical recommendations',
    group: 'MONITORING',
  },
  {
    path: '/signals',
    label: 'Signal Trends',
    desc: 'Temporal signal strength, quality, and anomaly score trends',
    group: 'MONITORING',
  },
  {
    path: '/events',
    label: 'Events & Explanations',
    desc: 'Diagnosed events, plain-English explanations, and technical evidence',
    group: 'MONITORING',
  },
  {
    path: '/cells',
    label: 'Cell & Network',
    desc: 'Cell transitions, carrier frequency, and handover timeline',
    group: 'NETWORK DETAILS',
  },
  {
    path: '/stream-health',
    label: 'Stream Health',
    desc: 'Transport latency, clock skew, sequence gaps, and pipeline diagnostics',
    group: 'ADVANCED DIAGNOSTICS',
  },
  {
    path: '/data-quality',
    label: 'Data Quality',
    desc: 'Measurement completeness, CSI availability, and deployment statistics',
    group: 'ADVANCED DIAGNOSTICS',
  },
  {
    path: '/about',
    label: 'About & Limitations',
    desc: 'Research positioning, system non-claims, privacy, and model metadata',
    group: 'ADVANCED DIAGNOSTICS',
  },
];
