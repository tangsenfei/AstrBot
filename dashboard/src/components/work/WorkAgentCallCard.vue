<template>
  <div class="agent-call-card" :class="[`status-${statusClass}`, { 'theme-dark': isDark }]">
    <button class="agent-avatar-button" type="button" @click="inputDialog = true">
      <v-avatar :color="avatar.color" size="42">
        <v-icon v-if="avatar.icon" :icon="avatar.icon" size="22" />
        <span v-else class="avatar-initial">{{ avatar.initial }}</span>
      </v-avatar>
    </button>

    <div class="agent-call-main">
      <div class="agent-call-header">
        <div class="agent-call-title">
          <span class="agent-name">{{ call.agentLabel || '智能体' }}</span>
          <span class="agent-subtitle">{{ call.stepLabel || call.nodeLabel || 'LLM 调用' }}</span>
        </div>
        <div class="agent-call-meta">
          <span v-if="call.providerId || call.model" class="meta-text">{{ providerText }}</span>
        </div>
      </div>
      <div v-if="showStatusChip || durationText || tokenText" class="agent-call-stats">
        <v-chip v-if="showStatusChip" size="x-small" variant="tonal" :color="statusColor">{{ statusText }}</v-chip>
        <span v-if="durationText" class="stat-item">耗时 {{ durationText }}</span>
        <span v-if="tokenText" class="stat-item">{{ tokenText }}</span>
      </div>

      <div v-if="hasReasoning" class="lane-section">
        <ReasoningBlock
          :parts="reasoningParts"
          :is-dark="isDark"
          :initial-expanded="false"
          :is-streaming="isRunning"
          :has-non-reasoning-content="hasOutput"
        />
      </div>

      <div v-if="hasOutput" class="lane-section output-section">
        <button class="output-header" type="button" @click="toggleOutput">
          <span class="output-header-left">
            <v-icon size="17" icon="mdi-message-text-outline" />
            <span>输出</span>
          </span>
          <span class="output-header-right">
            <span class="output-summary">{{ outputSummary }}</span>
            <v-icon size="20" class="output-chevron" :class="{ expanded: outputOpen }">
              mdi-chevron-right
            </v-icon>
          </span>
        </button>
        <div v-if="outputOpen" class="output-content">
          <template v-for="(segment, index) in call.outputSegments" :key="`out-${index}`">
            <pre v-if="segment.kind === 'text'" class="segment-text output-text">{{ segment.text }}</pre>
            <ToolCallCard
              v-else-if="segment.kind === 'tool'"
              :tool-call="toToolCall(segment)"
              :is-dark="isDark"
            />
            <pre v-else-if="segment.kind === 'error'" class="segment-text error-text">{{ segment.text }}</pre>
          </template>
        </div>
      </div>
    </div>

    <v-dialog v-model="inputDialog" max-width="980">
      <v-card class="input-card">
        <v-card-title class="input-title">
          <span>{{ call.agentLabel || '智能体' }} 输入原文</span>
          <v-spacer />
          <v-btn-toggle v-model="inputMode" density="compact" mandatory>
            <v-btn value="json" size="small">JSON</v-btn>
            <v-btn value="text" size="small">文本</v-btn>
          </v-btn-toggle>
        </v-card-title>
        <v-card-text>
          <pre class="input-payload">{{ inputMode === 'json' ? inputJson : inputText }}</pre>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="inputDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { MessagePart } from '@/composables/useMessages';
import ReasoningBlock from '@/components/chat/message_list_comps/ReasoningBlock.vue';
import ToolCallCard from '@/components/chat/message_list_comps/ToolCallCard.vue';

const props = withDefaults(defineProps<{
  call: any;
  isDark?: boolean;
}>(), {
  isDark: false,
});

const inputDialog = ref(false);
const inputMode = ref<'json' | 'text'>('json');
const outputOpen = ref(true);
const outputTouched = ref(false);

const hasOutput = computed(() => (props.call?.outputSegments || []).length > 0);
const hasReasoning = computed(() => (props.call?.reasoningSegments || []).length > 0);
const isRunning = computed(() => String(props.call?.status || 'running') === 'running');
const outputText = computed(() => (props.call?.outputSegments || [])
  .map((segment: any) => {
    if (segment.kind === 'text' || segment.kind === 'error') return String(segment.text || '');
    if (segment.kind === 'tool') return `${segment.name || 'tool'} ${segment.result || segment.args || ''}`;
    return '';
  })
  .join('\n'));
