/**
 * Header component — top bar with platform status, connection indicators, and controls.
 */
import { useStore } from '../../stores/appStore';
import { Cpu, Wifi, WifiOff, Zap, Settings, PanelLeft } from 'lucide-react';

export function Header() {
  const { wsConnected, backendConnected, agentState, tools, setActivePanel, toggleSidebar } = useStore();

  const stateColors: Record<string, string> = {
    idle: 'idle',
    planning: 'planning',
    executing: 'running',
    observing: 'running',
    verifying: 'running',
    recovering: 'error',
    completed: 'idle',
    failed: 'error',
    cancelled: 'idle',
  };

  return (
    <header style={{
      height: 48,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
      background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border-primary)',
      flexShrink: 0,
    }}>
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={toggleSidebar}
          style={{
            background: 'none', border: 'none', color: 'var(--text-secondary)',
            cursor: 'pointer', padding: 4, display: 'flex',
          }}
        >
          <PanelLeft size={18} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Cpu size={20} style={{ color: 'var(--accent-primary)' }} />
          <span style={{ fontWeight: 600, fontSize: 15 }} className="gradient-text">
            AI Computer
          </span>
        </div>
      </div>

      {/* Center — Agent State */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className={`status-dot ${stateColors[agentState] || 'idle'}`} />
        <span style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
          {agentState}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          · {tools.length} tools
        </span>
      </div>

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {wsConnected ? (
            <Wifi size={14} style={{ color: 'var(--success)' }} />
          ) : (
            <WifiOff size={14} style={{ color: 'var(--error)' }} />
          )}
          <span style={{ fontSize: 12, color: wsConnected ? 'var(--success)' : 'var(--error)' }}>
            {wsConnected ? 'Live' : 'Disconnected'}
          </span>
        </div>

        <div style={{
          width: 1, height: 20, background: 'var(--border-primary)',
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Zap size={14} style={{ color: backendConnected ? 'var(--success)' : 'var(--error)' }} />
          <span style={{ fontSize: 12, color: backendConnected ? 'var(--text-secondary)' : 'var(--error)' }}>
            {backendConnected ? 'Backend' : 'No Backend'}
          </span>
        </div>

        <button
          onClick={() => setActivePanel('settings')}
          style={{
            background: 'none', border: 'none', color: 'var(--text-secondary)',
            cursor: 'pointer', padding: 4, display: 'flex',
          }}
        >
          <Settings size={16} />
        </button>
      </div>
    </header>
  );
}
