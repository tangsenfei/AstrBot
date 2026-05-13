<template>
  <div class="agent-chat-panel" :class="{ 'is-dark': isDark }">
    <div ref="messagesContainer" class="chat-messages" @scroll="onScroll">
      <div v-if="messages.length === 0" class="chat-empty">
        <v-icon icon="mdi-chat-outline" size="56" color="grey-lighten-1" class="mb-3" />
        <p class="text-body-2 text-grey">{{ emptyText }}</p>
      </div>

      <div v-else class="message-list">
        <template v-for="(msg, idx) in messages" :key="msg.id || idx">
          <div v-if="showRoundDivider && isNewRound(idx)" class="round-divider">
            <v-divider />
            <div class="round-divider-label">
              <v-chip color="primary" variant="tonal" size="small">
                <v-icon start icon="mdi-rotate-right" size="small" />
                第 {{ msg.round }} 轮
              </v-chip>
            </div>
          </div>

          <div
            class="message-row"
            :class="msg.role === 'user' ? 'from-user' : 'from-bot'"
          >
            <div v-if="msg.role === 'user'" class="user-bubble-row">
              <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
              <div class="user-bubble">{{ msg.content }}</div>
            </div>

            <div v-else class="bot-bubble-row">
              <v-avatar size="30" class="bot-avatar" :color="getAvatarColor(msg)">
                <v-icon v-if="!msg.speaker" size="16" :icon="isMessageStreaming(idx) ? 'mdi-lightbulb-outline' : 'mdi-robot-outline'" />
                <span v-else class="avatar-text">{{ getSpeakerInitial(msg.speaker) }}</span>
              </v-avatar>
              <div class="bot-bubble-wrap">
                <div v-if="msg.speaker || (msg.type && msg.type !== 'speech')" class="speaker-label">
                  <v-icon v-if="msg.speaker" size="12" class="mr-1">mdi-account-circle</v-icon>
                  <span v-if="msg.speaker">{{ msg.speaker }}</span>
                  <span v-if="msg.round && !showRoundDivider" class="round-badge">R{{ msg.round }}</span>
                  <v-chip v-if="msg.type && msg.type !== 'speech' && msg.type !== 'thinking'" size="x-small" :color="getTypeBadgeColor(msg.type)" variant="tonal" class="ml-2">
                    {{ getTypeBadgeLabel(msg.type) }}
                  </v-chip>
                </div>
                <div class="bot-bubble">
                  <div v-if="msg.planning_steps" class="mb-2">
                    <v-expansion-panels density="compact" variant="accordion">
                      <v-expansion-panel>
                        <v-expansion-panel-title class="text-caption py-1">
                          <v-icon size="x-small" color="primary" class="mr-1">mdi-clipboard-list-outline</v-icon>
                          执行计划
                        </v-expansion-panel-title>
                        <v-expansion-panel-text>
                          <div class="planning-content">{{ msg.planning_steps }}</div>
                        </v-expansion-panel-text>
                      </v-expansion-panel>
                    </v-expansion-panels>
                  </div>

                  <ReasoningBlock
                    v-if="msg.thinking"
                    :parts="[{ type: 'thinking', text: msg.thinking }]"
                    :is-dark="isDark"
                    :initial-expanded="collapseThinkingByDefault ? false : (msg.thinkingDone ? false : true)"
                    :is-streaming="!msg.thinkingDone"
                    :has-non-reasoning-content="!!msg.content"
                  />

                  <div v-if="msg.content" class="bot-content">
                    <MarkdownMessagePart
                      :content="msg.content"
                      :is-dark="isDark"
                      :refs="null"
                      :custom-html-tags="[]"
                    />
                  </div>

                  <div v-if="!msg.content && !msg.thinking && isMessageStreaming(idx)" class="streaming-indicator">
                    <v-progress-circular indeterminate size="14" width="2" class="mr-2" />
                    <span class="text-caption text-grey">思考中...</span>
                  </div>

                  <div v-if="msg.toolCalls && msg.toolCalls.length > 0" class="tool-calls-section">
                    <div class="tool-calls-header">
                      <v-icon size="14" class="mr-1">mdi-tools</v-icon>
                      <span class="text-caption">工具调用</span>
                    </div>
                    <div class="tool-calls-list">
                      <ToolCallCard
                        v-for="tc in msg.toolCalls"
                        :key="tc.id || tc.name"
                        :tool-call="normalizeToolCall(tc)"
                        :is-dark="isDark"
                      />
                    </div>
                  </div>
                </div>

                <div class="bot-meta">
                  <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
                  <div v-if="msg._stats" class="meta-stats">
                    <v-chip size="x-small" variant="text" class="meta-chip">
                      <v-icon size="12" class="mr-1">mdi-arrow-up</v-icon>{{ msg._stats.input || 0 }}
                    </v-chip>
                    <v-chip size="x-small" variant="text" class="meta-chip">
                      <v-icon size="12" class="mr-1">mdi-arrow-down</v-icon>{{ msg._stats.output || 0 }}
                    </v-chip>
                    <v-chip v-if="msg._execution_time_ms" size="x-small" variant="text" class="meta-chip">
                      <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>{{ formatDuration(msg._execution_time_ms) }}
                    </v-chip>
                    <v-chip v-if="msg._time_to_first_token" size="x-small" variant="text" class="meta-chip">
                      <v-icon size="12" class="mr-1">mdi-lightning-bolt</v-icon>TTFT {{ formatDuration(msg._time_to_first_token) }}
                    </v-chip>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div v-if="showInput" class="chat-input-area">
      <div class="input-row">
        <v-textarea
          v-model="inputMessage"
          :placeholder="inputPlaceholder"
          rows="1"
          auto-grow
          max-rows="6"
          variant="outlined"
          :disabled="sending"
          hide-details
          density="compact"
          @keydown.enter.ctrl="handleSend"
          @keydown.enter.meta="handleSend"
        />
        <div class="input-actions">
          <v-btn v-if="!sending" color="primary" size="small" @click="handleSend" :disabled="!inputMessage.trim()">
            <v-icon start size="18" icon="mdi-send" />发送
          </v-btn>
          <v-btn v-else color="error" size="small" @click="handleStop">
            <v-icon start size="18" icon="mdi-stop" />停止
          </v-btn>
        </div>
      </div>
      <div class="input-hint">Ctrl+Enter 发送</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { useCustomizerStore } from '@/stores/customizer'
