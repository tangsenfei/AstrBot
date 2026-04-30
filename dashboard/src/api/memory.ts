import axios from 'axios';

export interface MemoryEvent {
  id: string;
  agent_id: string;
  scene_id?: string;
  type: 'user_message' | 'agent_reply' | 'tool_call' | 'scheduled_task' | 'system_event';
  role?: string;
  content: string;
  metadata: Record<string, any>;
  created_at: string;
  created_by?: string;
}

export interface EventsQueryParams {
  agent_id?: string;
  type?: string;
  search?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  page_size?: number;
}

export interface EventsResponse {
  total: number;
  page: number;
  page_size: number;
  items: MemoryEvent[];
}

export interface MemoryStats {
  events_total: number;
  scenes_total: number;
  claims_total: number;
  rules_total: number;
  identity_total: number;
  active_prompts: number;
  event_counts_by_agent: Array<{ agent_id: string; count: number }>;
}

export async function fetchEvents(params: EventsQueryParams): Promise<EventsResponse> {
  const response = await axios.get('/api/memory/events', { params });
  return response.data.data;
}

export async function fetchEventDetail(eventId: string): Promise<MemoryEvent> {
  const response = await axios.get(`/api/memory/events/${eventId}`);
  return response.data.data;
}

export async function exportEvents(params: EventsQueryParams) {
  const response = await axios.get('/api/memory/events/export', { params });
  return response.data.data as { items: MemoryEvent[]; total: number };
}

export async function fetchMemoryStats(agentId?: string): Promise<MemoryStats> {
  const response = await axios.get('/api/memory/stats', { params: { agent_id: agentId } });
  return response.data.data;
}
