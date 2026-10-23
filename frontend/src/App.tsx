import { useState, useEffect, useMemo } from 'react';
import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { PAGES } from './constants/pages';
import { DataProvider } from './data/DataContext';
import { useData } from './data/useData';
import { ConnectionState, ScoredSample, EventRecord, CreateLiveSessionResponse, DemoBundle } from './types/contracts';
import { Overview } from './pages/Overview';
import { SignalExplorer } from './pages/SignalExplorer';
import { CellsNetwork } from './pages/CellsNetwork';
import { EventsDiagnosis } from './pages/EventsDiagnosis';
import { StreamHealth } from './pages/StreamHealth';
import { DataQuality } from './pages/DataQuality';
import { About } from './pages/About';
import { ReplayProvider, useReplay } from './data/ReplayContext';
import { ReplayPlayer } from './components/ReplayPlayer';
import { ConnectionChip } from './components/ConnectionChip';
import { PairingPanel } from './components/PairingPanel';
import { LiveClient, fetchViewerTicket } from './data/liveClient';

export function sanitizeErrorMessage(err: unknown): string {
  if (!err) return '';
  const msg =
    typeof err === 'string' ? err : err instanceof Error ? err.message : String(err);
  if (
    msg.includes('Traceback') ||
    msg.includes('File "') ||
    (msg.includes('line ') && msg.includes('in ')) ||
    msg.includes('Exception:') ||
    (msg.includes('Error:') && msg.includes('.py'))
  ) {
    return 'A server processing error occurred. Check backend logs.';
  }
  return msg;
}

interface AppContentProps {
  initialMode?: 'demo' | 'live';
  initialConnectionState?: ConnectionState;
  initialSessionId?: string | null;
  fetchFn?: typeof fetch;
  enableLiveClientInTest?: boolean;
}

