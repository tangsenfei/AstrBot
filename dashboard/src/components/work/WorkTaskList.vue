<template>
  <div class="work-task-list" :class="{ compact }">
    <article
      v-for="task in tasks"
      :key="task.id"
      class="work-task-card"
      :class="{ active: selectedTaskId === task.id, 'needs-hitl': needsHuman(task) }"
    >
      <button class="task-main" type="button" @click="emit('select', task.id)">
        <div class="task-card-top">
          <span class="task-status-badge" :class="`status-${task.status || 'pending'}`">
            <v-icon :icon="statusIcon(task.status)" size="15" />
            <span>{{ statusLabel(task.status) }}</span>
          </span>
          <span class="task-name">{{ task.name }}</span>
          <span class="task-top-time">{{ formatCreatedTime(task.created_at) }}</span>
          <v-chip v-if="needsHuman(task)" color="warning" size="x-small" variant="flat">
            HITL
          </v-chip>
        </div>
        <div class="task-desc">{{ task.description || taskKindLabel(task.work_task_kind || task.task_type) }}</div>
        <v-progress-linear :model-value="task.progress || 0" :color="statusColor(task.status)" height="5" rounded />
        <div class="task-meta">
          <span class="meta-icon-text">
            <v-icon size="14" icon="mdi-clock-outline" />
            {{ formatDuration(task.started_at, task.completed_at) }}
          </span>
          <span v-if="!compact" class="meta-icon-text meta-tokens">
            tokens {{ formatTokens(task.total_tokens) }}
          </span>
        </div>
      </button>

      <button
        v-if="needsHuman(task) && !showHitlInline"
        class="hitl-entry"
        type="button"
        @click.stop="emit('select', task.id)"
      >
        <v-icon size="15" icon="mdi-hand-back-right-outline" />
        <span>{{ task.interaction_title || '等待人工确认' }}</span>
        <v-icon size="15" icon="mdi-chevron-right" />
      </button>

      <div v-if="showHitlInline && task.hitl_cards?.length" class="hitl-inline">
        <InteractionCardComponent
          :card="task.hitl_cards[0]"
          :is-dark="isDark"
          @respond="onRespond"
        />
      </div>
    </article>

    <div v-if="!tasks.length && !loading" class="empty-state">暂无任务</div>
  </div>
</template>

<script setup lang="ts">
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';

withDefaults(defineProps<{
  tasks: any[];
  selectedTaskId?: string | null;
  loading?: boolean;
  compact?: boolean;
  showHitlInline?: boolean;
  isDark?: boolean;
}>(), {
  tasks: () => [],
  selectedTaskId: null,
  loading: false,
  compact: false,
  showHitlInline: false,
  isDark: false,
});

const emit = defineEmits<{
  (e: 'select', taskId: string): void;
  (e: 'interaction-respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

function onRespond(payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }) {
  emit('interaction-respond', payload);
}

function needsHuman(task: any) {
  return task?.status === 'waiting_feedback' || task?.has_hitl || Boolean(task?.hitl_cards?.length);
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '执行中',
    paused: '已暂停',
    waiting_feedback: '等待确认',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  };
  return map[status] || status || '-';
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'grey',
    running: 'primary',
    waiting_feedback: 'warning',
    completed: 'success',
    failed: 'error',
    cancelled: 'grey',
  };
  return map[status] || 'grey';
}

function statusIcon(status: string) {
  const map: Record<string, string> = {
    pending: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    waiting_feedback: 'mdi-account-question-outline',
    completed: 'mdi-check-circle-outline',
    failed: 'mdi-alert-circle-outline',
    cancelled: 'mdi-cancel',
  };
  return map[status] || 'mdi-circle-outline';
}

function taskKindLabel(kind: string) {
  const map: Record<string, string> = {
    single_agent: '单智能体',
    multi_agent: '多智能体',
    workflow: '业务流',
    work_task: 'Work 任务',
  };
  return map[kind] || kind || '任务';
}

function formatTokens(value: number) {
  const n = Number(value || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function formatCreatedTime(value: string) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  const now = new Date();
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (date.toDateString() === now.toDateString()) return time;
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return `昨天 ${time}`;
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${time}`;
}

function formatDuration(started_at: string, completed_at: string) {
  if (!started_at) return '-';
  const start = new Date(started_at);
  if (Number.isNaN(start.getTime())) return '-';
  if (!completed_at) return '进行中';
  const end = new Date(completed_at);
  const diff = end.getTime() - start.getTime();
  if (diff < 0) return '-';
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return remainingSeconds > 0 ? `${minutes}m${remainingSeconds}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h${remainingMinutes}m` : `${hours}h`;
}
</script>

<style scoped>
.work-task-list {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.work-task-card {
  flex: 0 0 auto;
  border: 1px solid rgba(var(--v-border-color), 0.14);
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.92);
  overflow: hidden;
}

.work-task-card.active {
  border-color: rgba(var(--v-theme-primary), 0.65);
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.2);
}

.work-task-card.needs-hitl {
  border-color: rgba(var(--v-theme-warning), 0.58);
}

.task-main {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 10px 12px;
  text-align: left;
  color: inherit;
}

.task-main:hover {
  background: rgba(var(--v-theme-on-surface), 0.035);
}

.task-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.task-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}

.task-status-badge.status-pending {
  color: rgba(var(--v-theme-on-surface), 0.55);
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.task-status-badge.status-running {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
}

.task-status-badge.status-waiting_feedback {
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.12);
}

.task-status-badge.status-completed {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.1);
}

.task-status-badge.status-failed {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.1);
}

.task-status-badge.status-cancelled {
  color: rgba(var(--v-theme-on-surface), 0.45);
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.task-top-time {
  flex-shrink: 0;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.48);
  margin-left: auto;
}

.task-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 650;
  font-size: 14px;
}

.task-desc {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 12px;
  white-space: nowrap;
}

.meta-icon-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.meta-icon-text .v-icon {
  opacity: 0.65;
}

.meta-tokens {
  color: rgba(var(--v-theme-on-surface), 0.52);
}

.hitl-inline {
  padding: 0 10px 10px;
}

.hitl-entry {
  width: calc(100% - 20px);
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 10px 10px;
  padding: 7px 9px;
  border: 1px solid rgba(var(--v-theme-warning), 0.36);
  border-radius: 8px;
  background: rgba(var(--v-theme-warning), 0.08);
  color: rgb(var(--v-theme-warning));
  font-size: 12px;
  text-align: left;
}

.hitl-entry span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact .task-main {
  padding: 9px 10px;
}

.compact .hitl-inline :deep(.card-body) {
  max-height: 110px;
  overflow: auto;
  font-size: 12px;
}

.empty-state {
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 13px;
  text-align: center;
  padding: 18px;
}
</style>
