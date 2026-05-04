<template>
  <div class="work-progress-timeline" :class="{ 'is-dark': isDark }">
    <div v-if="activeCards.length" class="hitl-section">
      <InteractionCardComponent
        v-for="card in activeCards"
        :key="card.interaction_id"
        :card="card"
        :is-dark="isDark"
        @respond="emit('interaction-respond', $event)"
      />
    </div>

    <div v-if="task" class="timeline-item intro">
      <div class="item-icon">
        <v-icon size="17" icon="mdi-clipboard-text-outline" />
      </div>
      <div class="item-body">
        <div class="item-title">{{ task.name }}</div>
        <div class="item-text">{{ task.description || '任务已创建，等待执行进展。' }}</div>
      </div>
    </div>

    <div v-for="item in items" :key="item.id" class="timeline-item" :class="`event-${item.kind}`">
      <div class="item-icon">
        <v-icon size="17" :icon="item.icon" />
      </div>
      <div class="item-body">
        <div class="item-meta">
          <span>{{ item.title }}</span>
          <time v-if="item.created_at">{{ formatDate(item.created_at) }}</time>
        </div>
        <pre v-if="item.text" class="item-text">{{ item.text }}</pre>
        <pre v-if="item.payload" class="item-payload">{{ item.payload }}</pre>
      </div>
    </div>

    <div v-if="!items.length && !activeCards.length" class="empty-state">
      暂无执行输出
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';

const props = withDefaults(defineProps<{
  task?: any | null;
  logs?: any[];
  activeCards?: any[];
  isDark?: boolean;
  maxItems?: number;
}>(), {
  task: null,
  logs: () => [],
  activeCards: () => [],
  isDark: false,
  maxItems: 120,
});

const emit = defineEmits<{
  (e: 'interaction-respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

const items = computed(() => {
  const visible = props.logs.slice(-props.maxItems);
  const merged: TimelineItem[] = [];
  let textBuffer: TimelineItem | null = null;

  const flushText = () => {
    if (textBuffer) {
      merged.push(textBuffer);
      textBuffer = null;
    }
  };

  for (const log of visible) {
    const item = toTimelineItem(log);
    if (!item) continue;
    if (item.kind === 'text') {
      if (!textBuffer) {
        textBuffer = { ...item };
      } else {
        textBuffer.text = joinDeltaText(textBuffer.text, item.text);
        textBuffer.created_at = item.created_at || textBuffer.created_at;
      }
      continue;
    }
    flushText();
    merged.push(item);
  }
  flushText();
  return merged;
});

type TimelineItem = {
  id: string;
  kind: string;
  icon: string;
  title: string;
  text: string;
  payload: string;
  created_at?: string;
};

function toTimelineItem(log: any): TimelineItem | null {
  const data = log?.data || {};
  const event = data.event || 'log';
  if (event === 'interaction') return null;

  if (event === 'text_delta') {
    return baseItem(log, 'text', 'mdi-message-text-outline', '智能体输出', String(data.text || log.message || ''));
  }
  if (event === 'reasoning') {
    return baseItem(log, 'reasoning', 'mdi-brain', '推理过程', String(data.text || log.message || ''));
  }
  if (event === 'tool_call') {
    return baseItem(log, 'tool', 'mdi-tools', `工具调用：${data.name || data.tool || 'tool'}`, '', compactPayload(data));
  }
  if (event === 'tool_result') {
    return baseItem(log, 'tool', 'mdi-check-decagram-outline', `工具结果：${data.name || data.tool || 'tool'}`, stringifyToolResult(data));
  }
  if (event === 'token') {
    const counts = tokenCounts(data);
    const text = [
      `输入 ${formatTokens(counts.input)}`,
      `输出 ${formatTokens(counts.output)}`,
      `总计 ${formatTokens(counts.total)}`,
    ].join(' · ');
    return baseItem(log, 'token', 'mdi-counter', 'Token 统计', text);
  }
  if (event === 'phase') {
    return baseItem(log, 'phase', 'mdi-timeline-clock-outline', phaseTitle(data), data.message || log.message || '');
  }
  if (event === 'error' || log.level === 'error') {
    return baseItem(log, 'error', 'mdi-alert-circle-outline', '错误', data.message || log.message || '');
  }

  const text = data.message || log.message || '';
  return text ? baseItem(log, 'log', 'mdi-text-box-outline', '日志', text) : null;
}

function baseItem(log: any, kind: string, icon: string, title: string, text: string, payload = ''): TimelineItem {
  return {
    id: String(log.id || `${kind}-${log.created_at || Math.random()}`),
    kind,
    icon,
    title,
    text,
    payload,
    created_at: log.created_at,
  };
}

function phaseTitle(data: any) {
  const phase = data.phase || data.status || '';
  const map: Record<string, string> = {
    started: '任务已启动',
    plan_done: '规划完成',
    execute_done: '实施完成',
    review_done: '审查完成',
    done: '任务结束',
    running: '执行中',
    waiting_feedback: '等待人工确认',
    completed: '已完成',
    failed: '失败',
  };
  return map[phase] || '阶段更新';
}

function compactPayload(data: any) {
  const payload = { ...data };
  delete payload.event;
  delete payload.text;
  return formatJson(payload);
}

function stringifyToolResult(data: any) {
  const result = data.result ?? data.output ?? data.content ?? data.message;
  if (result == null) return '';
  return typeof result === 'string' ? result : formatJson(result);
}

function joinDeltaText(current: string, next: string) {
  if (!current) return next;
  if (!next) return current;
  if (/^[，。！？；：、,.!?;:)\]}]/.test(next)) return `${current}${next}`;
  if (/[\s([{（【]$/.test(current) || /^[\s]/.test(next)) return `${current}${next}`;
  if (/^[A-Za-z0-9_]/.test(next) && /[A-Za-z0-9_]$/.test(current)) return `${current} ${next}`;
  return `${current}${next}`;
}

function formatJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
}

function formatTokens(value: number) {
  const n = Number(value || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function tokenCounts(data: any) {
  const stats = data.stats || {};
  const usage = stats.token_usage || {};
  const input = Number(data.input_tokens ?? data.input ?? usage.input_other ?? usage.input ?? 0);
  const output = Number(data.output_tokens ?? data.output ?? usage.output ?? 0);
  const total = Number(data.total_tokens ?? data.total ?? usage.total ?? input + output);
  return { input, output, total };
}

function formatDate(value: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
</script>

<style scoped>
.work-progress-timeline {
  --timeline-border: rgba(var(--v-border-color), 0.16);
  --timeline-muted: rgba(var(--v-theme-on-surface), 0.58);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.work-progress-timeline.is-dark {
  --timeline-border: rgba(255, 255, 255, 0.1);
}

.hitl-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 4px;
}

.timeline-item {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 10px;
  width: 100%;
}

.item-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--timeline-border);
  border-radius: 50%;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.item-body {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--timeline-border);
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.86);
}

.item-title {
  font-weight: 750;
}

.item-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  color: var(--timeline-muted);
  font-size: 12px;
}

.item-meta span {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 650;
}

.item-text,
.item-payload {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
  font: inherit;
  line-height: 1.58;
}

.item-payload {
  max-height: 280px;
  overflow: auto;
  padding: 8px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.055);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.event-error .item-icon {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.08);
}

.event-token .item-icon,
.event-phase .item-icon {
  color: rgb(var(--v-theme-info));
  background: rgba(var(--v-theme-info), 0.08);
}

.empty-state {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--timeline-muted);
  font-size: 13px;
}
</style>
