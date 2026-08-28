/**
 * Chat panel — task input, conversation display, and tool call timeline.
 */
import { useState, useRef, useEffect } from 'react';
import { useStore } from '../../stores/appStore';
import { Send, Square, RotateCcw, Plus, CheckCircle, XCircle, Loader2, Wrench, MessageSquare } from 'lucide-react';

export function ChatPanel() {
  const {
    tasks, activeTaskId, taskMessages, taskToolCalls,
    agentState, agentThinking,
    createTask, cancelTask, selectTask,
    sidebarCollapsed,
  } = useStore();
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeMessages = activeTaskId ? taskMessages[activeTaskId] || [] : [];
  const activeToolCalls = activeTaskId ? taskToolCalls[activeTaskId] || [] : [];
  const activeTask = tasks.find(t => t.id === activeTaskId);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeMessages, activeToolCalls, agentThinking]);

  const handleSubmit = async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    try {
      await createTask(input.trim());
      setInput('');
    } catch (e) {
      console.error('Failed to create task:', e);
    }
    setSending(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Build conversation timeline
  const timeline: TimelineItem[] = [];
  let msgIdx = 0;
  let toolIdx = 0;

  // Interleave messages and tool calls by timestamp
  const allItems: TimelineItem[] = [];

  for (const msg of activeMessages) {
    if (msg.role === 'user') {
      allItems.push({ type: 'user', content: msg.content, timestamp: msg.timestamp });
    } else if (msg.role === 'assistant' && msg.content) {
      allItems.push({ type: 'assistant', content: msg.content, timestamp: msg.timestamp });
    }
  }

  for (const tc of activeToolCalls) {
    allItems.push({
      type: 'tool',
      toolName: tc.tool_name,
      input: tc.input,
      output: tc.output,
      status: tc.status,
      error: tc.error,
      durationMs: tc.duration_ms,
      timestamp: tc.started_at,
    });
  }

  allItems.sort((a, b) => a.timestamp - b.timestamp);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      borderRight: '1px solid var(--border-primary)',
      width: sidebarCollapsed ? 0 : undefined,
      minWidth: sidebarCollapsed ? 0 : 340,
      maxWidth: sidebarCollapsed ? 0 : 420,
      overflow: 'hidden',
      transition: 'all 0.2s ease',
    }}>
      {/* Task List Header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border-primary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Tasks</span>
        <button
          onClick={() => selectTask(null)}
          style={{
            background: 'none', border: 'none', color: 'var(--accent-primary)',
            cursor: 'pointer', padding: 2, display: 'flex', fontSize: 12,
          }}
        >
          <Plus size={14} />
        </button>
      </div>

      {/* Task Tabs */}
      {tasks.length > 0 && (
        <div style={{
          display: 'flex', gap: 2, padding: '6px 8px',
          overflowX: 'auto', borderBottom: '1px solid var(--border-primary)',
          flexShrink: 0,
        }}>
          {tasks.slice(0, 10).map(task => (
            <button
              key={task.id}
              onClick={() => selectTask(task.id)}
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 12,
                border: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                background: task.id === activeTaskId ? 'var(--bg-tertiary)' : 'transparent',
                color: task.id === activeTaskId ? 'var(--text-primary)' : 'var(--text-secondary)',
              }}
            >
              <StatusIcon status={task.status} />
              {' '}{task.title.slice(0, 30)}
            </button>
          ))}
        </div>
      )}

      {/* Conversation */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}>
        {allItems.length === 0 && !agentThinking && (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 12,
            color: 'var(--text-tertiary)',
          }}>
            <MessageSquare size={32} strokeWidth={1.5} />
            <span style={{ fontSize: 14 }}>Start a new task</span>
            <span style={{ fontSize: 12, maxWidth: 250, textAlign: 'center', lineHeight: 1.6 }}>
              Type a command like "Create a Python script that prints Fibonacci numbers"
            </span>
          </div>
        )}

        {allItems.map((item, i) => (
          <div key={i} className="animate-fade-in">
            {item.type === 'user' && (
              <div style={{
                background: 'var(--bg-tertiary)',
                borderRadius: 'var(--radius-md)',
                padding: '10px 14px',
                fontSize: 14,
                lineHeight: 1.6,
              }}>
                {item.content}
              </div>
            )}

            {item.type === 'assistant' && (
              <div style={{
                padding: '8px 0',
                fontSize: 14,
                lineHeight: 1.6,
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
              }}>
                {item.content}
              </div>
            )}

            {item.type === 'tool' && (
              <ToolCallCard
                name={item.toolName!}
                input={item.input!}
                output={item.output}
                status={item.status!}
                error={item.error}
                durationMs={item.durationMs}
              />
            )}
          </div>
        ))}

        {/* Agent thinking indicator */}
        {agentThinking && (
          <div className="animate-fade-in" style={{
            padding: '8px 0',
            fontSize: 14,
            color: 'var(--text-secondary)',
            fontStyle: 'italic',
          }}>
            <Loader2 size={14} style={{ display: 'inline', animation: 'spin 1s linear infinite' }} />
            {' '}{agentThinking.slice(-200)}
          </div>
        )}

        {/* Active task status */}
        {activeTask && ['running', 'planning', 'executing'].includes(activeTask.status) && !agentThinking && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 0', color: 'var(--text-secondary)', fontSize: 13,
          }}>
            <Loader2 size={14} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
            <span style={{ textTransform: 'capitalize' }}>{agentState}...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '12px 14px',
        borderTop: '1px solid var(--border-primary)',
        flexShrink: 0,
      }}>
        {/* Cancel button for running tasks */}
        {activeTask?.status === 'running' && (
          <div style={{ marginBottom: 8 }}>
            <button
              className="btn-danger"
              onClick={() => cancelTask(activeTask.id)}
              style={{ width: '100%', justifyContent: 'center', fontSize: 13, padding: '6px 12px' }}
            >
              <Square size={12} /> Cancel Task
            </button>
          </div>
        )}

        <div style={{ position: 'relative' }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What should the AI do?"
            className="input-field"
            rows={2}
            style={{ resize: 'none', paddingRight: 44 }}
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || sending}
            style={{
              position: 'absolute', right: 8, bottom: 8,
              background: input.trim() ? 'var(--accent-primary)' : 'var(--bg-hover)',
              color: input.trim() ? 'white' : 'var(--text-tertiary)',
              border: 'none', borderRadius: 'var(--radius-sm)',
              width: 32, height: 32,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: input.trim() ? 'pointer' : 'default',
              transition: 'all 0.2s ease',
            }}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

