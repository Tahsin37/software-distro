/**
 * Main application store using Zustand.
 * Manages tasks, events, agent state, and UI state.
 */
import { create } from 'zustand';
import { api, TaskRecord, ToolCallRecord, MessageRecord, ToolInfo, LLMSettings } from '../services/api';
import { wsService, PlatformEvent } from '../services/websocket';

interface AppState {
  // Connection
  wsConnected: boolean;
  backendConnected: boolean;

  // Tasks
  tasks: TaskRecord[];
  activeTaskId: string | null;
  taskMessages: Record<string, MessageRecord[]>;
  taskToolCalls: Record<string, ToolCallRecord[]>;

  // Agent
  agentState: string;
  agentThinking: string;

  // Events
  events: PlatformEvent[];

  // Tools
  tools: ToolInfo[];
  toolCategories: string[];

  // LLM
  llmSettings: LLMSettings | null;
  llmConnected: boolean | null;

  // UI
  activePanel: 'timeline' | 'terminal' | 'files' | 'browser' | 'tools' | 'events' | 'settings';
  sidebarCollapsed: boolean;

  // Actions
  init: () => Promise<void>;
  createTask: (message: string) => Promise<string>;
  cancelTask: (taskId: string) => Promise<void>;
  retryTask: (taskId: string) => Promise<void>;
  selectTask: (taskId: string | null) => void;
  setActivePanel: (panel: AppState['activePanel']) => void;
  toggleSidebar: () => void;
  loadTaskDetails: (taskId: string) => Promise<void>;
  testLLM: () => Promise<void>;
  updateLLMSettings: (settings: Partial<LLMSettings>) => Promise<void>;
  refreshTasks: () => Promise<void>;
}

export const useStore = create<AppState>((set, get) => ({
  // Initial state
  wsConnected: false,
  backendConnected: false,
  tasks: [],
  activeTaskId: null,
  taskMessages: {},
  taskToolCalls: {},
  agentState: 'idle',
  agentThinking: '',
  events: [],
  tools: [],
  toolCategories: [],
  llmSettings: null,
  llmConnected: null,
  activePanel: 'timeline',
  sidebarCollapsed: false,

  // Initialize
  init: async () => {
    // Connect WebSocket
    wsService.connect();

    // Subscribe to events
    wsService.subscribe((event: PlatformEvent) => {
      const state = get();

      // Update connection state
      if (event.type === 'ws.connected') {
        set({ wsConnected: true });
        return;
      }
      if (event.type === 'ws.disconnected') {
        set({ wsConnected: false });
        return;
      }

      // Add to event log
      set({ events: [...state.events.slice(-500), event] });

      // Handle specific events
      switch (event.type) {
        case 'task.started':
        case 'task.completed':
        case 'task.failed':
        case 'task.cancelled':
          get().refreshTasks();
          break;

        case 'agent.state_changed':
          set({ agentState: event.data.state as string });
          break;

        case 'agent.thinking':
          set({ agentThinking: event.data.accumulated as string || '' });
          break;

        case 'agent.message': {
          const taskId = event.task_id;
          if (taskId) {
            const msgs = state.taskMessages[taskId] || [];
            const newMsg: MessageRecord = {
              id: Date.now(),
              task_id: taskId,
              role: 'assistant',
              content: event.data.content as string,
              timestamp: event.timestamp,
            };
            set({
              taskMessages: { ...state.taskMessages, [taskId]: [...msgs, newMsg] },
              agentThinking: '',
            });
          }
          break;
        }

        case 'tool.started':
        case 'tool.completed':
        case 'tool.failed': {
          const taskId = event.task_id;
          if (taskId) {
            const calls = state.taskToolCalls[taskId] || [];
            if (event.type === 'tool.started') {
              calls.push({
                id: event.data.execution_id as string,
                task_id: taskId,
                tool_name: event.data.tool as string,
                input: JSON.stringify(event.data.args),
                status: 'running',
                started_at: event.timestamp,
              });
            } else {
              const idx = calls.findIndex(c => c.id === event.data.execution_id);
              if (idx !== -1) {
                calls[idx] = {
                  ...calls[idx],
                  status: event.data.success ? 'completed' : 'failed',
                  completed_at: event.timestamp,
                  duration_ms: event.data.duration_ms as number,
                  output: event.data.output_preview as string,
                  error: event.data.error as string,
                };
              }
            }
            set({ taskToolCalls: { ...state.taskToolCalls, [taskId]: [...calls] } });
          }
          break;
        }
      }
    });

    // Load initial data
    try {
      const [health, tasksData, toolsData, llmSettings] = await Promise.all([
        api.health(),
        api.listTasks(),
        api.listTools(),
        api.getLLMSettings(),
      ]);

      set({
        backendConnected: true,
        tasks: tasksData.tasks,
        tools: toolsData.tools,
        toolCategories: toolsData.categories,
        llmSettings,
      });
    } catch (e) {
      console.error('Failed to load initial data:', e);
      set({ backendConnected: false });
    }
  },

  createTask: async (message: string) => {
    const result = await api.createTask(message);
    set(state => ({
      activeTaskId: result.id,
      taskMessages: {
        ...state.taskMessages,
        [result.id]: [{
          id: Date.now(),
          task_id: result.id,
          role: 'user',
          content: message,
          timestamp: Date.now() / 1000,
        }],
      },
      taskToolCalls: { ...state.taskToolCalls, [result.id]: [] },
    }));
    get().refreshTasks();
    return result.id;
  },

  cancelTask: async (taskId: string) => {
    await api.cancelTask(taskId);
    get().refreshTasks();
  },

  retryTask: async (taskId: string) => {
    const result = await api.retryTask(taskId);
    set({ activeTaskId: result.new_task_id });
    get().refreshTasks();
  },

  selectTask: (taskId: string | null) => {
    set({ activeTaskId: taskId, agentThinking: '' });
    if (taskId) get().loadTaskDetails(taskId);
  },

  loadTaskDetails: async (taskId: string) => {
    try {
      const data = await api.getTask(taskId);
      set(state => ({
        taskMessages: { ...state.taskMessages, [taskId]: data.messages },
        taskToolCalls: { ...state.taskToolCalls, [taskId]: data.tool_calls },
      }));
    } catch (e) {
      console.error('Failed to load task details:', e);
    }
  },

  refreshTasks: async () => {
    try {
      const data = await api.listTasks();
      set({ tasks: data.tasks });
    } catch (e) {
      console.error('Failed to refresh tasks:', e);
    }
  },

  testLLM: async () => {
    try {
      const result = await api.testLLM();
      set({ llmConnected: result.connected });
    } catch (e) {
      set({ llmConnected: false });
    }
  },

  updateLLMSettings: async (settings: Partial<LLMSettings>) => {
    const updated = await api.updateLLMSettings(settings);
    set({ llmSettings: updated });
  },

  setActivePanel: (panel) => set({ activePanel: panel }),
  toggleSidebar: () => set(state => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
