/**
 * Bottom panel system — Timeline, Terminal, Files, Tools, Events, Settings tabs.
 */
import { useState } from 'react';
import { useStore } from '../../stores/appStore';
import {
  Clock, Terminal, FolderTree, Globe, Wrench, Activity,
  Settings, ChevronDown, ChevronRight, CheckCircle, XCircle,
  Loader2, AlertCircle,
} from 'lucide-react';

const TABS = [
  { id: 'timeline' as const, label: 'Timeline', icon: Clock },
  { id: 'terminal' as const, label: 'Terminal', icon: Terminal },
  { id: 'tools' as const, label: 'Tools', icon: Wrench },
  { id: 'events' as const, label: 'Events', icon: Activity },
  { id: 'settings' as const, label: 'Settings', icon: Settings },
] as const;

export function BottomPanel() {
  const { activePanel, setActivePanel } = useStore();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      borderTop: '1px solid var(--border-primary)',
      height: collapsed ? 36 : 280,
      minHeight: collapsed ? 36 : 200,
      transition: 'height 0.2s ease',
      flexShrink: 0,
    }}>
      {/* Tab Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 8px',
        height: 36,
        flexShrink: 0,
        background: 'var(--bg-secondary)',
        borderBottom: collapsed ? 'none' : '1px solid var(--border-primary)',
      }}>
        <div className="tab-bar" style={{ background: 'transparent', padding: 0, gap: 0 }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`tab-item ${activePanel === tab.id ? 'active' : ''}`}
              onClick={() => { setActivePanel(tab.id); if (collapsed) setCollapsed(false); }}
            >
              <tab.icon size={13} style={{ display: 'inline', verticalAlign: -2, marginRight: 4 }} />
              {tab.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', padding: 4, display: 'flex',
          }}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Panel Content */}
      {!collapsed && (
        <div style={{ flex: 1, overflow: 'auto', background: 'var(--bg-primary)' }}>
          {activePanel === 'timeline' && <TimelinePanel />}
          {activePanel === 'terminal' && <TerminalPanel />}
          {activePanel === 'tools' && <ToolsPanel />}
          {activePanel === 'events' && <EventsPanel />}
          {activePanel === 'settings' && <SettingsPanel />}
        </div>
      )}
    </div>
  );
}

/* ── Timeline Panel ── */
function TimelinePanel() {
  const { events, activeTaskId } = useStore();
  const taskEvents = activeTaskId
    ? events.filter(e => e.task_id === activeTaskId)
    : events;

  const relevantEvents = taskEvents.filter(e =>
    ['task.started', 'task.completed', 'task.failed', 'tool.started', 'tool.completed',
     'tool.failed', 'agent.state_changed', 'agent.message'].includes(e.type)
  ).slice(-50);

  if (relevantEvents.length === 0) {
    return (
      <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
        No events yet. Start a task to see the timeline.
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 14px' }}>
      {relevantEvents.map((event, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 0',
          borderBottom: '1px solid var(--bg-tertiary)',
          fontSize: 13,
        }}>
          <EventIcon type={event.type} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <EventLabel event={event} />
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
            {new Date(event.timestamp * 1000).toLocaleTimeString()}
          </span>
        </div>
      ))}
    </div>
  );
}

function EventIcon({ type }: { type: string }) {
  if (type.includes('completed')) return <CheckCircle size={14} style={{ color: 'var(--success)', marginTop: 2 }} />;
  if (type.includes('failed')) return <XCircle size={14} style={{ color: 'var(--error)', marginTop: 2 }} />;
  if (type.includes('started')) return <Loader2 size={14} style={{ color: 'var(--info)', marginTop: 2 }} />;
  return <Activity size={14} style={{ color: 'var(--text-tertiary)', marginTop: 2 }} />;
}

function EventLabel({ event }: { event: { type: string; data: Record<string, unknown> } }) {
  const { type, data } = event;
  switch (type) {
    case 'task.started':
      return <span>Task started: <strong>{data.title as string}</strong></span>;
    case 'task.completed':
      return <span style={{ color: 'var(--success)' }}>Task completed ({data.steps} steps)</span>;
    case 'task.failed':
      return <span style={{ color: 'var(--error)' }}>Task failed: {data.error as string}</span>;
    case 'tool.started':
      return <span>Running <span style={{ color: 'var(--text-accent)' }}>{data.tool as string}</span></span>;
    case 'tool.completed':
      return <span><span style={{ color: 'var(--text-accent)' }}>{data.tool as string}</span> completed ({(data.duration_ms as number)?.toFixed(0)}ms)</span>;
    case 'tool.failed':
      return <span style={{ color: 'var(--error)' }}><span style={{ color: 'var(--text-accent)' }}>{data.tool as string}</span> failed: {data.error as string}</span>;
    case 'agent.state_changed':
      return <span>Agent → <strong>{data.state as string}</strong></span>;
    case 'agent.message':
      return <span style={{ color: 'var(--text-secondary)' }}>Agent: {(data.content as string)?.slice(0, 80)}...</span>;
    default:
      return <span>{type}</span>;
  }
}

