export interface PageConfig {
  path: string;
  label: string;
  desc: string;
}

export const PAGES: PageConfig[] = [
  { path: '/overview', label: '1. Overview', desc: 'Real-time & replay diagnostic status, metrics, and multi-agent recommendations' },
  { path: '/signals', label: '2. Signal Explorer', desc: 'Four-panel stacked time series (SS-RSRP, SS-RSRQ, SS-SINR, IF score)' },
  { path: '/cells', label: '3. Cells & Network', desc: 'Discrete PCI/NCI transitions and carrier frequency timeline' },
  { path: '/events', label: '4. Events & Diagnosis', desc: 'Diagnosed events, provisional/final states, and multi-agent evidence' },
  { path: '/stream-health', label: '5. Stream Health', desc: 'Latency percentiles, clock skew, sequence completeness, and pipeline diagnostics' },
  { path: '/data-quality', label: '6. Data Quality', desc: 'Preprocess logs, validation drops, and device capability statistics' },
  { path: '/about', label: '7. About & Limitations', desc: 'Research positioning, system non-claims, and architectural disclaimers' },
];
