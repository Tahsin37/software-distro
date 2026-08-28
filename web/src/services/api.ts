/**
 * API client for the platform backend.
 */
const BASE_URL = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => fetchJSON<{ status: string; tools: number; categories: string[] }>('/health'),

  // Tasks
  createTask: (message: string, title?: string) =>
    fetchJSON<{ id: string; title: string; status: string }>('/tasks', {
      method: 'POST',
      body: JSON.stringify({ message, title }),
    }),

  listTasks: (limit = 50) =>
    fetchJSON<{ tasks: TaskRecord[] }>(`/tasks?limit=${limit}`),

  getTask: (id: string) =>
    fetchJSON<{ task: TaskRecord; messages: MessageRecord[]; tool_calls: ToolCallRecord[] }>(`/tasks/${id}`),

  cancelTask: (id: string) =>
    fetchJSON<{ cancelled: boolean }>(`/tasks/${id}/cancel`, { method: 'POST' }),

  retryTask: (id: string) =>
    fetchJSON<{ new_task_id: string }>(`/tasks/${id}/retry`, { method: 'POST' }),

  // Tools
  listTools: () =>
    fetchJSON<{ tools: ToolInfo[]; categories: string[]; total: number }>('/tools'),

  executeTool: (name: string, args: Record<string, unknown>) =>
    fetchJSON<ToolResult>(`/tools/${name}/execute`, {
      method: 'POST',
      body: JSON.stringify({ args }),
    }),

  // Settings
  getLLMSettings: () => fetchJSON<LLMSettings>('/settings/llm'),
  updateLLMSettings: (settings: Partial<LLMSettings>) =>
    fetchJSON<LLMSettings>('/settings/llm', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  testLLM: () => fetchJSON<{ connected: boolean; models?: string[]; error?: string }>('/settings/llm/test'),
  listModels: () => fetchJSON<{ models: string[] }>('/settings/llm/models'),

  // Events
  getEventHistory: (limit = 100) => fetchJSON<{ events: PlatformEvent[] }>(`/events/history?limit=${limit}`),
};

// Types
export interface TaskRecord {
  id: string;
  title: string;
  description?: string;
  status: string;
  created_at: number;
  started_at?: number;
  completed_at?: number;
  error?: string;
  result?: string;
}

export interface MessageRecord {
  id: number;
  task_id: string;
  role: string;
  content: string;
  tool_calls?: string;
  timestamp: number;
}

export interface ToolCallRecord {
  id: string;
  task_id?: string;
  tool_name: string;
  input: string;
  output?: string;
  status: string;
  started_at: number;
  completed_at?: number;
  duration_ms?: number;
  error?: string;
}

export interface ToolInfo {
  name: string;
  description: string;
  category: string;
  risk_level: string;
  version: string;
  parameters: Record<string, unknown>;
}

export interface ToolResult {
  success: boolean;
  output?: unknown;
  error?: string;
  duration_ms: number;
}

export interface LLMSettings {
  provider: string;
  base_url: string;
  model: string;
  temperature: number;
  context_size: number;
  max_output: number;
  timeout: number;
}

export interface PlatformEvent {
  type: string;
  data: Record<string, unknown>;
  task_id?: string;
  timestamp: number;
}
