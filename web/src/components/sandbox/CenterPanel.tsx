/**
 * Center panel — Live sandbox view and agent state display.
 * Shows the "computer" the AI is operating on.
 */
import { useStore } from '../../stores/appStore';
import {
  Monitor, Activity, CheckCircle, XCircle, Loader2,
  Brain, Eye, Shield, RotateCcw, Cpu, HardDrive, Wifi,
} from 'lucide-react';

export function CenterPanel() {
  const { agentState, activeTaskId, tasks, events, tools, wsConnected } = useStore();
  const activeTask = tasks.find(t => t.id === activeTaskId);

  // Get recent tool executions for the active task
  const recentTools = events
    .filter(e => e.task_id === activeTaskId && (e.type === 'tool.completed' || e.type === 'tool.failed'))
    .slice(-8);

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Sandbox Header */}
      <div style={{
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border-primary)',
        background: 'var(--bg-secondary)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Monitor size={15} style={{ color: 'var(--text-secondary)' }} />
          <span style={{ fontSize: 13, fontWeight: 500 }}>Sandbox Computer</span>
          <span className={`badge badge-${wsConnected ? 'success' : 'error'}`}>
            {wsConnected ? 'Connected' : 'Offline'}
          </span>
        </div>
        {activeTask && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Task: {activeTask.title.slice(0, 50)}
          </span>
        )}
      </div>

      {/* Main Content Area */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'auto',
      }}>
        {/* Agent State Visualization */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px 20px',
          gap: 40,
        }}>
          <AgentStateIndicator state={agentState} />
        </div>

        {/* Live Activity Feed */}
        <div style={{ padding: '0 20px', flex: 1 }}>
          {/* Active Task Info */}
          {activeTask && (
            <div className="glass-panel animate-fade-in" style={{ padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <TaskStatusBadge status={activeTask.status} />
                <span style={{ fontSize: 14, fontWeight: 500 }}>{activeTask.title}</span>
              </div>
              {activeTask.description && (
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {activeTask.description.slice(0, 200)}
                </p>
              )}
              {activeTask.error && (
                <div style={{
                  marginTop: 8, padding: '8px 12px',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 12, color: 'var(--error)',
                }}>
                  {activeTask.error}
                </div>
              )}
              {activeTask.result && (
                <div style={{
                  marginTop: 8, padding: '8px 12px',
                  background: 'rgba(34, 197, 94, 0.05)',
                  border: '1px solid rgba(34, 197, 94, 0.2)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 13, color: 'var(--text-primary)',
                  lineHeight: 1.5, whiteSpace: 'pre-wrap',
                  maxHeight: 200, overflow: 'auto',
                }}>
                  {activeTask.result}
                </div>
              )}
            </div>
          )}

          {/* Recent Tool Executions */}
          {recentTools.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 8, fontWeight: 500 }}>
                Recent Operations
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                {recentTools.map((event, i) => (
                  <div key={i} className={`tool-card ${event.data.success ? 'success' : 'error'}`}
                    style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 13, color: 'var(--text-accent)', fontWeight: 500 }}>
                        {event.data.tool as string}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                        {(event.data.duration_ms as number)?.toFixed(0)}ms
                      </span>
                    </div>
                    {event.data.error && (
                      <div style={{ fontSize: 11, color: 'var(--error)', marginTop: 4 }}>
                        {(event.data.error as string).slice(0, 80)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* System Status Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
            gap: 10,
          }}>
            <StatusCard icon={Cpu} label="Tools" value={`${tools.length} registered`} color="var(--accent-primary)" />
            <StatusCard icon={HardDrive} label="Sandbox" value="Process-level" color="var(--success)" />
            <StatusCard icon={Wifi} label="Network" value="Normal" color="var(--info)" />
            <StatusCard icon={Shield} label="Security" value="Enforced" color="var(--warning)" />
          </div>

          {/* No task state */}
          {!activeTask && (
            <div style={{
              textAlign: 'center', padding: '40px 20px',
              color: 'var(--text-tertiary)',
            }}>
              <Monitor size={40} strokeWidth={1} style={{ display: 'block', margin: '0 auto 12px', opacity: 0.5 }} />
              <p style={{ fontSize: 15, marginBottom: 8 }}>No active task</p>
              <p style={{ fontSize: 13 }}>Enter a task in the chat panel to start the AI agent</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentStateIndicator({ state }: { state: string }) {
  const states = [
    { key: 'planning', label: 'Plan', icon: Brain },
    { key: 'executing', label: 'Act', icon: Activity },
    { key: 'observing', label: 'Observe', icon: Eye },
    { key: 'verifying', label: 'Verify', icon: CheckCircle },
    { key: 'recovering', label: 'Recover', icon: RotateCcw },
  ];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      {states.map((s, i) => {
        const isActive = state === s.key;
        const isPast = states.findIndex(x => x.key === state) > i;
        const Icon = s.icon;
        return (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              opacity: isActive ? 1 : isPast ? 0.7 : 0.3,
              transition: 'opacity 0.3s ease',
            }}>
              <div style={{
                width: 36, height: 36,
                borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: isActive
                  ? 'var(--accent-gradient)'
                  : isPast ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-tertiary)',
                border: isActive ? 'none' : '1px solid var(--border-primary)',
                transition: 'all 0.3s ease',
                boxShadow: isActive ? 'var(--shadow-glow)' : 'none',
              }}>
                <Icon size={16} style={{ color: isActive ? 'white' : 'var(--text-secondary)' }} />
              </div>
              <span style={{
                fontSize: 10, fontWeight: 500,
                color: isActive ? 'var(--text-accent)' : 'var(--text-tertiary)',
              }}>
                {s.label}
              </span>
            </div>
            {i < states.length - 1 && (
              <div style={{
                width: 30, height: 2,
                background: isPast ? 'var(--accent-primary)' : 'var(--border-primary)',
                margin: '0 4px', marginBottom: 18,
                transition: 'background 0.3s ease',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function TaskStatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: typeof CheckCircle }> = {
    completed: { color: 'var(--success)', icon: CheckCircle },
    failed: { color: 'var(--error)', icon: XCircle },
    running: { color: 'var(--info)', icon: Loader2 },
    cancelled: { color: 'var(--text-tertiary)', icon: XCircle },
    pending: { color: 'var(--text-tertiary)', icon: Activity },
  };

  const c = config[status] || config.pending;
  const Icon = c.icon;

  return (
    <span className={`badge badge-${status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'info'}`}>
      <Icon size={11} style={{
        marginRight: 4,
        ...(status === 'running' ? { animation: 'spin 1s linear infinite' } : {}),
      }} />
      {status}
    </span>
  );
}

function StatusCard({
  icon: Icon, label, value, color,
}: {
  icon: typeof Cpu; label: string; value: string; color: string;
}) {
  return (
    <div className="glass-panel" style={{
      padding: '12px 14px',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon size={14} style={{ color }} />
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 500 }}>{label}</span>
      </div>
      <span style={{ fontSize: 13, fontWeight: 500 }}>{value}</span>
    </div>
  );
}
