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

    <div v-for="item in items" :key="item.id" class="tl-entry" :class="`kind-${item.kind}`">
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
              <div class="tl-section-title">Args</div>
              <pre class="tl-json">{{ item.args }}</pre>
            </div>
          </template>

          <template v-if="item.kind === 'tool_result' && item.result">
            <div class="tl-section">
              <div class="tl-section-title">Result</div>
              <pre class="tl-json">{{ item.result }}</pre>
            </div>
          </template>

          <template v-if="item.kind === 'reasoning'">
            <pre class="tl-text reasoning-text">{{ item.text }}</pre>
          </template>

          <template v-if="item.kind === 'text_delta'">
            <pre class="tl-text output-text">{{ item.text }}</pre>
          </template>

          <template v-if="item.kind === 'error'">
            <pre class="tl-text error-text">{{ item.text }}</pre>
          </template>

          <pre v-if="item.kind === 'token'" class="tl-text token-text">{{ item.text }}</pre>

          <pre v-if="item.kind === 'log' || item.kind === 'phase'" class="tl-text log-text">{{ item.text }}</pre>

          <div v-if="item.kind === 'artifact' && item.content" class="tl-artifact">
            <div class="tl-section-title">交付内容</div>
            <pre class="tl-text">{{ item.content }}</pre>
          </div>

          <div v-if="item.kind === 'interaction' && item.card" class="tl-interaction">
            <InteractionCardComponent
              :card="item.card"
              :is-dark="isDark"
              @respond="onRespond"
            />
          </div>

          <pre v-if="item.kind === 'hitl_resolved' && item.text" class="tl-text log-text">{{ item.text }}</pre>
        </div>
      </div>
    </div>

    <div v-if="loading" class="tl-loading">
      <v-progress-circular indeterminate size="16" width="2" />
      <span>执行中...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';

const props = withDefaults(defineProps<{
  task?: any | null;
  logs?: any[];
  activeCards?: any[];
  isDark?: boolean;
  maxItems?: number;
  loading?: boolean;
}>(), {
  task: null,
  logs: () => [],
  activeCards: () => [],
  isDark: false,
  maxItems: 0,
  loading: false,
});

