<template>
  <div class="progress-timeline" :class="{ 'theme-dark': isDark }">
    <div v-if="activeCards && activeCards.length" class="active-cards-section">
      <InteractionCardComponent
        v-for="card in activeCards"
        :key="card.interaction_id"
        :card="card"
        :is-dark="isDark"
        :resolved="card._resolved"
        @respond="onRespond"
      />
    </div>

    <div v-if="!items.length && !activeCards.length && !loading" class="empty-hint">暂无执行进展</div>

    <template v-for="item in items" :key="item.id">
      <WorkAgentCallCard
        v-if="item.kind === 'agent_call'"
        :call="item.call"
        :is-dark="isDark"
      />

      <div v-else class="tl-entry" :class="`kind-${item.kind}`">
        <div class="tl-node">
          <v-icon size="16" :icon="item.icon" />
        </div>

        <div class="tl-body">
          <div class="tl-header" @click="item.collapsible ? toggleCollapse(item.id) : undefined" :class="{ clickable: item.collapsible }">
            <span class="tl-title">
              <span class="tl-kind-badge" :class="`badge-${item.kind}`">{{ kindLabel(item.kind) }}</span>
              {{ item.title }}
              <span v-if="item.subtitle" class="tl-subtitle">· {{ item.subtitle }}</span>
            </span>
            <span class="tl-right">
              <time v-if="item.created_at" class="tl-time">{{ formatTime(item.created_at) }}</time>
              <span v-if="item.duration_ms" class="tl-dur">{{ formatDur(item.duration_ms) }}</span>
              <v-icon v-if="item.collapsible" size="14" :icon="isCollapsed(item.id) ? 'mdi-chevron-down' : 'mdi-chevron-up'" />
            </span>
          </div>

          <div v-if="!isCollapsed(item.id)" class="tl-content">
            <template v-if="item.kind === 'tool_call' && item.args">
              <div class="tl-section">
                <div class="tl-section-title">内容</div>
                <pre class="tl-json">{{ item.args }}</pre>
              </div>
            </template>

            <template v-if="item.kind === 'tool_result' && item.result">
              <div class="tl-section">
                <div class="tl-section-title">结果</div>
                <pre class="tl-json">{{ item.result }}</pre>
              </div>
            </template>

            <template v-if="item.kind === 'reasoning'">
              <pre class="tl-text reasoning-text">{{ item.text }}</pre>
            </template>

            <template v-if="item.kind === 'text_delta'">
              <button
                v-if="item.reasoning"
                class="reasoning-toggle"
                type="button"
                @click.stop="toggleReasoning(item.id)"
              >
                <v-icon size="15" icon="mdi-brain" />
                <span>思考过程</span>
                <v-icon size="15" :icon="isReasoningCollapsed(item.id) ? 'mdi-chevron-right' : 'mdi-chevron-down'" />
              </button>
              <pre v-if="item.reasoning && !isReasoningCollapsed(item.id)" class="tl-text reasoning-text">{{ item.reasoning }}</pre>
              <pre class="tl-text output-text">{{ item.text }}</pre>
            </template>

            <template v-if="item.kind === 'error'">
              <pre class="tl-text error-text">{{ item.text }}</pre>
            </template>

            <div v-if="item.kind === 'artifact' && item.content" class="tl-artifact">
              <div class="tl-section-title">交付内容</div>
              <pre class="tl-text">{{ item.content }}</pre>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="loading" class="tl-loading">
      <v-progress-circular indeterminate size="16" width="2" />
      <span>执行中...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';
import WorkAgentCallCard from '@/components/work/WorkAgentCallCard.vue';

const props = withDefaults(defineProps<{
  task?: any | null;
  logs?: any[];
  activeCards?: any[];
  isDark?: boolean;
  maxItems?: number;
  loading?: boolean;
  agentLabel?: string;
}>(), {
  task: null,
  logs: () => [],
  activeCards: () => [],
  isDark: false,
  maxItems: 0,
  loading: false,
  agentLabel: '',
});