/* ── Terminal Panel ── */
function TerminalPanel() {
  const { events } = useStore();
  const terminalEvents = events.filter(e =>
    e.type === 'tool.completed' && (e.data.tool as string)?.startsWith('terminal.')
  );

  if (terminalEvents.length === 0) {
    return (
      <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
        <Terminal size={20} style={{ display: 'block', margin: '0 auto 8px' }} />
        Terminal output appears here when commands are executed.
      </div>
    );
  }

  return (
    <div className="terminal-output" style={{ padding: '8px 14px' }}>
      {terminalEvents.map((event, i) => (
        <div key={i} style={{ marginBottom: 12 }}>
          <div style={{ color: 'var(--text-accent)', fontSize: 12, marginBottom: 4 }}>
            $ {event.data.tool as string}
          </div>
          <div style={{ color: event.data.success ? 'var(--text-primary)' : 'var(--error)' }}>
            {event.data.output_preview as string || event.data.error as string || 'No output'}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Tools Panel ── */
function ToolsPanel() {
  const { tools, toolCategories } = useStore();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const filtered = selectedCategory
    ? tools.filter(t => t.category === selectedCategory)
    : tools;

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Category list */}
      <div style={{
        width: 140, borderRight: '1px solid var(--border-primary)',
        padding: '8px 0', overflowY: 'auto',
      }}>
        <button
          className={`tab-item ${!selectedCategory ? 'active' : ''}`}
          onClick={() => setSelectedCategory(null)}
          style={{ width: '100%', textAlign: 'left', padding: '4px 12px' }}
        >
          All ({tools.length})
        </button>
        {toolCategories.map(cat => (
          <button
            key={cat}
            className={`tab-item ${selectedCategory === cat ? 'active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
            style={{ width: '100%', textAlign: 'left', padding: '4px 12px' }}
          >
            {cat} ({tools.filter(t => t.category === cat).length})
          </button>
        ))}
      </div>

      {/* Tool list */}
      <div style={{ flex: 1, padding: '8px 14px', overflowY: 'auto' }}>
        {filtered.map(tool => (
          <div key={tool.name} style={{
            padding: '8px 0', borderBottom: '1px solid var(--bg-tertiary)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-accent)' }}>{tool.name}</span>
              <span className={`badge badge-${tool.risk_level === 'safe' ? 'success' : tool.risk_level === 'low' ? 'info' : 'warning'}`}>
                {tool.risk_level}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
              {tool.description}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Events Panel ── */
function EventsPanel() {
  const { events } = useStore();
  const recentEvents = events.slice(-100).reverse();

  return (
    <div className="terminal-output" style={{ padding: '8px 14px' }}>
      {recentEvents.map((event, i) => (
        <div key={i} style={{
          display: 'flex', gap: 10, padding: '3px 0',
          fontSize: 12, color: 'var(--text-secondary)',
        }}>
          <span style={{ color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
            {new Date(event.timestamp * 1000).toLocaleTimeString()}
          </span>
          <span style={{ color: eventColor(event.type) }}>{event.type}</span>
          <span style={{ color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {JSON.stringify(event.data).slice(0, 80)}
          </span>
        </div>
      ))}
      {recentEvents.length === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: 20 }}>
          No events yet
        </div>
      )}
    </div>
  );
}

function eventColor(type: string): string {
  if (type.includes('completed') || type.includes('success')) return 'var(--success)';
  if (type.includes('failed') || type.includes('error')) return 'var(--error)';
  if (type.includes('started') || type.includes('created')) return 'var(--info)';
  return 'var(--text-accent)';
}

/* ── Settings Panel ── */
function SettingsPanel() {
  const { llmSettings, llmConnected, testLLM, updateLLMSettings } = useStore();
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    await testLLM();
    setTesting(false);
  };

  if (!llmSettings) return <div style={{ padding: 20, color: 'var(--text-tertiary)' }}>Loading settings...</div>;

  return (
    <div style={{ padding: '14px 20px', maxWidth: 600 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 14, color: 'var(--text-primary)' }}>
        LLM Configuration
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
        <SettingField
          label="Provider" value={llmSettings.provider}
          onChange={v => updateLLMSettings({ provider: v })}
        />
        <SettingField
          label="Model" value={llmSettings.model}
          onChange={v => updateLLMSettings({ model: v })}
        />
        <SettingField
          label="Base URL" value={llmSettings.base_url}
          onChange={v => updateLLMSettings({ base_url: v })}
          span={2}
        />
        <SettingField
          label="Temperature" value={String(llmSettings.temperature)}
          onChange={v => updateLLMSettings({ temperature: parseFloat(v) || 0 })}
        />
        <SettingField
          label="Context Size" value={String(llmSettings.context_size)}
          onChange={v => updateLLMSettings({ context_size: parseInt(v) || 8192 })}
        />
        <SettingField
          label="Max Output" value={String(llmSettings.max_output)}
          onChange={v => updateLLMSettings({ max_output: parseInt(v) || 4096 })}
        />
        <SettingField
          label="Timeout (s)" value={String(llmSettings.timeout)}
          onChange={v => updateLLMSettings({ timeout: parseInt(v) || 120 })}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16 }}>
        <button className="btn-primary" onClick={handleTest} disabled={testing}>
          {testing ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Wrench size={14} />}
          Test Connection
        </button>
        {llmConnected !== null && (
          <span style={{
            fontSize: 13,
            color: llmConnected ? 'var(--success)' : 'var(--error)',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            {llmConnected ? <><CheckCircle size={14} /> Connected</> : <><AlertCircle size={14} /> Not connected</>}
          </span>
        )}
      </div>
    </div>
  );
}

function SettingField({ label, value, onChange, span }: {
  label: string; value: string; onChange: (v: string) => void; span?: number;
}) {
  return (
    <div style={{ gridColumn: span ? `span ${span}` : undefined }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>
        {label}
      </label>
      <input
        className="input-field"
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ padding: '6px 10px', fontSize: 13 }}
      />
    </div>
  );
}
