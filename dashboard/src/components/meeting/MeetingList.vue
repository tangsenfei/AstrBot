<template>
  <div class="meeting-list">
    <article
      v-for="meeting in meetings"
      :key="meeting.id"
      class="meeting-card"
      :class="{ active: selectedMeetingId === meeting.id, 'needs-hitl': needsHuman(meeting) }"
    >
      <button class="meeting-main" type="button" @click="emit('select', meeting.id)">
        <div class="meeting-card-top">
          <span class="meeting-status-badge" :class="`status-${displayStatus(meeting)}`">
            <v-icon :icon="statusIcon(displayStatus(meeting))" size="15" />
            <span>{{ statusLabel(displayStatus(meeting)) }}</span>
          </span>
          <span class="meeting-name">{{ meeting.name }}</span>
          <span class="meeting-top-time">{{ formatCreatedTime(meeting.created_at) }}</span>
          <v-chip v-if="needsHuman(meeting)" color="warning" size="x-small" variant="flat">
            HITL
          </v-chip>
        </div>
        <div class="meeting-desc">{{ meeting.type_info?.name || typeName(meeting.meeting_type) }}</div>
        <v-progress-linear :model-value="meeting.progress || 0" :color="statusColor(displayStatus(meeting))" height="5" rounded />
        <div class="meeting-meta">
          <span class="meta-icon-text">
            <v-icon size="14" icon="mdi-clock-outline" />
            {{ formatDuration(meeting.started_at, meeting.completed_at) }}
          </span>
          <span class="meta-icon-text meta-tokens">
            tokens {{ formatTokens(meeting.total_tokens) }}
          </span>
        </div>
      </button>

      <button
        v-if="needsHuman(meeting)"
        class="hitl-entry"
        type="button"
        @click.stop="emit('hitl-open', meeting.id)"
      >
        <v-icon size="15" icon="mdi-hand-back-right-outline" />
        <span>{{ meeting.active_hitl?.title || '等待人工确认' }}</span>
        <v-icon size="15" icon="mdi-chevron-right" />
      </button>
    </article>

    <div v-if="!meetings.length && !loading" class="empty-state">暂无会议</div>
    <div v-else-if="loadingMore" class="list-footer">正在加载更多...</div>
    <div v-else-if="hasMore" class="list-footer">下拉加载更多</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  meetings: any[];
  selectedMeetingId?: string | null;
  loading?: boolean;
  loadingMore?: boolean;
  hasMore?: boolean;
  isDark?: boolean;
}>(), {
  meetings: () => [],
  selectedMeetingId: null,
  loading: false,
  loadingMore: false,
  hasMore: false,
  isDark: false,
});

const emit = defineEmits<{
  (e: 'select', meetingId: string): void;
  (e: 'hitl-open', meetingId: string): void;
}>();

function needsHuman(meeting: any) {
  return Boolean(meeting?.active_hitl?.interaction_id) || Boolean(meeting?.hitl_cards?.length);
}

function displayStatus(meeting: any) {
  if (!meeting) return 'pending';
  if (meeting.status === 'waiting_feedback' && !needsHuman(meeting)) {
    return Number(meeting.progress || 0) >= 100 ? 'completed' : 'running';
  }
  return meeting.status || 'pending';
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    pending: '待开始',
    running: '进行中',
    waiting_feedback: '等待确认',
    completed: '已结束',
    failed: '失败',
    cancelled: '已取消',
  };
  return map[status] || status || '-';
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    draft: 'grey',
    pending: 'info',
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
    draft: 'mdi-file-outline',
    pending: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    waiting_feedback: 'mdi-account-question-outline',
    completed: 'mdi-check-circle-outline',
    failed: 'mdi-alert-circle-outline',
    cancelled: 'mdi-cancel',
  };
  return map[status] || 'mdi-circle-outline';
}

function typeName(type: string) {
  const map: Record<string, string> = {
    solution_design: '方案设计',
    brainstorming: '头脑风暴',
    review: '评审会议',
    daily: '日常会议',
  };
  return map[type] || type || '会议';
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
.meeting-list {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meeting-card {
  flex: 0 0 auto;
  border: 1px solid rgba(var(--v-border-color), 0.14);
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.92);
  overflow: hidden;
}

.meeting-card.active {
  border-color: rgba(var(--v-theme-primary), 0.65);
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.2);
}

.meeting-card.needs-hitl {
  border-color: rgba(var(--v-theme-warning), 0.58);
}

.meeting-main {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 10px 12px;
  text-align: left;
  color: inherit;
}

.meeting-main:hover {
  background: rgba(var(--v-theme-on-surface), 0.035);
}

.meeting-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.meeting-status-badge {
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

.meeting-status-badge.status-draft {
  color: rgba(var(--v-theme-on-surface), 0.55);
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.meeting-status-badge.status-pending {
  color: rgba(var(--v-theme-on-surface), 0.55);
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.meeting-status-badge.status-running {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
}

.meeting-status-badge.status-waiting_feedback {
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.12);
}

.meeting-status-badge.status-completed {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.1);
}

.meeting-status-badge.status-failed {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.1);
}

.meeting-status-badge.status-cancelled {
  color: rgba(var(--v-theme-on-surface), 0.45);
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.meeting-top-time {
  flex-shrink: 0;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.48);
  margin-left: auto;
}

.meeting-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 650;
  font-size: 14px;
}

.meeting-desc {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meeting-meta {
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

.empty-state {
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 13px;
  text-align: center;
  padding: 18px;
}

.list-footer {
  flex: 0 0 auto;
  padding: 10px 0 4px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 12px;
}
</style>