const emit = defineEmits<{
  (e: 'interaction-respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

const collapsedIds = ref<Set<string>>(new Set());
const collapsedReasoningIds = ref<Set<string>>(new Set());
const initializedCollapsedIds = ref<Set<string>>(new Set());
const initializedReasoningIds = ref<Set<string>>(new Set());
let prevLogCount = 0;

watch(() => props.logs, (newLogs) => {
  if (newLogs.length < prevLogCount) {
    collapsedIds.value = new Set();
    collapsedReasoningIds.value = new Set();
    initializedCollapsedIds.value = new Set();
    initializedReasoningIds.value = new Set();
  }
  prevLogCount = newLogs.length;
}, { immediate: false });

function toggleCollapse(id: string) {
  const next = new Set(collapsedIds.value);
  if (next.has(id)) next.delete(id); else next.add(id);
  collapsedIds.value = next;
}

function isCollapsed(id: string) {
  return collapsedIds.value.has(id);
}

function toggleReasoning(id: string) {
  const next = new Set(collapsedReasoningIds.value);
  if (next.has(id)) next.delete(id); else next.add(id);
  collapsedReasoningIds.value = next;
}

function isReasoningCollapsed(id: string) {
  return collapsedReasoningIds.value.has(id);
}

function onRespond(payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }) {
  for (const card of (props.activeCards || [])) {
    if (card.interaction_id === payload.interaction_id) {
      card._resolved = {
        status: payload.action_key === 'confirm' ? 'confirmed' : payload.action_key === 'cancel' ? 'cancelled' : 'rejected',
        message: `已完成 — ${payload.action_key}`,
      };
    }
  }
  emit('interaction-respond', payload);
}

interface TimelineItem {
  id: string;
  kind: string;
  icon: string;
  title: string;
  subtitle?: string;
  text: string;
  args?: string;
  result?: string;
  content?: string;
  card?: any;
  created_at: string;
  duration_ms?: number;
  collapsible: boolean;
  reasoning?: string;
  traceKey?: string;
  call?: any;
}

function kindLabel(kind: string) {
  const map: Record<string, string> = {
    text_delta: '输出', reasoning: '思考', tool_call: '使用工具',
    tool_result: '工具结果', error: '错误', artifact: '交付物',
  };
  return map[kind] || kind;
}

function formatTime(v: string) {
  if (!v) return '';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDur(ms: number) {
  if (!ms || ms < 0) return '';
  if (ms < 1000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  return rs > 0 ? `${m}m${rs}s` : `${m}m`;
}

const items = computed<TimelineItem[]>(() => {
  const logs = props.logs || [];
  const result: TimelineItem[] = [];
  let prevTs: number | null = null;
  let textBuffer: TimelineItem | null = null;
  const pendingReasoning = new Map<string, { text: string; created_at: string; duration_ms?: number; title: string; id: string }>();
  const agentCallItems = new Map<string, TimelineItem>();

  const pushItem = (item: TimelineItem) => {
    if (item.kind !== 'text_delta' && item.collapsible && !initializedCollapsedIds.value.has(item.id)) {
      initializedCollapsedIds.value.add(item.id);
      collapsedIds.value.add(item.id);
    }
    if (item.kind === 'text_delta' && item.reasoning && !initializedReasoningIds.value.has(item.id)) {
      initializedReasoningIds.value.add(item.id);
      collapsedReasoningIds.value.add(item.id);
    }
    result.push(item);
  };

  const ensureAgentCall = (log: any, data: any, index: number): TimelineItem => {
    const callId = String(data.call_id || '');
    let item = agentCallItems.get(callId);
    if (item) return item;
    const call = {
      callId,
      attempt: Number(data.call_attempt || 1),
      agentId: data.agent_id || '',
      agentLabel: agentDisplay(data),
      nodeId: data.node_id || '',
      nodeLabel: nodeLabel(data.node_id || data.stage_id || ''),
      stepId: data.step_id || '',
      stepLabel: data.step_label || '',
      stageId: data.stage_id || '',
      status: data.agent_call_status || 'running',
      providerId: data.provider_id || '',
      model: data.model || '',
      tools: data.func_tools || [],
      inputPayload: data.input_payload || {},
      startedAt: log.created_at,
      completedAt: '',
      durationMs: data.duration_ms || 0,
      token: {},
      outputSegments: [] as any[],
      reasoningSegments: [] as any[],
    };
    item = {
      id: `agent-call-${callId || log.id || index}`,
      kind: 'agent_call',
      icon: 'mdi-robot-outline',
      title: `${call.agentLabel} 调用`,
      text: '',
      created_at: log.created_at,
      collapsible: false,
      call,
    };
    agentCallItems.set(callId, item);
    pushItem(item);
    return item;
  };

  const appendTextToCall = (call: any, lane: string, text: string) => {
    if (!text) return;
    const segments = lane === 'reasoning' ? call.reasoningSegments : call.outputSegments;
    const last = segments[segments.length - 1];
    if (last?.kind === 'text') {
      last.text += text;
    } else {
      segments.push({ kind: 'text', text });
    }
  };

  const appendToolToCall = (call: any, lane: string, event: string, data: any, dur?: number, createdAt?: string) => {
    const segments = lane === 'reasoning' ? call.reasoningSegments : call.outputSegments;
    const toolId = String(data.tool_call_id || data.id || `${data.name || data.tool || 'tool'}-${segments.length}`);
    const name = data.name || data.tool || 'tool';
    const eventTs = createdAt ? Date.parse(createdAt) / 1000 : Date.now() / 1000;
    if (event === 'tool_call') {
      const argsObj = { ...data };
      stripTraceFields(argsObj);
      segments.push({
        kind: 'tool',
        toolCallId: toolId,
        id: toolId,
        name,
        args: JSON.stringify(argsObj, null, 2),
        result: '',
        ts: Number.isFinite(eventTs) ? eventTs : Date.now() / 1000,
        finishedTs: 0,
        duration: dur ? formatDur(dur) : '',
      });
      return;
    }
    const matched = [...call.outputSegments, ...call.reasoningSegments]
      .reverse()
      .find((segment: any) => segment.kind === 'tool' && segment.toolCallId === toolId);
    let resultStr = '';
    if (data.result !== undefined) {
      resultStr = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
    } else {
      resultStr = JSON.stringify(data, null, 2);
    }
    if (matched) {
      matched.result = resultStr;
      matched.duration = dur ? formatDur(dur) : matched.duration;
      matched.finishedTs = Number.isFinite(eventTs) ? eventTs : Date.now() / 1000;
    } else {
      segments.push({
        kind: 'tool',
        toolCallId: toolId,
        id: toolId,
        name,
        args: '',
        result: resultStr,
        ts: Number.isFinite(eventTs) ? eventTs : Date.now() / 1000,
        finishedTs: Number.isFinite(eventTs) ? eventTs : Date.now() / 1000,
        duration: dur ? formatDur(dur) : '',
      });
    }
  };

  const applyAgentCallEvent = (item: TimelineItem, log: any, data: any, event: string, dur?: number) => {
    const call = item.call;
    if (event === 'agent_call_start') {
      call.status = data.agent_call_status || call.status || 'running';
      call.providerId = data.provider_id || call.providerId;
      call.model = data.model || call.model;
      call.tools = data.func_tools || call.tools;
      call.inputPayload = data.input_payload || call.inputPayload;
      call.startedAt = log.created_at || call.startedAt;
      return;
    }
    if (event === 'agent_call_end') {
      call.status = data.agent_call_status || call.status || 'completed';
      call.completedAt = log.created_at || call.completedAt;
      call.durationMs = data.duration_ms || call.durationMs;
      return;
    }
    if (event === 'text_delta' || event === 'reasoning') {
      appendTextToCall(call, data.lane || (event === 'reasoning' ? 'reasoning' : 'output'), String(data.text || log.message || ''));
      return;
    }
    if (event === 'tool_call' || event === 'tool_result') {
      appendToolToCall(call, data.lane || 'reasoning', event, data, dur, log.created_at);
      return;
    }
    if (event === 'token') {
      call.token = { ...call.token, ...data };
      return;
    }
    if (event === 'error') {
      const lane = data.lane || 'output';
      const segments = lane === 'reasoning' ? call.reasoningSegments : call.outputSegments;
      const detailParts = [String(data.message || log.message || '')];
      if (data.diagnostic) detailParts.push(`诊断信息：\n${JSON.stringify(data.diagnostic, null, 2)}`);
      segments.push({ kind: 'error', text: detailParts.filter(Boolean).join('\n\n') });
      call.status = data.status || call.status;
    }
  };

  const flushTextBuffer = () => {
    if (textBuffer && textBuffer.text.trim()) {
      pushItem(textBuffer);
    }
    textBuffer = null;
  };

  for (let i = 0; i < logs.length; i++) {
    const log = logs[i];
    const data = log?.data || {};
    const event = data.event || 'log';
    const ts = log.created_at ? Date.parse(log.created_at) : 0;
    const dur = prevTs && ts ? Math.max(0, ts - prevTs) : undefined;

    if (data.call_id || event === 'agent_call_start' || event === 'agent_call_end') {
      flushTextBuffer();
      const callItem = ensureAgentCall(log, data, i);
      applyAgentCallEvent(callItem, log, data, event, dur ? Math.min(dur, 30000) : undefined);
      prevTs = ts;
      continue;
    }

    if (event === 'text_delta') {
      const text = String(data.text || log.message || '');
      if (!text) continue;
      const key = [
        data.stage_id || '',
        data.step_id || '',
        data.agent_id || '',
        data.agent_label || data.agent || '',
        data.step_label || '',
      ].join('|');
      if (!textBuffer || textBuffer.traceKey !== key) {
        flushTextBuffer();
        const agentLabel = agentDisplay(data);
        const pending = pendingReasoning.get(key);
        textBuffer = {
          id: log.id || `log-${i}`,
          kind: 'text_delta',
          icon: 'mdi-message-text-outline',
          title: `${agentLabel} 输出`,
          subtitle: data.step_label || '',
          text: '',
          created_at: log.created_at,
          duration_ms: dur ? Math.min(dur, 30000) : undefined,
          collapsible: false,
          reasoning: pending?.text || '',
          traceKey: key,
        };
        if (pending) pendingReasoning.delete(key);
      }
      textBuffer.text += text;
    } else if (event === 'reasoning') {
      const text = String(data.text || log.message || '');
      if (!text) continue;
      const key = [
        data.stage_id || '',
        data.step_id || '',
        data.agent_id || '',
        data.agent_label || data.agent || '',
        data.step_label || '',
      ].join('|');
      if (textBuffer && textBuffer.traceKey === key) {
        textBuffer.reasoning = `${textBuffer.reasoning || ''}${text}`;
      } else {
        const current = pendingReasoning.get(key);
        pendingReasoning.set(key, {
          id: current?.id || log.id || `log-${i}`,
          title: `${agentDisplay(data)} 思考过程`,
          text: `${current?.text || ''}${text}`,
          created_at: current?.created_at || log.created_at,
          duration_ms: current?.duration_ms || (dur ? Math.min(dur, 30000) : undefined),
        });
      }
    } else if (event === 'tool_call') {
      flushTextBuffer();
      const name = data.name || data.tool || 'tool';
      const argsObj = { ...data };
      stripTraceFields(argsObj);
      pushItem({
        id: log.id || `log-${i}`, kind: 'tool_call', icon: 'mdi-wrench-outline',
        title: `调用工具：${name}`, args: JSON.stringify(argsObj, null, 2),
        text: '', created_at: log.created_at, duration_ms: dur ? Math.min(dur, 30000) : undefined, collapsible: true,
      });
    } else if (event === 'tool_result') {
      flushTextBuffer();
      const name = data.name || data.tool || 'tool';
      let resultStr = '';
      if (data.result !== undefined) {
        resultStr = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
      } else {
        resultStr = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      }
      const bytes = new TextEncoder().encode(resultStr).length;
      const lines = resultStr.split('\n').length;
      pushItem({
        id: log.id || `log-${i}`, kind: 'tool_result', icon: 'mdi-check-circle-outline',
        title: `工具结果：${name}`, subtitle: `${formatDur(dur || 0)} · ${lines}行 · ${bytes >= 1024 ? (bytes / 1024).toFixed(1) + 'KB' : bytes + 'B'}`,
        result: resultStr, text: '', created_at: log.created_at,
        duration_ms: dur ? Math.min(dur, 30000) : undefined, collapsible: true,
      });
    } else if (event === 'token') {
      flushTextBuffer();
      continue;
    } else if (event === 'phase') {
      flushTextBuffer();
      continue;
    } else if (event === 'interaction') {
      flushTextBuffer();
      const args = formatInteractionArgs(data);
      pushItem({
        id: log.id || `log-${i}`,
        kind: 'tool_call',
        icon: 'mdi-account-question-outline',
        title: `HITL 请求：${data.title || '人工确认'}`,
        args,
        text: '',
        created_at: log.created_at,
        duration_ms: dur ? Math.min(dur, 30000) : undefined,
        collapsible: Boolean(args),
      });
    } else if (event === 'hitl_resolved') {
      flushTextBuffer();
      const actionLabels: Record<string, string> = { approve: '批准执行', modify: '调整计划', reject: '拒绝', retry: '继续返工', finish: '接受当前结果', cancel: '取消任务' };
      const label = actionLabels[data.action_key] || data.action_key || '';
      pushItem({
        id: log.id || `log-${i}`,
        kind: 'tool_result',
        icon: 'mdi-account-check-outline',
        title: `HITL 结果：${label || '已处理'}`,
        result: formatHitlResult(data),
        text: '',
        created_at: log.created_at,
        duration_ms: dur ? Math.min(dur, 30000) : undefined,
        collapsible: true,
      });
    } else if (event === 'error' || log.level === 'error') {
      flushTextBuffer();
      const detailParts = [String(data.message || log.message || '')];
      if (data.diagnostic) {
        detailParts.push(`诊断信息：\n${JSON.stringify(data.diagnostic, null, 2)}`);
      }
      if (data.retryable) detailParts.push('状态：可重试');
      pushItem({
        id: log.id || `log-${i}`, kind: 'error', icon: 'mdi-alert-circle-outline',
        title: '错误', text: detailParts.filter(Boolean).join('\n\n'),
        created_at: log.created_at, collapsible: true,
      });
    } else if (event === 'artifact') {
      flushTextBuffer();
      pushItem({
        id: log.id || `log-${i}`, kind: 'artifact', icon: 'mdi-file-document-outline',
        title: data.title || '交付物', content: data.content || log.message || '',
        text: '', created_at: log.created_at, collapsible: true,
      });
    } else {
      flushTextBuffer();
      continue;
    }
    prevTs = ts;
  }
  flushTextBuffer();
  for (const pending of pendingReasoning.values()) {
    pushItem({
      id: pending.id,
      kind: 'reasoning',
      icon: 'mdi-brain',
      title: pending.title,
      text: pending.text,
      created_at: pending.created_at,
      duration_ms: pending.duration_ms,
      collapsible: true,
    });
  }

  for (const item of result) {
    if (item.kind === 'text_delta') {
      item.traceKey = undefined;
      if (!item.subtitle) item.subtitle = undefined;
    }
  }

  if (props.maxItems && props.maxItems > 0) return result.slice(-props.maxItems);
  return result;
});

function stripTraceFields(data: Record<string, any>) {
  for (const key of ['event', 'name', 'tool', 'ts', 'id', 'stage_id', 'step_id', 'agent_id', 'agent_label', 'tool_call_id', 'call_id', 'call_attempt', 'lane', 'input_payload', 'agent_call_status']) {
    delete data[key];
  }
}

function nodeLabel(value: string) {
  const map: Record<string, string> = {
    clarify: '需求明确',
    plan: '规划',
    execute: '执行',
    review: '审查',
    finalize: '交付',
    stage_clarify: '需求明确',
    stage_plan: '规划',
    stage_execute: '执行',
    stage_review: '审查',
    stage_deliver: '交付',
  };
  return map[String(value || '')] || String(value || '');
}

function agentDisplay(data: any) {
  const label = data.agent_label || data.agent || data.executor || '';
  if (label && !looksLikeAgentId(label)) return label;
  return props.agentLabel || label || '智能体';
}

function looksLikeAgentId(value: unknown) {
  const text = String(value || '');
  return text.startsWith('agent_') || text.startsWith('expert_');
}

function formatInteractionArgs(data: any) {
  const parts: string[] = [];
  if (data.body) parts.push(String(data.body));
  const fields = Array.isArray(data.fields) ? data.fields : [];
  if (fields.length) {
    const lines = fields.map((field: any) => {
      const suffix = field.required ? '（必填）' : '';
      const recommended = field.recommended ? `，推荐：${field.recommended}` : '';
      return `- ${field.label || field.key}${suffix}${recommended}`;
    });
    parts.push(`需要用户填写：\n${lines.join('\n')}`);
  }
  const actions = Array.isArray(data.actions) ? data.actions : [];
  if (actions.length) {
    parts.push(`可选操作：${actions.map((action: any) => action.label || action.key).join(' / ')}`);
  }
  return parts.join('\n\n');
}

function formatHitlResult(data: any) {
  const fields = data.field_values || {};
  const lines = [`操作：${data.action_key || '已处理'}`];
  const fieldLines = Object.entries(fields)
    .filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== '')
    .map(([key, value]) => `${key}：${Array.isArray(value) ? value.join('、') : String(value)}`);
  if (fieldLines.length) lines.push(`用户输入：\n${fieldLines.join('\n')}`);
  return lines.join('\n');
}
</script>

<style scoped>
.progress-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 4px 0;
  min-height: 0;
  overflow: auto;
}

.tl-entry {
  display: flex;
  gap: 10px;
  padding: 8px 12px 8px 8px;
  border-left: 2px solid transparent;
  transition: background 0.12s;
}

.tl-entry:hover {
  background: rgba(var(--v-theme-on-surface), 0.025);
}

.tl-node {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.48);
}