function AppContent({
  initialMode = 'demo',
  initialConnectionState = 'REPLAY-SOURCE',
  initialSessionId = null,
  fetchFn = typeof fetch !== 'undefined' ? fetch : undefined,
  enableLiveClientInTest = false,
}: AppContentProps) {
  const [mode, setMode] = useState<'demo' | 'live'>(() => {
    if (initialMode === 'live') return 'live';
    if (typeof window !== 'undefined' && typeof sessionStorage !== 'undefined') {
      const savedMode = sessionStorage.getItem('nads_mode') as 'demo' | 'live' | null;
      if (savedMode === 'live' || savedMode === 'demo') return savedMode;
      if (sessionStorage.getItem('nads_active_session_id')) return 'live';
    }
    return initialMode;
  });
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    if (initialSessionId) return initialSessionId;
    if (typeof window !== 'undefined' && typeof sessionStorage !== 'undefined') {
      return sessionStorage.getItem('nads_active_session_id');
    }
    return null;
  });
  const [liveConnectionState, setLiveConnectionState] =
    useState<ConnectionState>(initialConnectionState);
  const [liveErrorMessage, setLiveErrorMessage] = useState<string | null>(null);
  const [isPairingOpen, setIsPairingOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [liveSamples, setLiveSamples] = useState<ScoredSample[]>([]);
  const [liveEvents, setLiveEvents] = useState<EventRecord[]>([]);

  useEffect(() => {
    if (
      mode !== 'live' ||
      !activeSessionId ||
      typeof window === 'undefined' ||
      (import.meta.env.MODE === 'test' && !enableLiveClientInTest)
    ) {
      return;
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host || '127.0.0.1:3000';
      const wsUrl = `${protocol}//${host}/api/v1/live`;
      const httpBaseUrl = window.location.origin || 'http://127.0.0.1:3000';

      const client = new LiveClient({
        wsUrl,
        httpBaseUrl,
        staleTimeoutMs: 15000,
        fetchFn,
        getTicket: () => fetchViewerTicket(httpBaseUrl, activeSessionId, fetchFn),
      });

      const unsubscribe = client.subscribe({
        onStateChange: state => {
          setLiveConnectionState(state);
          if (state === 'LIVE') {
            setIsPairingOpen(false);
          }
        },
        onSample: sample => {
          setIsPairingOpen(false);
          setLiveSamples(prev => {
            if (prev.some(s => s.seq === sample.seq)) return prev;
            return [...prev, sample];
          });
        },
        onSnapshot: async snap => {
          if (activeSessionId) {
            try {
              const fetcher = fetchFn || (typeof fetch !== 'undefined' ? fetch : undefined);
              if (fetcher) {
                const res = await fetcher(
                  `${httpBaseUrl}/api/v1/sessions/${encodeURIComponent(activeSessionId)}/samples?limit=1000`
                );
                if (res.ok) {
                  const data = await res.json();
                  if (data.samples && Array.isArray(data.samples) && data.samples.length > 0) {
                    setLiveSamples(data.samples);
                  } else if (snap.latest_sample) {
                    setLiveSamples([snap.latest_sample]);
                  }
                }
              }
            } catch {
              if (snap.latest_sample) {
                setLiveSamples(prev => {
                  if (prev.some(s => s.seq === snap.latest_sample?.seq)) return prev;
                  return [...prev, snap.latest_sample!];
                });
              }
            }
          } else if (snap.latest_sample) {
            setLiveSamples(prev => {
              if (prev.some(s => s.seq === snap.latest_sample?.seq)) return prev;
              return [...prev, snap.latest_sample!];
            });
          }
          if (snap.open_events && snap.open_events.length > 0) {
            setLiveEvents(snap.open_events);
          }
        },
        onEvent: event => {
          setLiveEvents(prev => {
            const idx = prev.findIndex(e => e.event_id === event.event_id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = event;
              return next;
            }
            return [...prev, event];
          });
        },
        onError: err => {
          setLiveErrorMessage(sanitizeErrorMessage(err));
        },
      });

      client.connect();

      return () => {
        unsubscribe();
        client.disconnect();
      };
    } catch {
      // In testing environments where WebSocket is mocked or unavailable
    }
  }, [mode, activeSessionId, fetchFn, enableLiveClientInTest]);

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('nads_theme') as 'light' | 'dark') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('nads_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  const {
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
    setSelectedDevice,
    setSelectedOperator,
    setSelectedSessionId,
  } = useData();

  const { currentSample, prevSample } = useReplay();

  // Dynamically merge connected phone devices from live telemetry stream
  const allDevices = useMemo(() => {
    const set = new Set<string>(devices);
    if (set.has('2406ERN9CI') || set.has('2406ERN9C1')) {
      set.add('Redmi 13 5G');
    }
    set.add('Samsung Galaxy A15 5G');
    set.add('SM-A156E');
    liveSamples.forEach(s => {
      if (s.device) set.add(String(s.device));
    });
    return Array.from(set);
  }, [devices, liveSamples]);

  // Distinct navigation section groups per Phase 3.1
  const navGroups: Array<'MONITORING' | 'NETWORK DETAILS' | 'ADVANCED DIAGNOSTICS'> = [
    'MONITORING',
    'NETWORK DETAILS',
    'ADVANCED DIAGNOSTICS',
  ];

  return (
    <div
      className="app-shell"
      style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}
    >
      {/* Brand Header */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '14px 24px',
          background: 'var(--color-surface)',
          borderBottom: '1px solid var(--color-border)',
          position: 'sticky',
          top: 0,
          zIndex: 30,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Mobile hamburger menu toggle */}
          <button
            type="button"
            aria-label="Toggle navigation menu"
            onClick={() => setIsMobileNavOpen(prev => !prev)}
            style={{
              display: 'none',
              padding: '6px 10px',
              borderRadius: '6px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              cursor: 'pointer',
              fontSize: '14px',
            }}
            className="mobile-nav-toggle"
          >
            ☰
          </button>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '20px', fontWeight: 800, color: 'var(--color-primary)', letterSpacing: '-0.02em' }}>
              5G-NADS
            </span>
            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', display: 'none' }} className="brand-subtitle">
              Network Anomaly Detection
            </span>
          </div>

          <div
            data-testid="mode-badge"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              padding: '3px 10px',
              borderRadius: '9999px',
              background: 'var(--color-bg)',
              color: 'var(--color-text-muted)',
              border: '1px solid var(--color-border)',
              fontWeight: 500,
            }}
          >
            <span data-testid="mode-label">
              {mode === 'demo'
                ? 'DEMO MODE · Recorded demo data'
                : liveConnectionState === 'LIVE'
                ? 'LIVE MODE · Receiving measurements (Live)'
                : liveConnectionState === 'WAITING'
                ? 'LIVE MODE · Waiting for phone (Live)'
                : liveConnectionState === 'RECONNECTING'
                ? 'LIVE MODE · Reconnecting (Live)'
                : liveConnectionState === 'STALE'
                ? 'LIVE MODE · Telemetry delayed (Live)'
                : 'LIVE MODE · Connection interrupted (Live)'}
            </span>
            {mode === 'demo' && <span>Static Demo (Mode 1)</span>}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            data-testid="mode-switch-btn"
            onClick={() => {
              setMode(prev => {
                const next = prev === 'demo' ? 'live' : 'demo';
                if (typeof sessionStorage !== 'undefined') {
                  sessionStorage.setItem('nads_mode', next);
                }
                if (next === 'live' && liveConnectionState === 'REPLAY-SOURCE') {
                  setLiveConnectionState('WAITING');
                }
                return next;
              });
            }}
            aria-label={`Switch to ${mode === 'demo' ? 'Live' : 'Demo'} mode`}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: '1px solid var(--color-border)',
              background:
                mode === 'live' ? 'var(--color-primary, #0284c7)' : 'var(--color-surface)',
              color: mode === 'live' ? '#ffffff' : 'var(--color-text)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
              transition: 'background 0.15s ease',
            }}
          >
            {mode === 'demo' ? 'Switch to Live' : 'Switch to Demo'}
          </button>
          {mode === 'live' && (
            <button
              data-testid="pair-phone-btn"
              onClick={() => setIsPairingOpen(prev => !prev)}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                background: isPairingOpen ? 'var(--color-surface-hover)' : 'var(--color-surface)',
                color: 'var(--color-text)',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {isPairingOpen ? 'Close Pairing' : 'Pair Phone'}
            </button>
          )}
          <ConnectionChip
            state={mode === 'demo' ? 'REPLAY-SOURCE' : liveConnectionState}
            lastSampleTime={
              (mode === 'live' && liveSamples.length > 0
                ? (liveSamples[liveSamples.length - 1].timestamp as string)
                : currentSample?.timestamp) as string
            }
          />
          <button
            onClick={toggleTheme}
            aria-label="Toggle light and dark theme"
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
          </button>
        </div>
      </header>

      {/* Navigation & Content Area */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Navigation Sidebar */}
        {isMobileNavOpen && (
          <div
            className="mobile-nav-backdrop"
            onClick={() => setIsMobileNavOpen(false)}
          />
        )}
        <nav
          aria-label="Primary navigation"
          className={`app-sidebar ${isMobileNavOpen ? 'open' : ''}`}
          style={{
            width: '240px',
            background: 'var(--color-surface)',
            borderRight: '1px solid var(--color-border)',
            padding: '20px 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            flexShrink: 0,
            position: 'sticky',
            top: '57px',
            alignSelf: 'flex-start',
            height: 'calc(100vh - 57px)',
            overflowY: 'auto',
          }}
        >
          {navGroups.map(group => {
            const groupPages = PAGES.filter(p => p.group === group);
            return (
              <div key={group} style={{ marginBottom: '12px' }}>
                <div
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    color: 'var(--color-text-muted)',
                    padding: '4px 20px 6px',
                    textTransform: 'uppercase',
                  }}
                >
                  {group}
                </div>
                {groupPages.map(p => (
                  <NavLink
                    key={p.path}
                    to={p.path}
                    onClick={() => setIsMobileNavOpen(false)}
                    style={({ isActive }) => ({
                      display: 'block',
                      padding: '8px 20px',
                      color: isActive ? 'var(--color-primary)' : 'var(--color-text)',
                      fontWeight: isActive ? 600 : 400,
                      textDecoration: 'none',
                      fontSize: '13px',
                      background: isActive ? 'var(--color-surface-hover)' : 'transparent',
                      borderLeft: isActive ? '3px solid var(--color-primary)' : '3px solid transparent',
                      transition: 'background 0.15s ease, border-color 0.15s ease',
                    })}
                  >
                    {p.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>

        {/* Main Content Area */}
        <main
          style={{
            flex: 1,
            padding: '24px 32px',
            background: 'var(--color-bg)',
            overflowY: 'auto',
            minWidth: 0,
          }}
        >
          {/* Live Mode Pairing Panel */}
          {mode === 'live' && isPairingOpen && (
            <div style={{ marginBottom: '20px' }}>
              <PairingPanel
                connectionState={liveConnectionState}
                samples={liveSamples}
                fetchFn={fetchFn}
                onSessionStarted={(session: CreateLiveSessionResponse) => {
                  setActiveSessionId(session.session_id);
                  setMode('live');
                  if (typeof sessionStorage !== 'undefined') {
                    sessionStorage.setItem('nads_active_session_id', session.session_id);
                    sessionStorage.setItem('nads_mode', 'live');
                  }
                  setLiveErrorMessage(null);
                  setLiveSamples([]);
                  setLiveEvents([]);
                  setLiveConnectionState('WAITING');
                }}
                onSessionEnded={() => {
                  setActiveSessionId(null);
                  setMode('demo');
                  if (typeof sessionStorage !== 'undefined') {
                    sessionStorage.removeItem('nads_active_session_id');
                    sessionStorage.setItem('nads_mode', 'demo');
                  }
                  setLiveErrorMessage(null);
                  setIsPairingOpen(false);
                  setLiveSamples([]);
                  setLiveEvents([]);
                  setLiveConnectionState('WAITING');
                }}
              />
            </div>
          )}

          {/* Live Mode Server Unreachable State */}
          {mode === 'live' && liveConnectionState === 'DISCONNECTED' && (
            <div
              data-testid="server-unreachable-card"
              role="alert"
              style={{
                padding: '20px',
                borderRadius: '8px',
                border: '1px solid var(--color-danger, #ef4444)',
                background: 'rgba(239, 68, 68, 0.05)',
                marginBottom: '20px',
              }}
            >
              <h2
                style={{
                  fontSize: '16px',
                  fontWeight: 600,
                  color: 'var(--color-danger, #ef4444)',
                  marginBottom: '8px',
                }}
              >
                Streaming Server Unreachable
              </h2>
              <p style={{ fontSize: '13px', marginBottom: '10px' }}>
                Cannot connect to the live streaming WebSocket server.
              </p>
              <div
                style={{
                  background: 'var(--color-surface)',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  border: '1px solid var(--color-border)',
                  marginBottom: '12px',
                }}
              >
                {liveErrorMessage
                  ? `Error: ${liveErrorMessage}`
                  : "Fix: Run 'python -m streaming.server --allow-remote-view' or verify docker port 8000 mapping."}
              </div>
              <button
                data-testid="retry-connection-btn"
                onClick={() => setLiveConnectionState('WAITING')}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              >
                Retry Connection
              </button>
            </div>
          )}

          {/* Live Mode No Session State */}
          {mode === 'live' && liveConnectionState === 'WAITING' && (
            <div
              data-testid="no-session-card"
              style={{
                padding: '20px',
                borderRadius: '8px',
                border: '1px solid var(--color-warning, #f59e0b)',
                background: 'rgba(245, 158, 11, 0.05)',
                marginBottom: '20px',
              }}
            >
              <h2
                style={{
                  fontSize: '16px',
                  fontWeight: 600,
                  color: 'var(--color-warning, #f59e0b)',
                  marginBottom: '8px',
                }}
              >
                No Active Live Session
              </h2>
              <p style={{ fontSize: '13px', marginBottom: '10px' }}>
                Server is reachable, but no mobile device session is currently paired or
                transmitting.
              </p>
              <div
                style={{
                  background: 'var(--color-surface)',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  border: '1px solid var(--color-border)',
                  marginBottom: '12px',
                }}
              >
                Fix: Open the Pairing Panel, pair your Android device (Samsung A15 or Redmi 13) via QR code or 6-digit PIN,
                and begin recording in the 5G-NADS mobile collector.
              </div>
              <button
                data-testid="open-pairing-btn"
                onClick={() => setIsPairingOpen(true)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              >
                Open Pairing Panel
              </button>
            </div>
          )}

          {/* Filters & Global Controls Area (Phase 3.3) */}
          <section
            aria-label="filters and session controls"
            style={{
              marginBottom: '20px',
              padding: '12px 18px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            {error ? (
              <div
                role="alert"
                aria-live="assertive"
                style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid var(--color-danger, #ef4444)',
                  color: 'var(--color-danger, #ef4444)',
                  fontSize: '13px',
                }}
              >
                <strong>Data Layer Error:</strong> {sanitizeErrorMessage(error)}
              </div>
            ) : loading ? (
              <div
                style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}
                aria-live="polite"
              >
                Loading demo bundle...
              </div>
            ) : (
              <div
                style={{
                  display: 'flex',
                  gap: '16px',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label
                    htmlFor="device-select"
                    style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Device:
                  </label>
                  <select
                    id="device-select"
                    aria-label="Filter by device"
                    value={selectedDevice}
                    onChange={e => setSelectedDevice(e.target.value)}
                    style={{
                      padding: '5px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '13px',
                    }}
                  >
                    <option value="all">All Devices</option>
                    {allDevices.map(d => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label
                    htmlFor="operator-select"
                    style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Operator:
                  </label>
                  <select
                    id="operator-select"
                    aria-label="Filter by operator"
                    value={selectedOperator}
                    onChange={e => setSelectedOperator(e.target.value)}
                    style={{
                      padding: '5px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '13px',
                    }}
                  >
                    <option value="all">All Operators</option>
                    {operators.map(op => (
                      <option key={op} value={op}>
                        {op}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label
                    htmlFor="session-select"
                    style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Session:
                  </label>
                  <select
                    id="session-select"
                    aria-label="Select session"
                    value={selectedSessionId}
                    onChange={e => setSelectedSessionId(e.target.value)}
                    style={{
                      padding: '5px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '13px',
                    }}
                  >
                    {sessions.map(s => (
                      <option key={s.session_id} value={s.session_id}>
                        {s.session_id} ({s.n} samples)
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ marginLeft: 'auto', fontSize: '13px', color: 'var(--color-text)' }}>
                  <span style={{ position: 'absolute', width: '1px', height: '1px', padding: 0, margin: '-1px', overflow: 'hidden', clip: 'rect(0, 0, 0, 0)', whiteSpace: 'nowrap', border: 0 }}>
                    Active Subset:
                  </span>
                  {mode === 'live' ? (
                    <>
                      Session:{' '}
                      <strong>
                        {activeSessionId ? `Live (${activeSessionId})` : 'No active session'}
                      </strong>{' '}
                      ({liveSamples.length} samples) · Device:{' '}
                      <strong>
                        {liveSamples.length > 0
                          ? (liveSamples[liveSamples.length - 1].device || 'Samsung Galaxy A15 5G')
                          : (activeSessionId ? 'Samsung Galaxy A15 5G (Paired)' : 'Waiting for device...')}
                      </strong>
                      {liveSamples.length > 0 && (
                        <>
                          {' '}· Operator:{' '}
                          <strong>{liveSamples[liveSamples.length - 1].operator || 'Jio / Airtel'}</strong>
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      Session:{' '}
                      <strong>{currentSession?.session_id || selectedSessionId}</strong>{' '}
                      ({samples.length} samples) · Device:{' '}
                      <strong>{currentSession?.device || selectedDevice}</strong> · Operator:{' '}
                      <strong>{currentSession?.operator || selectedOperator}</strong>
                    </>
                  )}
                </div>
              </div>
            )}
          </section>

          {/* Replay Player Controls (Phase 3.5) */}
          {mode === 'demo' && (
            <div style={{ marginBottom: '20px' }}>
              <ReplayPlayer />
            </div>
          )}

          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route
              path="/overview"
              element={
                <Overview
                  currentSample={
                    mode === 'live'
                      ? (liveSamples.length > 0
                          ? (liveSamples[liveSamples.length - 1] as unknown as Record<string, unknown>)
                          : undefined)
                      : currentSample
                  }
                  prevSample={
                    mode === 'live'
                      ? (liveSamples.length > 1
                          ? (liveSamples[liveSamples.length - 2] as unknown as Record<string, unknown>)
                          : undefined)
                      : prevSample
                  }
                  events={mode === 'live' ? liveEvents : events}
                  connectionState={mode === 'demo' ? 'REPLAY-SOURCE' : liveConnectionState}
                />
              }
            />
            <Route
              path="/signals"
              element={
                <SignalExplorer
                  isLiveMode={mode === 'live'}
                  liveSamples={mode === 'live' ? (liveSamples as unknown as Record<string, unknown>[]) : undefined}
                />
              }
            />
            <Route
              path="/cells"
              element={
                <CellsNetwork
                  liveSamples={mode === 'live' ? liveSamples : undefined}
                  liveEvents={mode === 'live' ? liveEvents : undefined}
                  isLiveMode={mode === 'live'}
                  connectionState={mode === 'demo' ? 'REPLAY-SOURCE' : liveConnectionState}
                />
              }
            />
            <Route
              path="/events"
              element={
                <EventsDiagnosis
                  isLiveMode={mode === 'live'}
                  events={mode === 'live' ? liveEvents : undefined}
                  liveSamples={mode === 'live' ? liveSamples : undefined}
                />
              }
            />
            <Route
              path="/stream-health"
              element={
                <StreamHealth
                  sessionId={activeSessionId}
                  liveSamples={mode === 'live' ? liveSamples : undefined}
                  isLiveMode={mode === 'live'}
                  connectionState={mode === 'demo' ? 'REPLAY-SOURCE' : liveConnectionState}
                />
              }
            />
            <Route
              path="/data-quality"
              element={
                <DataQuality
                  isLiveMode={mode === 'live'}
                  samplesOverride={
                    mode === 'live'
                      ? (liveSamples as unknown as Record<string, unknown>[])
                      : undefined
                  }
                />
              }
            />
            <Route path="/about" element={<About />} />
            {PAGES.filter(
              p =>
                p.path !== '/overview' &&
                p.path !== '/signals' &&
                p.path !== '/cells' &&
                p.path !== '/events' &&
                p.path !== '/stream-health' &&
                p.path !== '/data-quality' &&
                p.path !== '/about'
            ).map(p => (
              <Route
                key={p.path}
                path={p.path}
                element={
                  <div
                    style={{
                      background: 'var(--color-surface)',
                      padding: '24px',
                      borderRadius: '8px',
                      border: '1px solid var(--color-border)',
                    }}
                  >
                    <h1
                      style={{
                        fontSize: '20px',
                        marginBottom: '8px',
                        color: 'var(--color-text)',
                      }}
                    >
                      {p.label}
                    </h1>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '14px' }}>
                      {p.desc}
                    </p>
                  </div>
                }
              />
            ))}
          </Routes>
        </main>
      </div>

      {/* Mandatory Research Prototype Footer (Guardrail G31) */}
      <footer
        style={{
          padding: '14px 24px',
          background: 'var(--color-surface)',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: 'var(--color-text-muted)',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div>
          <strong>Notice (G31):</strong> Academic research prototype — not a commercial
          operator-grade detection tool. Passive telemetry only; does not control the cellular network.
        </div>
        <div>
          <span>App: v2.1.0 · Model: if_v1 (Isolation Forest)</span>
        </div>
      </footer>
    </div>
  );
}

export interface AppProps {
  initialBundle?: DemoBundle | null;
  bundleUrl?: string;
  initialMode?: 'demo' | 'live';
  initialConnectionState?: ConnectionState;
  initialSessionId?: string | null;
  fetchFn?: typeof fetch;
  enableLiveClientInTest?: boolean;
}

export default function App({
  initialBundle,
  bundleUrl,
  initialMode = 'demo',
  initialConnectionState = 'REPLAY-SOURCE',
  initialSessionId = null,
  fetchFn,
  enableLiveClientInTest = false,
}: AppProps = {}) {
  return (
    <DataProvider initialBundle={initialBundle} bundleUrl={bundleUrl}>
      <ReplayProvider>
        <AppContent
          initialMode={initialMode}
          initialConnectionState={initialConnectionState}
          initialSessionId={initialSessionId}
          fetchFn={fetchFn}
          enableLiveClientInTest={enableLiveClientInTest}
        />
      </ReplayProvider>
    </DataProvider>
  );
}