import MarkdownMessagePart from '@/components/chat/message_list_comps/MarkdownMessagePart.vue'
import ReasoningBlock from '@/components/chat/message_list_comps/ReasoningBlock.vue'
import ToolCallCard from '@/components/chat/message_list_comps/ToolCallCard.vue'
import 'markstream-vue/index.css'

export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  thinkingDone?: boolean
  planning_steps?: string | null
  toolCalls?: ToolCallInfo[]
  speaker?: string
  round?: number
  type?: string
  streaming?: boolean
  created_at?: number
  _stats?: { input: number; output: number; total: number } | null
  _execution_time_ms?: number
  _time_to_first_token?: number
}

export interface ToolCallInfo {
  id?: string
  name: string
  args?: any
  result?: any
  status?: 'running' | 'done' | 'error'
  ts?: number
  finished_ts?: number
}

const props = withDefaults(defineProps<{
  messages: ChatMessage[]
  sending?: boolean
  showInput?: boolean
  inputPlaceholder?: string
  emptyText?: string
  showRoundDivider?: boolean
  collapseThinkingByDefault?: boolean
}>(), {
  sending: false,
  showInput: true,
  inputPlaceholder: '输入消息...',
  emptyText: '暂无消息',
  showRoundDivider: false,
  collapseThinkingByDefault: false,
})

const emit = defineEmits<{
  (e: 'send', message: string): void
  (e: 'stop'): void
}>()

const customizer = useCustomizerStore()
const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark')
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const shouldStickToBottom = ref(true)

function isNewRound(idx: number): boolean {
  const current = props.messages[idx]
  if (!current.round || current.round <= 0) return false
  if (idx === 0) return true
  const prev = props.messages[idx - 1]
  return !prev.round || prev.round <= 0 || current.round !== prev.round
}

function isMessageStreaming(idx: number): boolean {
  const msg = props.messages[idx]
  if (!msg || msg.role !== 'assistant') return false
  if (msg.streaming) return true
  return props.sending && idx === props.messages.length - 1
}

