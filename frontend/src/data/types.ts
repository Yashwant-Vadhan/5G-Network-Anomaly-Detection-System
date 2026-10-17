import { BundleSession, BundleTransition, DemoBundle, EventRecord } from '../types/contracts';

export interface DataContextValue {
  bundle: DemoBundle | null;
  loading: boolean;
  error: string | null;
  devices: string[];
  operators: string[];
  sessions: BundleSession[];
  selectedDevice: string | 'all';
  selectedOperator: string | 'all';
  selectedSessionId: string | 'all';
  currentSession: BundleSession | null;
  samples: Record<string, unknown>[];
  events: EventRecord[];
  transitions: BundleTransition[];
  setSelectedDevice: (device: string | 'all') => void;
  setSelectedOperator: (operator: string | 'all') => void;
  setSelectedSessionId: (sessionId: string | 'all') => void;
  reloadBundle: (customBundle?: DemoBundle) => void;
}