const outputLineCount = computed(() => outputText.value ? outputText.value.split(/\r?\n/).length : 0);
const outputCharCount = computed(() => outputText.value.length);
const isLongOutput = computed(() => outputCharCount.value > 2400 || outputLineCount.value > 60);
const outputSummary = computed(() => {
  const parts = [];
  if (outputLineCount.value) parts.push(`${outputLineCount.value} 行`);
  if (outputCharCount.value) parts.push(formatBytes(outputCharCount.value));
  return parts.join(' · ') || '无内容';
});

watch(
  () => [props.call?.callId, props.call?.status, outputCharCount.value, outputLineCount.value],
  () => {
    if (outputTouched.value) return;
    outputOpen.value = isRunning.value || !isLongOutput.value;
  },
  { immediate: true },
);

const reasoningParts = computed<MessagePart[]>(() => segmentsToMessageParts(props.call?.reasoningSegments || []));

const statusClass = computed(() => String(props.call?.status || 'running'));
const statusColor = computed(() => {
  const status = String(props.call?.status || 'running');
  if (status === 'completed') return 'success';
  if (status === 'failed' || status === 'retryable_failed') return 'error';
  return 'info';
});
const statusText = computed(() => {
  const status = String(props.call?.status || 'running');
  const map: Record<string, string> = {
    running: '调用中',
    completed: '已完成',
    failed: '失败',
    retryable_failed: '可重试失败',
  };
  return map[status] || status;
});
const providerText = computed(() => [props.call?.providerId, props.call?.model].filter(Boolean).join(' / '));
const showStatusChip = computed(() => String(props.call?.status || 'running') !== 'completed');
const durationText = computed(() => props.call?.durationMs ? formatDur(props.call.durationMs) : '');
const tokenText = computed(() => {
  const token = props.call?.token || {};
  const input = Number(token.input || token.input_tokens || 0);
  const output = Number(token.output || token.output_tokens || 0);
  if (!input && !output) return '';
  return `输入 ${formatTokens(input)} / 输出 ${formatTokens(output)}`;
});
const visibleInputPayload = computed(() => pickVisibleInputPayload(props.call?.inputPayload || {}));
const inputJson = computed(() => JSON.stringify(visibleInputPayload.value, null, 2));
const inputText = computed(() => inputPayloadToText(visibleInputPayload.value));

const avatar = computed(() => avatarForAgent(props.call?.agentId, props.call?.agentLabel));

function avatarForAgent(agentId: string, label: string) {
  const text = `${agentId || ''} ${label || ''}`;
  if (text.includes('research')) return { color: 'indigo', icon: 'mdi-microscope', initial: '' };
  if (text.includes('review')) return { color: 'deep-purple', icon: 'mdi-clipboard-check-outline', initial: '' };
  if (text.includes('report')) return { color: 'teal', icon: 'mdi-file-document-edit-outline', initial: '' };
  if (text.includes('executor') || text.includes('执行')) return { color: 'blue', icon: 'mdi-account-hard-hat-outline', initial: '' };
  if (text.includes('assistant') || text.includes('助手')) return { color: 'cyan', icon: 'mdi-robot-outline', initial: '' };
  return { color: stableColor(text), icon: '', initial: String(label || agentId || 'A').slice(0, 1).toUpperCase() };
}

function stableColor(value: string) {
  const colors = ['blue', 'teal', 'indigo', 'deep-purple', 'cyan', 'green'];
  let hash = 0;
  for (const ch of value || 'agent') hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return colors[hash % colors.length];
}

function formatTokens(value: number) {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return `${value}`;
}

