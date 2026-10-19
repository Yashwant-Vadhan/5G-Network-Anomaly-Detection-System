import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { PAGES } from './constants/pages';
import { DataProvider } from './data/DataContext';
import { useData } from './data/useData';
import { DemoBundle, ConnectionState } from './types/contracts';
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
}

function AppContent({
  initialMode = 'demo',
  initialConnectionState = 'REPLAY-SOURCE',
}: AppContentProps) {
  const [mode, setMode] = useState<'demo' | 'live'>(initialMode);
  const [liveConnectionState, setLiveConnectionState] =
    useState<ConnectionState>(initialConnectionState);
  const [isPairingOpen, setIsPairingOpen] = useState(false);
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
          padding: '16px 24px',
          background: 'var(--color-surface)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-primary)' }}>
            5G-NADS
          </div>
          <div
            data-testid="mode-badge"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              padding: '2px 8px',
              borderRadius: '9999px',
              background: 'var(--color-bg)',
              color: 'var(--color-text-muted)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span data-testid="mode-label">
              {mode === 'demo' ? 'Recorded demo data' : 'Live'}
            </span>
            {mode === 'demo' && <span>Static Demo (Mode 1)</span>}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            data-testid="mode-switch-btn"
            onClick={() => {
              setMode(prev => {
                const next = prev === 'demo' ? 'live' : 'demo';
                if (next === 'live' && liveConnectionState === 'REPLAY-SOURCE') {
                  setLiveConnectionState('WAITING');
                }
                return next;
              });
            }}
            aria-label={`Switch to ${mode === 'demo' ? 'Live' : 'Demo'} mode`}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--color-border)',
              background:
                mode === 'live' ? 'var(--color-primary, #0284c7)' : 'var(--color-surface)',
              color: mode === 'live' ? '#ffffff' : 'var(--color-text)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            {mode === 'demo' ? 'Switch to Live' : 'Switch to Demo'}
          </button>
          {mode === 'live' && (
            <button
              data-testid="pair-phone-btn"
              onClick={() => setIsPairingOpen(prev => !prev)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
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
            lastSampleTime={currentSample?.timestamp as string}
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
            }}
          >
            {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
          </button>
        </div>
      </header>

      {/* Navigation & Content Area */}
      <div style={{ display: 'flex', flex: 1 }}>
        {/* Navigation Sidebar */}
        <nav
          aria-label="Primary navigation"
          style={{
            width: '240px',
            background: 'var(--color-surface)',
            borderRight: '1px solid var(--color-border)',
            padding: '16px 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {PAGES.map(p => (
            <NavLink
              key={p.path}
              to={p.path}
              style={({ isActive }) => ({
                display: 'block',
                padding: '10px 20px',
                color: isActive ? 'var(--color-primary)' : 'var(--color-text)',
                fontWeight: isActive ? 600 : 400,
                textDecoration: 'none',
                background: isActive ? 'var(--color-surface-hover)' : 'transparent',
                borderLeft: isActive ? '4px solid var(--color-primary)' : '4px solid transparent',
              })}
            >
              {p.label}
            </NavLink>
          ))}
        </nav>

        {/* Main Content Area */}
        <main
          style={{
            flex: 1,
            padding: '24px 32px',
            background: 'var(--color-bg)',
            overflowY: 'auto',
          }}
        >
          {/* Live Mode Pairing Panel */}
          {mode === 'live' && isPairingOpen && (
            <div style={{ marginBottom: '20px' }}>
              <PairingPanel
                connectionState={liveConnectionState}
                onSessionEnded={() => setIsPairingOpen(false)}
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
                Fix: Run &apos;python -m streaming.server --allow-remote-view&apos; or check
                network and port.
              </div>
              <button
                data-testid="retry-connection-btn"
                onClick={() => setLiveConnectionState('WAITING')}
                style={{
                  padding: '6px 12px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  cursor: 'pointer',
                  fontSize: '12px',
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
                Fix: Open the Pairing Panel, pair your Android device via QR code or 6-digit PIN,
                and begin recording in the 5G-NADS mobile collector.
              </div>
              <button
                data-testid="open-pairing-btn"
                onClick={() => setIsPairingOpen(true)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  cursor: 'pointer',
                  fontSize: '12px',
                }}
              >
                Open Pairing Panel
              </button>
            </div>
          )}

          {/* Filters & Global Controls Area (T16-008) */}
          <section
            aria-label="Filters and session controls"
            style={{
              marginBottom: '20px',
              padding: '12px 16px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
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
                      padding: '4px 8px',
                      borderRadius: '4px',
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '13px',
                    }}
                  >
                    <option value="all">All Devices</option>
                    {devices.map(d => (
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
                      padding: '4px 8px',
                      borderRadius: '4px',
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
                      padding: '4px 8px',
                      borderRadius: '4px',
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
                  Active Subset:{' '}
                  <strong>{currentSession?.session_id || selectedSessionId}</strong> (
                  {samples.length} samples) · Device:{' '}
                  <strong>{currentSession?.device || selectedDevice}</strong> · Operator:{' '}
                  <strong>{currentSession?.operator || selectedOperator}</strong>
                </div>
              </div>
            )}
          </section>

          {/* Replay Player Controls (T16-010) */}
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
                  currentSample={currentSample}
                  prevSample={prevSample}
                  events={events}
                  connectionState={mode === 'demo' ? 'REPLAY-SOURCE' : liveConnectionState}
                />
              }
            />
            <Route path="/signals" element={<SignalExplorer />} />
            <Route path="/cells" element={<CellsNetwork />} />
            <Route path="/events" element={<EventsDiagnosis />} />
            <Route path="/stream-health" element={<StreamHealth />} />
            <Route path="/data-quality" element={<DataQuality />} />
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
          padding: '16px 24px',
          background: 'var(--color-surface)',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: 'var(--color-text-muted)',
        }}
      >
        <div>
          <strong>Notice (G31):</strong> Academic research prototype — not a commercial
          operator-grade detection tool. Does not control the network.
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
}

export default function App({
  initialBundle,
  bundleUrl,
  initialMode = 'demo',
  initialConnectionState = 'REPLAY-SOURCE',
}: AppProps = {}) {
  return (
    <DataProvider initialBundle={initialBundle} bundleUrl={bundleUrl}>
      <ReplayProvider>
        <AppContent
          initialMode={initialMode}
          initialConnectionState={initialConnectionState}
        />
      </ReplayProvider>
    </DataProvider>
  );
}
