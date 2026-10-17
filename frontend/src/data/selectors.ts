/**
 * Typed Selectors for Demo Bundle Data (T16-008).
 *
 * Adheres strictly to Guardrail G30: NO scores, flags, anomaly thresholds,
 * or statistical calculations are recomputed on the frontend.
 */

import {
  BundleSession,
  BundleTransition,
  DemoBundle,
  EventRecord,
} from '../types/contracts';

export interface SessionFilter {
  device?: string | 'all';
  operator?: string | 'all';
}

export function getDevices(bundle: DemoBundle | null): string[] {
  if (!bundle) return [];
  const devices = new Set<string>();
  for (const s of bundle.sessions) {
    if (s.device) {
      devices.add(s.device);
    }
  }
  return Array.from(devices).sort();
}

export function getOperators(
  bundle: DemoBundle | null,
  deviceFilter?: string | 'all'
): string[] {
  if (!bundle) return [];
  const operators = new Set<string>();
  for (const s of bundle.sessions) {
    if (!deviceFilter || deviceFilter === 'all' || s.device === deviceFilter) {
      if (s.operator) {
        operators.add(s.operator);
      }
    }
  }
  return Array.from(operators).sort();
}

export function getFilteredSessions(
  bundle: DemoBundle | null,
  filter?: SessionFilter
): BundleSession[] {
  if (!bundle) return [];
  return bundle.sessions.filter(s => {
    if (filter?.device && filter.device !== 'all' && s.device !== filter.device) {
      return false;
    }
    if (
      filter?.operator &&
      filter.operator !== 'all' &&
      s.operator !== filter.operator
    ) {
      return false;
    }
    return true;
  });
}

export function getSamplesForSession(
  bundle: DemoBundle | null,
  sessionId: string | 'all'
): Record<string, unknown>[] {
  if (!bundle || !bundle.samples || !bundle.samples.columns || !bundle.samples.rows) {
    return [];
  }

  const cols = bundle.samples.columns;
  const sessionIdx = cols.indexOf('session_id');

  const rows: Record<string, unknown>[] = [];
  for (const r of bundle.samples.rows) {
    if (sessionIdx >= 0 && sessionId !== 'all') {
      if (r[sessionIdx] !== sessionId) {
        continue;
      }
    }
    const obj: Record<string, unknown> = {};
    for (let c = 0; c < cols.length; c++) {
      obj[cols[c]] = r[c];
    }
    rows.push(obj);
  }
  return rows;
}

export function getEventsForSession(
  bundle: DemoBundle | null,
  sessionId: string | 'all'
): EventRecord[] {
  if (!bundle || !Array.isArray(bundle.events)) return [];
  if (sessionId === 'all') return bundle.events as EventRecord[];
  return (bundle.events as EventRecord[]).filter(e => e.session_id === sessionId);
}

export function getTransitionsForSession(
  bundle: DemoBundle | null,
  sessionId: string | 'all'
): BundleTransition[] {
  if (!bundle || !Array.isArray(bundle.transitions)) return [];
  if (sessionId === 'all') return bundle.transitions;
  return bundle.transitions.filter(t => t.session_id === sessionId);
}

export function getDataQuality(bundle: DemoBundle | null): Record<string, unknown> {
  return bundle?.quality || {};
}

export function getModelMeta(bundle: DemoBundle | null): Record<string, unknown> {
  return bundle?.model_meta || {};
}
