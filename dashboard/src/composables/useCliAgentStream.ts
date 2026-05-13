import { isRef, onUnmounted, ref, type Ref } from 'vue';
import axios from 'axios';
import { EventSourcePolyfill } from 'event-source-polyfill';

export type CliAgentMessage = {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  created_at?: string;
};

export type PermissionRequest = {
  id?: string;
  permission_id?: string;
  title?: string;
  body?: string;
  payload?: Record<string, any>;
};

function sourceValue(sessionId: string | Ref<string>) {
  return isRef(sessionId) ? sessionId.value : sessionId;
}

export function useCliAgentStream(
  sessionId: string | Ref<string>,
  initialMessages?: Ref<CliAgentMessage[]>,
) {
  const messages = initialMessages || ref<CliAgentMessage[]>([]);
  const isStreaming = ref(false);
  const connected = ref(false);
  const pendingPermission = ref<PermissionRequest | null>(null);
  const errorText = ref('');
  const statusText = ref('');
  const recovering = ref(false);
  const capabilities = ref<Record<string, any>>({});
  const modelOptions = ref<{ label: string; value: string }[]>([]);
  const modeOptions = ref<{ label: string; value: string }[]>([]);
  const currentModelId = ref('');
  const currentModeId = ref('');
  let eventSource: EventSourcePolyfill | null = null;
  let lastEventId = 0;
  let localTurnPending = false;

  function connect(targetSessionId = sourceValue(sessionId)) {
    disconnect();
    if (!targetSessionId) return;
    const token = localStorage.getItem('token') || '';
    const query = lastEventId > 0 ? `?after_seq=${lastEventId}` : '?live=1';
    eventSource = new EventSourcePolyfill(
      `/api/plug/cli-agents/sessions/${targetSessionId}/stream${query}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        heartbeatTimeout: 60000,
      },
    );
    eventSource.addEventListener('message', (event: MessageEvent) => {
      if (event.lastEventId) lastEventId = Number(event.lastEventId) || lastEventId;
      if (!event.data || event.data === '[DONE]') {
        isStreaming.value = false;
        return;
      }
      try {
        handleEvent(JSON.parse(event.data));
      } catch (error: any) {
        errorText.value = error?.message || 'CLI Agent 流式事件解析失败';
      }
    });
    eventSource.onopen = () => {
      connected.value = true;
    };
    eventSource.onerror = () => {
      connected.value = false;
    };
  }

  function disconnect() {
    connected.value = false;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function handleEvent(payload: any) {
    if (!payload || typeof payload !== 'object') return;
    connected.value = true;
    if (payload.seq) lastEventId = Math.max(lastEventId, Number(payload.seq) || 0);
    switch (payload.type) {
      case 'message':
        appendCompleteMessage(payload.role, payload.content);
        break;
      case 'message_chunk':
        appendToStreamingMessage(String(payload.text || ''));
        if (localTurnPending) isStreaming.value = true;
        break;
      case 'tool_call':
        upsertToolCallMessage(payload);
        break;
      case 'permission':
        pendingPermission.value = payload;
        break;
      case 'permission_timeout':
        if (
          !pendingPermission.value ||
          pendingPermission.value.permission_id === payload.permission_id ||
          pendingPermission.value.id === payload.permission_id
        ) {
          pendingPermission.value = null;
        }
        statusText.value = payload.message || '权限请求超时，已自动拒绝';
        break;
      case 'lifecycle':
        readCapabilitySnapshot(payload.result || {});
        break;
      case 'status':
        statusText.value = payload.message || '';
        recovering.value = /重连|恢复/.test(statusText.value);
        break;
      case 'turn_done':
        localTurnPending = false;
        isStreaming.value = false;
        recovering.value = false;
        statusText.value = '';
        break;
      case 'error':
        localTurnPending = false;
        isStreaming.value = false;
        recovering.value = false;
        errorText.value = payload.message || 'CLI Agent 执行失败';
        break;
      case 'disconnected':
        localTurnPending = false;
        isStreaming.value = false;
        recovering.value = false;
        statusText.value = payload.message || 'CLI Agent 连接已断开';
        break;
      default:
        break;
    }
  }

  async function sendMessage(content: string) {
    const targetSessionId = sourceValue(sessionId);
    if (!targetSessionId || !content.trim()) return;
    errorText.value = '';
    statusText.value = '';
    localTurnPending = true;
    isStreaming.value = true;
    appendCompleteMessage('user', content.trim(), true);
    try {
      await axios.post(`/api/plug/cli-agents/sessions/${targetSessionId}/send`, {
        content: content.trim(),
      });
    } catch (error) {
      localTurnPending = false;
      isStreaming.value = false;
      throw error;
    }
  }

  async function respondPermission(decision: string) {
    const permissionId = pendingPermission.value?.permission_id || pendingPermission.value?.id;
    if (!permissionId) return;
    await axios.post(`/api/plug/cli-agents/permissions/${permissionId}/respond`, {
      decision,
    });
    pendingPermission.value = null;
  }

  async function setModel(modelId: string) {
    const targetSessionId = sourceValue(sessionId);
    if (!targetSessionId || !modelId) return;
    await axios.post(`/api/plug/cli-agents/sessions/${targetSessionId}/model`, {
      model_id: modelId,
    });
  }

  async function setMode(modeId: string) {
    const targetSessionId = sourceValue(sessionId);
    if (!targetSessionId || !modeId) return;
    await axios.post(`/api/plug/cli-agents/sessions/${targetSessionId}/mode`, {
      mode_id: modeId,
    });
  }

  function appendCompleteMessage(role: string, content: string, optimistic = false) {
    const text = String(content || '');
    if (!text) return;
    const last = messages.value[messages.value.length - 1];
    if (role === 'user' && last?.role === 'user' && last.content === text) return;
    messages.value.push({
      id: `cli-${role}-${optimistic ? 'local-' : ''}${Date.now()}-${messages.value.length}`,
      role: role === 'user' ? 'user' : 'assistant',
      content: text,
      created_at: new Date().toISOString(),
    });
  }

  function appendToStreamingMessage(text: string) {
    if (!text) return;
    const last = messages.value[messages.value.length - 1];
    if (last?.role === 'assistant' && last.id.startsWith('cli-stream-')) {
      last.content += text;
      return;
    }
    messages.value.push({
      id: `cli-stream-${Date.now()}`,
      role: 'assistant',
      content: text,
      created_at: new Date().toISOString(),
    });
  }

  function upsertToolCallMessage(payload: any) {
    const toolCall = normalizeToolCall(payload);
    const messageId = `cli-tool-${toolCall.id}`;
    const content = JSON.stringify({
      type: 'tool_call',
      tool_calls: [toolCall],
    });
    const existing = messages.value.findIndex(
      (message) => message.role === 'tool' && message.id === messageId,
    );
    if (existing >= 0) {
      messages.value[existing] = {
        ...messages.value[existing],
        content,
      };
      return;
    }
    messages.value.push({
      id: messageId,
      role: 'tool',
      content,
      created_at: new Date().toISOString(),
    });
  }

  function normalizeToolCall(payload: any) {
    const fallbackId = payload?.toolCallId || payload?.tool_call_id || payload?.id || payload?.seq || Date.now();
    const args = payload?.args || payload?.rawInput || payload?.input || payload?.tool_call?.input || {};
    const result = payload?.result ?? payload?.rawOutput ?? payload?.output;
    return {
      id: String(fallbackId),
      name: String(payload?.name || payload?.toolName || payload?.title || payload?.tool_call?.name || 'tool'),
      status: String(payload?.status || 'running'),
      kind: payload?.kind || '',
      args: args && typeof args === 'object' ? args : { input: args },
      result,
      ts: Number(payload?.ts || Date.now() / 1000),
      finished_ts: payload?.finished_ts,
      raw: payload?.raw || payload,
    };
  }

  function readCapabilitySnapshot(result: any) {
    if (!result || typeof result !== 'object') return;
    capabilities.value =
      result.agentCapabilities ||
      result.capabilities ||
      result.agentInfo?.capabilities ||
      {};
    modelOptions.value = normalizeModels(
      result.models?.availableModels ||
      result.availableModels ||
      result.agentInfo?.models?.availableModels ||
      [],
    );
    currentModelId.value = String(
      result.models?.currentModelId ||
      result.currentModelId ||
      result.agentInfo?.models?.currentModelId ||
      currentModelId.value ||
      '',
    );
    modeOptions.value = normalizeModes(
      result.modes?.availableModes ||
      result.availableModes ||
      result.agentInfo?.modes?.availableModes ||
      [],
    );
    currentModeId.value = String(
      result.modes?.currentModeId ||
      result.currentModeId ||
      result.agentInfo?.modes?.currentModeId ||
      currentModeId.value ||
      '',
    );
  }

  function normalizeModels(items: any[]) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => {
        const value = String(item?.modelId || item?.id || item?.value || '');
        const label = String(item?.name || item?.label || value);
        return value ? { label, value } : null;
      })
      .filter(Boolean) as { label: string; value: string }[];
  }

  function normalizeModes(items: any[]) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => {
        const value = String(item?.id || item?.modeId || item?.value || '');
        const label = String(item?.name || item?.label || value);
        return value ? { label, value } : null;
      })
      .filter(Boolean) as { label: string; value: string }[];
  }

  onUnmounted(disconnect);

  return {
    messages,
    isStreaming,
    connected,
    capabilities,
    modelOptions,
    modeOptions,
    currentModelId,
    currentModeId,
    pendingPermission,
    errorText,
    statusText,
    recovering,
    connect,
    disconnect,
    applyCapabilitySnapshot: readCapabilitySnapshot,
    sendMessage,
    respondPermission,
    setModel,
    setMode,
  };
}