function formatDur(ms: number) {
  const value = Number(ms || 0);
  if (!value) return '';
  if (value < 1000) return `${value}ms`;
  const seconds = Math.floor(value / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes}m${rest}s` : `${minutes}m`;
}

function formatBytes(chars: number) {
  if (chars >= 1000000) return `${(chars / 1000000).toFixed(1)}M 字符`;
  if (chars >= 1000) return `${(chars / 1000).toFixed(1)}K 字符`;
  return `${chars} 字符`;
}

function toggleOutput() {
  outputTouched.value = true;
  outputOpen.value = !outputOpen.value;
}

function inputPayloadToText(payload: Record<string, any>) {
  const sections = [
    ['系统提示词', payload.system_prompt],
    ['用户提示词', payload.user_prompt],
    ['消息历史', payload.messages],
    ['压缩上下文', payload.compact_context],
    ['可用工具', payload.func_tools],
  ];
  return sections
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([title, value]) => `## ${title}\n${typeof value === 'string' ? value : JSON.stringify(value, null, 2)}`)
    .join('\n\n');
}

function pickVisibleInputPayload(payload: Record<string, any>) {
  const allowedKeys = ['system_prompt', 'user_prompt', 'messages', 'compact_context', 'func_tools'];
  return allowedKeys.reduce((result: Record<string, any>, key) => {
    if (payload[key] !== undefined) result[key] = payload[key];
    return result;
  }, {});
}

function segmentsToMessageParts(segments: any[]): MessagePart[] {
  const parts: MessagePart[] = [];
  for (const segment of segments || []) {
    if (segment.kind === 'text' || segment.kind === 'error') {
      const text = String(segment.text || '');
      if (text.trim()) parts.push({ type: 'think', think: text });
      continue;
    }
    if (segment.kind === 'tool') {
      parts.push({ type: 'tool_call', tool_calls: [toToolCall(segment)] });
    }
  }
  return parts;
}

function toToolCall(segment: any) {
  return {
    id: segment.id || segment.toolCallId || segment.name || 'tool',
    name: segment.name || 'tool',
    args: parseJsonSafe(segment.args || {}),
    arguments: parseJsonSafe(segment.args || {}),
    result: stringifyToolResult(segment.result),
    ts: Number(segment.ts || segment.startedAt || 0) || undefined,
    finished_ts: Number(segment.finishedTs || segment.finished_ts || 0) || undefined,
  };
}

function stringifyToolResult(value: unknown) {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function parseJsonSafe(value: unknown) {
  if (typeof value !== 'string') return value;
  if (!value.trim()) return {};
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}
</script>

<style scoped>
.agent-call-card {
  display: flex;
  gap: 12px;
  padding: 12px 0 16px;
}

.agent-avatar-button {
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  align-self: flex-start;
}

.agent-call-main {
  min-width: 0;
  flex: 1;
  border-left: 3px solid rgba(var(--v-theme-primary), 0.25);
  padding-left: 12px;
}

.agent-call-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.agent-call-title {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-name {
  font-weight: 700;
  color: rgb(var(--v-theme-on-surface));
}

.agent-subtitle,
.meta-text {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
}

.agent-call-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-call-stats {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: -2px 0 8px;
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 12px;
}

.stat-item {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
}

.lane-section {
  margin-top: 8px;
}

.segment-text,
.input-payload {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.segment-text {
  margin: 0;
  padding: 12px;
  border-radius: 12px;
  background: rgba(var(--v-theme-on-surface), 0.052);
}

.error-text {
  color: rgb(var(--v-theme-error));
}

.output-section {
  max-width: 100%;
}

.output-header {
  width: 100%;
  border: 0;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.72);
  cursor: pointer;
  user-select: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 0;
  margin-bottom: 8px;
  font: inherit;
  text-align: left;
}

.output-header:hover {
  color: rgba(var(--v-theme-on-surface), 0.9);
}

.output-header-left,
.output-header-right {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.output-header-left {
  font-size: 14px;
  font-weight: 700;
}

.output-header-right {
  justify-content: flex-end;
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 12px;
}

.output-summary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.output-chevron {
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.output-chevron.expanded {
  transform: rotate(90deg);
}

.output-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 560px;
  overflow: auto;
  padding: 12px;
  border-radius: 18px;
  background: rgba(var(--v-theme-on-surface), 0.045);
}

.output-content :deep(.tool-call-card) {
  font-size: 13.5px;
  line-height: 1.56;
}

.input-card {
  max-height: 82vh;
}

.input-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.input-payload {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.055);
  max-height: 62vh;
  overflow: auto;
}

.avatar-initial {
  font-weight: 700;
}
</style>