.tl-body {
  flex: 1;
  min-width: 0;
}

.tl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 24px;
  cursor: default;
}

.tl-header.clickable {
  cursor: pointer;
}

.tl-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 550;
  color: rgba(var(--v-theme-on-surface), 0.82);
  min-width: 0;
  flex-wrap: wrap;
}

.tl-kind-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
  flex-shrink: 0;
}

.badge-text_delta { color: rgba(var(--v-theme-on-surface), 0.55); background: rgba(var(--v-theme-on-surface), 0.08); }
.badge-reasoning { color: rgb(var(--v-theme-secondary)); background: rgba(var(--v-theme-secondary), 0.1); }
.badge-tool_call { color: rgb(var(--v-theme-info)); background: rgba(var(--v-theme-info), 0.12); }
.badge-tool_result { color: rgb(var(--v-theme-success)); background: rgba(var(--v-theme-success), 0.12); }
.badge-token { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.1); }
.badge-phase { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.08); }
.badge-error { color: rgb(var(--v-theme-error)); background: rgba(var(--v-theme-error), 0.1); }
.badge-artifact { color: rgb(var(--v-theme-success)); background: rgba(var(--v-theme-success), 0.1); }
.badge-interaction { color: rgb(var(--v-theme-warning)); background: rgba(var(--v-theme-warning), 0.12); }
.badge-log { color: rgba(var(--v-theme-on-surface), 0.5); background: rgba(var(--v-theme-on-surface), 0.06); }