// Sub-components
function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle size={12} style={{ color: 'var(--success)', display: 'inline' }} />;
    case 'failed':
      return <XCircle size={12} style={{ color: 'var(--error)', display: 'inline' }} />;
    case 'running':
      return <Loader2 size={12} style={{ color: 'var(--info)', display: 'inline', animation: 'spin 1s linear infinite' }} />;
    default:
      return <span className="status-dot idle" style={{ width: 6, height: 6 }} />;
  }
}

function ToolCallCard({
  name, input, output, status, error, durationMs,
}: {
  name: string; input: string; output?: string; status: string;
  error?: string; durationMs?: number;
}) {
  const [expanded, setExpanded] = useState(false);

  let parsedInput: Record<string, unknown> = {};
  try { parsedInput = JSON.parse(input); } catch {}

  return (
    <div
      className={`tool-card ${status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'running'}`}
      onClick={() => setExpanded(!expanded)}
      style={{ cursor: 'pointer' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Wrench size={12} style={{ color: 'var(--text-tertiary)' }} />
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-accent)' }}>{name}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {durationMs !== undefined && (
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{durationMs.toFixed(0)}ms</span>
          )}
          <span className={`badge badge-${status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'info'}`}>
            {status}
          </span>
        </div>
      </div>

      {/* Brief args */}
      {!expanded && Object.keys(parsedInput).length > 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {Object.entries(parsedInput).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ').slice(0, 80)}
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Input:</span>
            <pre className="terminal-output" style={{
              background: 'var(--bg-primary)', padding: 8, borderRadius: 'var(--radius-sm)',
              marginTop: 4, maxHeight: 120, overflow: 'auto',
            }}>
              {JSON.stringify(parsedInput, null, 2)}
            </pre>
          </div>

          {output && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ color: 'var(--text-tertiary)' }}>Output:</span>
              <pre className="terminal-output" style={{
                background: 'var(--bg-primary)', padding: 8, borderRadius: 'var(--radius-sm)',
                marginTop: 4, maxHeight: 200, overflow: 'auto',
              }}>
                {typeof output === 'string' ? output : JSON.stringify(output, null, 2)}
              </pre>
            </div>
          )}

          {error && (
            <div style={{ color: 'var(--error)', fontSize: 12, marginTop: 4 }}>
              ⚠ {error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface TimelineItem {
  type: 'user' | 'assistant' | 'tool';
  content?: string;
  toolName?: string;
  input?: string;
  output?: string;
  status?: string;
  error?: string;
  durationMs?: number;
  timestamp: number;
}
