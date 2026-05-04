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
          <v-icon :color="statusColor(task.status)" :icon="statusIcon(task.status)" size="18" />
          <span class="task-name">{{ task.name }}</span>
          <v-chip v-if="needsHuman(task)" color="warning" size="x-small" variant="flat">
            HITL
          </v-chip>
        </div>
        <div class="task-desc">{{ task.description || taskKindLabel(task.work_task_kind || task.task_type) }}</div>
        <v-progress-linear :model-value="task.progress || 0" :color="statusColor(task.status)" height="5" rounded />
        <div class="task-meta">
          <span>{{ statusLabel(task.status) }}</span>
          <span v-if="!compact">{{ formatTokens(task.total_tokens) }} tokens</span>
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
</script>

<style scoped>
.work-task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.work-task-card {
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
  gap: 8px;
  padding: 12px;
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
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
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
  padding: 10px;
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