.tl-subtitle {
  font-size: 11px;
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.4);
}

.tl-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.tl-time {
  font-size: 10px;
  font-family: 'Courier New', monospace;
  color: rgba(var(--v-theme-on-surface), 0.38);
}

.tl-dur {
  font-size: 10px;
  font-family: 'Courier New', monospace;
  color: rgba(var(--v-theme-on-surface), 0.42);
}

.tl-content {
  margin-top: 6px;
}

.tl-section {
  margin-bottom: 8px;
}

.reasoning-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 4px 8px;
  border: 1px solid rgba(var(--v-border-color), 0.18);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  color: rgba(var(--v-theme-on-surface), 0.62);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.reasoning-toggle:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.tl-section-title {
  font-size: 10px;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: rgba(var(--v-theme-on-surface), 0.38);
  margin-bottom: 4px;
}

.tl-json {
  margin: 0;
  padding: 8px 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border-radius: 6px;
  border: 1px solid rgba(var(--v-border-color), 0.12);
  font-size: 11px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
  color: rgba(var(--v-theme-on-surface), 0.72);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
  max-height: 360px;
  overflow: auto;
  line-height: 1.5;
}

.tl-text {
  margin: 0;
  padding: 6px 8px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-radius: 6px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.68);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
  line-height: 1.5;
  max-height: 280px;
  overflow: auto;
}