function formatTime(ts: number | string | undefined): string {
  if (!ts) return ''
  const d = new Date(typeof ts === 'number' ? ts : Date.parse(ts))
  if (isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(ms: number | undefined): string {
  if (!ms) return '--'
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

function getSpeakerInitial(speaker: string): string {
  if (!speaker) return '?'
  return speaker.charAt(0).toUpperCase()
}

function getAvatarColor(msg: ChatMessage): string {
  if (msg.speaker) {
    const colors = ['primary', 'success', 'warning', 'info', 'purple', 'teal', 'orange', 'indigo']
    let hash = 0
    for (const c of msg.speaker) hash = ((hash << 5) - hash + c.charCodeAt(0)) | 0
    return colors[Math.abs(hash) % colors.length]
  }
  return 'primary-lighten-3'
}

function getTypeBadgeColor(type: string): string {
  const colors: Record<string, string> = {
    opening: 'info',
    guide: 'info',
    summary: 'warning',
    integration: 'warning',
    filter: 'warning',
    vote: 'purple',
    question: 'teal',
    answer: 'green',
    evaluation: 'orange',
  }
  return colors[type] || 'primary'
}

function getTypeBadgeLabel(type: string): string {
  const labels: Record<string, string> = {
    opening: '引导',
    guide: '引导',
    speech: '发言',
    summary: '总结',
    integration: '整合',
    filter: '筛选',
    vote: '投票',
    question: '提问',
    answer: '回答',
    evaluation: '评估',
    thinking: '思考',
  }
  return labels[type] || type
}

function normalizeToolCall(tc: ToolCallInfo) {
  const normalized: any = { ...tc }
  if (typeof normalized.args === 'string') {
    try { normalized.args = JSON.parse(normalized.args) } catch { /* keep as string */ }
  }
  if (typeof normalized.result === 'string') {
    try { normalized.result = JSON.parse(normalized.result) } catch { /* keep as string */ }
  }
  if (normalized.result && typeof normalized.result === 'object') {
    normalized.result = JSON.stringify(normalized.result, null, 2)
  }
  if (!normalized.ts) normalized.ts = Date.now() / 1000
  return normalized
}

function onScroll() {
  const el = messagesContainer.value
  if (!el) return
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
  shouldStickToBottom.value = atBottom
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesContainer.value
    if (!el) return
    if (shouldStickToBottom.value) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function handleSend() {
  if (!inputMessage.value.trim() || props.sending) return
  emit('send', inputMessage.value.trim())
  inputMessage.value = ''
}

function handleStop() {
  emit('stop')
}

watch(() => props.messages.length, () => scrollToBottom())
watch(() => props.messages, () => scrollToBottom(), { deep: true })

onBeforeUnmount(() => {})

defineExpose({ scrollToBottom })
</script>

<style scoped>
.agent-chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgb(var(--v-theme-background));
  min-height: 0;
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 20px;
}

.chat-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.round-divider {
  margin: 8px 0;
}

.round-divider-label {
  display: flex;
  justify-content: center;
  margin-top: -12px;
  position: relative;
  z-index: 1;
}

.user-bubble-row {
  display: flex;
  justify-content: flex-end;
  align-items: flex-end;
  gap: 8px;
}

.user-bubble {
  background: rgb(var(--v-theme-primary));
  color: white;
  padding: 8px 14px;
  border-radius: 16px 16px 4px 16px;
  max-width: 70%;
  word-break: break-word;
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.6;
}

.bot-bubble-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.bot-avatar {
  flex-shrink: 0;
  margin-top: 2px;
}

.avatar-text {
  font-size: 13px;
  font-weight: 600;
  color: white;
}

.bot-bubble-wrap {
  flex: 1;
  min-width: 0;
  max-width: 88%;
}

.speaker-label {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  margin-bottom: 4px;
  gap: 2px;
}

.round-badge {
  font-size: 10px;
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: 6px;
  font-weight: 600;
}

.bot-bubble {
  background: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 12px;
  padding: 10px 14px;
  word-break: break-word;
}

.is-dark .bot-bubble {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

.bot-content {
  font-size: 14px;
  line-height: 1.7;
}

.bot-content :deep(p) {
  margin-bottom: 8px;
}

.bot-content :deep(p:last-child) {
  margin-bottom: 0;
}

.bot-content :deep(pre) {
  border-radius: 8px;
  margin: 8px 0;
}

.bot-content :deep(code) {
  font-size: 13px;
}

.streaming-indicator {
  display: flex;
  align-items: center;
  padding: 4px 0;
}

.tool-calls-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.tool-calls-header {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.tool-calls-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.planning-content {
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  font-size: 13px;
}

.bot-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  min-height: 22px;
  gap: 8px;
}

.msg-time {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.4);
  flex-shrink: 0;
}

.meta-stats {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}

.meta-chip {
  font-size: 11px !important;
  height: 20px !important;
  padding: 0 4px !important;
}

.meta-chip :deep(.v-icon) {
  opacity: 0.5;
}

.chat-input-area {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  padding: 12px 16px;
  background: rgb(var(--v-theme-background));
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-row :deep(.v-textarea) {
  flex: 1;
}

.input-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding-bottom: 2px;
}

.input-hint {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.4);
  margin-top: 4px;
  text-align: right;
}
</style>
