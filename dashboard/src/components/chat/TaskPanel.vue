<template>
  <div class="task-panel pa-3">
    <div class="d-flex align-center justify-space-between mb-3">
      <span class="text-subtitle-2 font-weight-medium">
        <v-icon icon="mdi-clipboard-list" size="18" class="mr-1" /> 任务
      </span>
      <v-btn icon size="x-small" variant="text" @click="$emit('close')">
        <v-icon size="16">mdi-close</v-icon>
      </v-btn>
    </div>

    <div v-if="loading" class="text-center py-4">
      <v-progress-circular indeterminate size="20" width="2" />
    </div>

    <div v-else-if="tasks.length === 0" class="text-center py-4">
      <p class="text-caption text-grey mb-0">暂无任务</p>
    </div>

    <div v-else class="task-list">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="task-item pa-3 mb-2 rounded"
        :class="{ 'task-hover': !selectedTask || selectedTask.id !== task.id }"
        style="cursor: pointer; border: 1px solid rgba(var(--v-border-color), 0.12);"
        @click="selectTask(task)"
      >
        <div class="d-flex align-center mb-1">
          <v-icon :icon="taskIcon(task)" :color="taskColor(task)" size="16" class="mr-2" />
          <span class="text-body-2 font-weight-medium text-truncate flex-grow-1">{{ task.name }}</span>
        </div>
        <v-progress-linear
          :model-value="taskProgress(task)"
          :color="taskColor(task)"
          height="4"
          rounded
          class="mb-1"
        />
        <div class="d-flex justify-space-between">
          <span class="text-caption text-grey">{{ taskStatusLabel(task) }}</span>
          <span class="text-caption text-grey">{{ taskStepInfo(task) }}</span>
        </div>
      </div>
    </div>

    <TaskDetailOverlay
      v-if="selectedTask"
      :task="selectedTask"
      @close="selectedTask = null"
      @input-submitted="onInputSubmitted"
      @interaction-respond="onInteractionRespond"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import axios from 'axios';
import TaskDetailOverlay from './TaskDetailOverlay.vue';

defineEmits(['close']);

const tasks = ref<any[]>([]);
const loading = ref(true);
const selectedTask = ref<any>(null);
let pollTimer: ReturnType<typeof setInterval> | null = null;

function taskIcon(task: any) {
  if (task.status === 'running') return 'mdi-progress-clock';
  if (task.status === 'completed') return 'mdi-check-circle';
  if (task.status === 'failed') return 'mdi-alert-circle';
  if (task.status === 'paused' || task.status === 'waiting_feedback') return 'mdi-pause-circle';
  if (task.status === 'cancelled') return 'mdi-cancel';
  return 'mdi-clock-outline';
}

function taskColor(task: any) {
  if (task.status === 'running') return 'primary';
  if (task.status === 'completed') return 'success';
  if (task.status === 'failed') return 'error';
  if (task.status === 'waiting_feedback') return 'warning';
  return 'grey';
}

function taskProgress(task: any) {
  if (task.status === 'completed') return 100;
  const steps = Array.isArray(task.steps) ? task.steps : [];
  if (steps.length === 0) return 0;
  const done = steps.filter((s: any) => s.status === 'done').length;
  return Math.round((done / steps.length) * 100);
}

function taskStatusLabel(task: any) {
  const map: Record<string, string> = {
    pending: '等待中', running: '执行中', completed: '已完成',
    failed: '失败', paused: '已暂停', cancelled: '已取消',
    waiting_feedback: '等待确认',
  };
  return map[task.status] || task.status;
}

function taskStepInfo(task: any) {
  const steps = Array.isArray(task.steps) ? task.steps : [];
  if (steps.length === 0) return '';
  const done = steps.filter((s: any) => s.status === 'done').length;
  return `${done}/${steps.length} 步`;
}

function selectTask(task: any) {
  selectedTask.value = task;
}

async function fetchTasks() {
  try {
    const resp = await axios.get('/api/plug/agent/tasks', { params: { page_size: 50 } });
    if (resp.data?.status === 'ok') {
      tasks.value = resp.data.data?.tasks || [];
    }
  } catch (e) { /* ignore */ }
  loading.value = false;
}

function onInputSubmitted(taskId: string, text: string) {
  axios.post(`/api/plug/agent/tasks/${taskId}/input`, { text })
    .then(() => fetchTasks())
    .catch((e) => console.error('Failed to submit input:', e));
}

function onInteractionRespond(payload: any) {
  axios.post('/api/interaction/respond', payload)
    .then(() => fetchTasks())
    .catch((e) => console.error('Failed to respond:', e));
}

onMounted(() => {
  fetchTasks();
  pollTimer = setInterval(fetchTasks, 5000);
});

onBeforeUnmount(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
});
</script>

<style scoped>
.task-panel { width: 100%; height: 100%; overflow-y: auto; }
.task-item:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
</style>