.reasoning-text {
  border-left: 3px solid rgba(var(--v-theme-secondary), 0.35);
  background: rgba(var(--v-theme-secondary), 0.04);
}

.output-text {
  border-left: 3px solid rgba(var(--v-theme-primary), 0.22);
}

.error-text {
  color: rgb(var(--v-theme-error));
  font-weight: 550;
}

.tl-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.empty-hint {
  color: rgba(var(--v-theme-on-surface), 0.38);
  font-size: 12px;
  text-align: center;
  padding: 24px;
}

.active-cards-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 16px;
}

.kind-tool_call .tl-node { color: rgb(var(--v-theme-info)); background: rgba(var(--v-theme-info), 0.1); }
.kind-tool_result .tl-node { color: rgb(var(--v-theme-success)); background: rgba(var(--v-theme-success), 0.1); }
.kind-reasoning .tl-node { color: rgb(var(--v-theme-secondary)); background: rgba(var(--v-theme-secondary), 0.1); }
.kind-error .tl-node { color: rgb(var(--v-theme-error)); background: rgba(var(--v-theme-error), 0.1); }
.kind-token .tl-node { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.08); }
.kind-phase .tl-node { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.08); }
.kind-artifact .tl-node { color: rgb(var(--v-theme-success)); background: rgba(var(--v-theme-success), 0.1); }
</style>
