/**
 * React Data Context & State Management for Demo Data (T16-008).
 *
 * Provides reactive access to loaded demo bundle data, filtered sessions,
 * and current active selections across pages.
 */

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { DemoBundle } from '../types/contracts';
import { fetchDemoBundle, loadAndValidateBundle } from './bundleLoader';
import {
  getDevices,
  getOperators,
  getFilteredSessions,
  getSamplesForSession,
  getEventsForSession,
  getTransitionsForSession,
} from './selectors';
import { DataContextValue } from './types';
import { DataContext } from './useData';

export interface DataProviderProps {
  children: React.ReactNode;
  initialBundle?: DemoBundle | null;
  bundleUrl?: string;
}

export const DataProvider: React.FC<DataProviderProps> = ({
  children,
  initialBundle = null,
  bundleUrl = '/data/demo_bundle.json',
}) => {
  const [bundle, setBundle] = useState<DemoBundle | null>(initialBundle);
  const [loading, setLoading] = useState<boolean>(!initialBundle);
  const [error, setError] = useState<string | null>(null);

  const [selectedDevice, setSelectedDevice] = useState<string | 'all'>('all');
  const [selectedOperator, setSelectedOperator] = useState<string | 'all'>('all');
  const [selectedSessionId, setSelectedSessionId] = useState<string | 'all'>('all');

  const reloadBundle = useCallback(
    (customBundle?: DemoBundle) => {
      if (customBundle) {
        const res = loadAndValidateBundle(customBundle);
        if (res.error) {
          setError(res.error);
          setBundle(null);
        } else {
          setBundle(res.bundle);
          setError(null);
        }
        setLoading(false);
        return;
      }

      setLoading(true);
      fetchDemoBundle(bundleUrl).then(res => {
        setBundle(res.bundle);
        setError(res.error);
        setLoading(false);
      });
    },
    [bundleUrl]
  );

  useEffect(() => {
    if (!initialBundle) {
      reloadBundle();
    }
  }, [initialBundle, reloadBundle]);

  const devices = useMemo(() => getDevices(bundle), [bundle]);
  const operators = useMemo(
    () => getOperators(bundle, selectedDevice),
    [bundle, selectedDevice]
  );

  const sessions = useMemo(() => {
    return getFilteredSessions(bundle, {
      device: selectedDevice,
      operator: selectedOperator,
    });
  }, [bundle, selectedDevice, selectedOperator]);

  // Keep selectedSessionId in sync with filtered sessions
  useEffect(() => {
    if (sessions.length > 0) {
      if (selectedSessionId === 'all' || !sessions.some(s => s.session_id === selectedSessionId)) {
        setSelectedSessionId(sessions[0].session_id);
      }
    } else {
      setSelectedSessionId('all');
    }
  }, [sessions, selectedSessionId]);

  const currentSession = useMemo(() => {
    if (!bundle || selectedSessionId === 'all') return null;
    return bundle.sessions.find(s => s.session_id === selectedSessionId) || null;
  }, [bundle, selectedSessionId]);

  const samples = useMemo(
    () => getSamplesForSession(bundle, selectedSessionId),
    [bundle, selectedSessionId]
  );

  const events = useMemo(
    () => getEventsForSession(bundle, selectedSessionId),
    [bundle, selectedSessionId]
  );

  const transitions = useMemo(
    () => getTransitionsForSession(bundle, selectedSessionId),
    [bundle, selectedSessionId]
  );

  const value: DataContextValue = {
    bundle,
    loading,
    error,
    devices,
    operators,
    sessions,
    selectedDevice,
    selectedOperator,
    selectedSessionId,
    currentSession,
    samples,
    events,
    transitions,
    setSelectedDevice,
    setSelectedOperator,
    setSelectedSessionId,
    reloadBundle,
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
};