const emit = defineEmits<{
  (e: 'interaction-respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

const collapsedIds = ref<Set<string>>(new Set());
let prevLogCount = 0;

watch(() => props.logs, (newLogs) => {
  if (newLogs.length < prevLogCount) {
    prevLogCount = newLogs.length;
  }
}, { immediate: false });

function toggleCollapse(id: string) {
  const next = new Set(collapsedIds.value);
  if (next.has(id)) next.delete(id); else next.add(id);
  collapsedIds.value = next;
}

function isCollapsed(id: string) {
  return collapsedIds.value.has(id);
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
}

function kindLabel(kind: string) {
  const map: Record<string, string> = {
    text_delta: '输出', reasoning: '推理', tool_call: '工具调用',
    tool_result: '工具结果', token: 'Token', phase: '阶段',
    error: '错误', artifact: '交付物', interaction: '交互',
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

function formatTokens(n: number) {
  const v = Number(n || 0);
  if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return `${v}`;
}

const items = computed<TimelineItem[]>(() => {
  const logs = props.logs || [];
  const result: TimelineItem[] = [];
  let prevTs: number | null = null;

  for (let i = 0; i < logs.length; i++) {
    const log = logs[i];
    const data = log?.data || {};
    const event = data.event || 'log';
    const ts = log.created_at ? Date.parse(log.created_at) : 0;
    const dur = prevTs && ts ? Math.max(0, ts - prevTs) : undefined;

    if (event === 'text_delta') {
      const text = String(data.text || log.message || '');
      if (!text) continue;
      result.push({
        id: log.id || `log-${i}`, kind: 'text_delta', icon: 'mdi-message-text-outline',
        title: data.step_label || data.agent || '智能体输出', text, created_at: log.created_at,
        duration_ms: dur ? Math.min(dur, 30000) : undefined, collapsible: false,
      });
    } else if (event === 'reasoning') {
      const text = String(data.text || log.message || '');
      const item: TimelineItem = {
        id: log.id || `log-${i}`, kind: 'reasoning', icon: 'mdi-brain',
        title: '推理过程', text, created_at: log.created_at,
        duration_ms: dur ? Math.min(dur, 30000) : undefined, collapsible: true,
      };
      collapsedIds.value.add(item.id);
      result.push(item);
    } else if (event === 'tool_call') {
      const name = data.name || data.tool || 'tool';
      const argsObj = { ...data };
      delete argsObj.event; delete argsObj.name; delete argsObj.tool; delete argsObj.ts; delete argsObj.id;
      result.push({
        id: log.id || `log-${i}`, kind: 'tool_call', icon: 'mdi-wrench-outline',
        title: `调用工具：${name}`, args: JSON.stringify(argsObj, null, 2),
        text: '', created_at: log.created_at, duration_ms: dur ? Math.min(dur, 30000) : undefined, collapsible: true,
      });
    } else if (event === 'tool_result') {
      const name = data.name || data.tool || 'tool';
      let resultStr = '';
      if (data.result !== undefined) {
        resultStr = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
      } else {
        resultStr = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      }
      const bytes = new TextEncoder().encode(resultStr).length;
      const lines = resultStr.split('\n').length;
      result.push({
        id: log.id || `log-${i}`, kind: 'tool_result', icon: 'mdi-check-circle-outline',
        title: `工具结果：${name}`, subtitle: `${formatDur(dur || 0)} · ${lines}行 · ${bytes >= 1024 ? (bytes / 1024).toFixed(1) + 'KB' : bytes + 'B'}`,
        result: resultStr, text: '', created_at: log.created_at,
        duration_ms: dur ? Math.min(dur, 30000) : undefined, collapsible: true,
      });
    } else if (event === 'token') {
      const counts = tokenCounts(data);
      result.push({
        id: log.id || `log-${i}`, kind: 'token', icon: 'mdi-cash-multiple',
        title: 'Token 统计',
        text: [`入 ${formatTokens(counts.input)}`, `出 ${formatTokens(counts.output)}`, `共 ${formatTokens(counts.total)}`].join(' · '),
        created_at: log.created_at, collapsible: false,
      });
    } else if (event === 'phase') {
      result.push({
        id: log.id || `log-${i}`, kind: 'phase', icon: 'mdi-timeline-clock-outline',
        title: phaseTitle(data), text: data.message || log.message || '',
        created_at: log.created_at, collapsible: false,
      });
    } else if (event === 'interaction') {
      const card = data.interaction_id ? data : null;
      result.push({
        id: log.id || `log-${i}`, kind: 'interaction', icon: 'mdi-account-question-outline',
        title: data.title || '等待人工确认', text: data.body || log.message || '',
        card, created_at: log.created_at, collapsible: Boolean(card),
      });
    } else if (event === 'hitl_resolved') {
      const actionLabels: Record<string, string> = { approve: '批准执行', modify: '调整计划', reject: '拒绝', retry: '继续返工', finish: '接受当前结果', cancel: '取消任务' };
      const label = actionLabels[data.action_key] || data.action_key || '';
      const fields = data.field_values || {};
      const feedback = fields.modify_text || fields.guidance || fields.feedback || '';
      result.push({
        id: log.id || `log-${i}`, kind: 'hitl_resolved', icon: 'mdi-account-check-outline',
        title: `已处理：${label}`, text: feedback,
        created_at: log.created_at, collapsible: false,
      });
    } else if (event === 'error' || log.level === 'error') {
      result.push({
        id: log.id || `log-${i}`, kind: 'error', icon: 'mdi-alert-circle-outline',
        title: '错误', text: data.message || log.message || '',
        created_at: log.created_at, collapsible: false,
      });
    } else if (event === 'artifact') {
      result.push({
        id: log.id || `log-${i}`, kind: 'artifact', icon: 'mdi-file-document-outline',
        title: data.title || '交付物', content: data.content || log.message || '',
        text: '', created_at: log.created_at, collapsible: false,
      });
    } else {
      const text = data.message || log.message || '';
      if (text) {
        result.push({
          id: log.id || `log-${i}`, kind: 'log', icon: 'mdi-text-box-outline',
          title: '日志', text, created_at: log.created_at, collapsible: false,
        });
      }
    }
    prevTs = ts;
  }

  if (props.maxItems && props.maxItems > 0) return result.slice(-props.maxItems);
  return result;
});

function tokenCounts(data: any) {
  return {
    input: Number(data.input_tokens || data.prompt_tokens || 0),
    output: Number(data.output_tokens || data.completion_tokens || 0),
    total: Number(data.total_tokens || (data.input_tokens || 0) + (data.output_tokens || 0)),
  };
}

function phaseTitle(data: any) {
  const map: Record<string, string> = {
    prepare: '准备阶段', plan: '规划阶段', execute: '执行阶段',
    review: '审查阶段', finalize: '交付', done: '已完成',
    approval: '等待审批', rework: '返工',
  };
  const phase = data.phase || data.stage || '';
  return map[phase] || phase || '阶段更新';
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

.token-text {
  text-align: center;
  font-family: 'Courier New', monospace;
  font-size: 11px;
}

.tl-interaction {
  padding: 4px 0;
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
